"""
Paperboy relay — runs on GitHub Actions, not in the Claude sandbox.

The sandbox can research and write, but it cannot push to GitHub: the cloud
container's git proxy refuses credentials for repos outside the session's
authorised set, and the Claude GitHub integration is read-only. So the brief
travels as JSON through a shared Drive folder, and this script — running on a
GitHub runner with a normal network stack — collects it and publishes.

    outbox/brief-2026-08-13-daily.json   written by the 06:00 Claude run
        |
        v  (this script, 06:20)
    issues/2026-08-13-daily.html + pdf/ + index.html + archive.html
                                 + state/brief-log.md

The brief's `log` field is the run log the next Claude run reads to avoid
repeating headlines. It is written back on every run from the newest brief
seen -- published or already published -- so a repo whose log has fallen
behind repairs itself on the next Action run rather than at the next publish.

Anything already listed in issues.json is skipped, so re-running is harmless
and a missed day is picked up by the next run.

Environment:
    PAPERBOY_OUTBOX   Drive folder id holding the brief JSON (required)
    GDRIVE_API_KEY    optional; without it, the public folder view is scraped
    PAPERBOY_NO_PDF   set to skip the WeasyPrint step
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paperboy_publish import Repo  # noqa: E402
from paperboy_render import render_issue  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTBOX = os.environ.get("PAPERBOY_OUTBOX", "").strip()
API_KEY = os.environ.get("GDRIVE_API_KEY", "").strip()

UA = {"User-Agent": "Mozilla/5.0 (paperboy relay)"}


def _get(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ------------------------------------------------------------------- drive

def list_outbox():
    """[(file_id, name)] for brief-*.json in the outbox, oldest name first.

    Two paths. The API key is the supported one and should be preferred. The
    scrape exists so setup needs no Google Cloud project on day one; it reads
    the legacy embedded folder view, which returns plain HTML for any folder
    shared with 'anyone with the link'.
    """
    if not OUTBOX:
        raise SystemExit("PAPERBOY_OUTBOX is not set")

    if API_KEY:
        query = urllib.parse.quote(f"'{OUTBOX}' in parents and trashed = false")
        url = (f"https://www.googleapis.com/drive/v3/files?q={query}"
               f"&key={API_KEY}&fields=files(id,name)&pageSize=200")
        files = json.loads(_get(url))["files"]
        found = [(f["id"], f["name"]) for f in files]
    else:
        html = _get(f"https://drive.google.com/embeddedfolderview?id={OUTBOX}#list")
        html = html.decode("utf-8", "replace")
        # rows look like: <div id="entry-<ID>" ...><... >name.json</div>
        found = re.findall(
            r'id="entry-([A-Za-z0-9_-]{20,})".*?flip-entry-title[^>]*>([^<]+)<',
            html, re.S,
        )

    briefs = [(fid, name) for fid, name in found
              if name.startswith("brief-") and name.endswith(".json")]
    briefs.sort(key=lambda pair: pair[1])
    return briefs


def fetch(file_id):
    if API_KEY:
        url = (f"https://www.googleapis.com/drive/v3/files/{file_id}"
               f"?alt=media&key={API_KEY}")
    else:
        url = f"https://drive.google.com/uc?export=download&id={file_id}"
    return json.loads(_get(url))


# --------------------------------------------------------------------- pdf

PAGE_CSS = """
@page { size: A4; margin: 0; background: #FFF1E5; }
* { font-family: 'Bitstream Charter', 'Century Schoolbook L', 'DejaVu Serif', serif !important; }
p, div { orphans: 3; widows: 3; }
.jump, .foot { display: none; }
.item { break-inside: avoid; page-break-inside: avoid; }
.item h2, .topic, .field { break-after: avoid; page-break-after: avoid; }
.wrap { max-width: none; padding: 32px 28px; }
"""


def render_pdf(brief, path):
    """Typeset archive copy. Never fail the run over it — the web edition is
    the product and a missing PDF is a footnote, not an outage."""
    try:
        from weasyprint import CSS, HTML
        html = render_issue(dict(brief, pdf=None), root="")
        HTML(string=html).write_pdf(path, stylesheets=[CSS(string=PAGE_CSS)])
        return path
    except Exception as exc:  # noqa: BLE001
        print(f"  pdf skipped: {exc}")
        return None


# -------------------------------------------------------------------- main

LOG_PATH = os.path.join(REPO_ROOT, "state", "brief-log.md")


def write_log(text):
    """Persist the run log. Returns True if the file changed on disk.

    Never fail the run over it -- a stale log costs a repeated headline, a
    crashed relay costs the whole edition."""
    if not text or not text.strip():
        return False
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH) as fh:
                if fh.read() == text:
                    return False
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w") as fh:
            fh.write(text)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"  log not written: {exc}")
        return False


def already_published(kind, date):
    manifest = os.path.join(REPO_ROOT, "issues.json")
    if not os.path.exists(manifest):
        return False
    with open(manifest) as fh:
        return any(i["date"] == date and i["kind"] == kind for i in json.load(fh))


def main():
    briefs = list_outbox()
    print(f"outbox: {len(briefs)} brief file(s)")

    repo = Repo.at(REPO_ROOT)
    published = []
    latest_log = None

    for file_id, name in briefs:
        try:
            brief = fetch(file_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: could not fetch — {exc}")
            continue

        missing = [k for k in ("kind", "date", "dateline", "sections") if k not in brief]
        if missing:
            print(f"  {name}: malformed, missing {missing} — skipped")
            continue

        # Briefs arrive oldest name first, so the last assignment wins and
        # the log always comes from the newest brief in the outbox.
        if isinstance(brief.get("log"), str):
            latest_log = brief["log"]

        if already_published(brief["kind"], brief["date"]):
            print(f"  {name}: already published")
            continue

        pdf = None
        if not os.environ.get("PAPERBOY_NO_PDF"):
            pdf = render_pdf(brief, f"/tmp/{brief['date']}-{brief['kind']}.pdf")

        repo.publish(brief, pdf_path=pdf, push=False)
        published.append(name)
        print(f"  {name}: published")

    if not published:
        print("nothing new")
    else:
        print(f"published {len(published)}: {', '.join(published)}")

    log_updated = write_log(latest_log)
    if log_updated:
        print("run log updated")

    # Surfaced to the workflow so it can skip an empty commit. `changed` is
    # what the commit step gates on: a log-only run still needs committing.
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as fh:
            fh.write(f"published={len(published)}\n")
            fh.write(f"log_updated={int(log_updated)}\n")
            fh.write(f"changed={int(bool(published) or log_updated)}\n")


if __name__ == "__main__":
    main()
