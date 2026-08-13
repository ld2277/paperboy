"""
Paperboy — publish an issue to GitHub Pages.

This file lives in the repo it publishes to, under tools/. A run clones the
repo (which is also how it gets this code), builds the brief as a dict, and
calls publish(). The skill stays short because the machinery is versioned
here instead of being pasted into a prompt every morning.

    import sys; sys.path.insert(0, "/tmp/paperboy/tools")
    from paperboy_publish import Repo

    repo = Repo.clone("louka", "paperboy", token)      # or .at(path, ...)
    url  = repo.publish(brief, pdf_path="brief.pdf")

Repo layout it maintains:

    index.html          latest daily      <- the bookmark / home-screen target
    weekly.html         latest weekly
    archive.html        every issue, newest first
    issues.json         manifest (source of truth for the archive)
    issues/2026-08-13-daily.html
    pdf/2026-08-13-daily.pdf
    icon.png            home-screen icon
    tools/              this code
    .nojekyll           stop Pages running Jekyll over the files
"""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from datetime import date as _date

from paperboy_render import render_archive, render_issue

API = "https://api.github.com"


# ------------------------------------------------------------------ helpers

def _month_label(iso):
    """'2026-08-13' -> 'August 2026'. Groups the archive."""
    year, month, day = (int(p) for p in iso.split("-"))
    return _date(year, month, day).strftime("%B %Y")


def _run(cmd, cwd, secret=None):
    """Run a command, scrubbing the token from anything we might surface."""
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout).strip()
        if secret:
            err = err.replace(secret, "***")
        raise RuntimeError(f"`{' '.join(cmd[:3])}` failed: {err}")
    return proc.stdout.strip()


def api(path, token, method="GET", body=None):
    req = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "paperboy",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw)
        except Exception:
            return exc.code, {"message": raw.decode(errors="replace")[:300]}


def make_icon(path):
    """Salmon tile, red serif P. The home-screen icon on iOS."""
    from PIL import Image, ImageDraw, ImageFont

    size = 180
    img = Image.new("RGB", (size, size), "#FFF1E5")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, size - 1, 12], fill="#E3120B")
    font = None
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ):
        if os.path.exists(candidate):
            font = ImageFont.truetype(candidate, 112)
            break
    if font is None:
        font = ImageFont.load_default()
    box = draw.textbbox((0, 0), "P", font=font)
    draw.text(
        ((size - box[2] + box[0]) / 2 - box[0], (size - box[3] + box[1]) / 2 - box[1] + 6),
        "P", fill="#E3120B", font=font,
    )
    img.save(path, "PNG")


# --------------------------------------------------------------------- repo

class Repo:
    """A local checkout of the paperboy Pages repo."""

    def __init__(self, path, owner, name, token=None):
        self.path = path
        self.owner = owner
        self.name = name
        self.token = token

    # -- constructors --

    @classmethod
    def clone(cls, owner, name, token, path=None):
        path = path or tempfile.mkdtemp(prefix="paperboy-")
        if os.path.exists(path) and os.listdir(path):
            shutil.rmtree(path)
        remote = f"https://x-access-token:{token}@github.com/{owner}/{name}.git"
        _run(["git", "clone", "--depth", "1", remote, path], cwd="/", secret=token)
        _run(["git", "config", "user.email", "paperboy@localhost"], cwd=path)
        _run(["git", "config", "user.name", "Paperboy"], cwd=path)
        return cls(path, owner, name, token)

    @classmethod
    def at(cls, path, owner="x", name="y", token=None):
        """An existing directory. With no token, publish() builds but never pushes."""
        os.makedirs(path, exist_ok=True)
        return cls(path, owner, name, token)

    # -- one-time setup --

    def ensure(self, private=False):
        """Create the repo and switch Pages on. Safe to call repeatedly."""
        status, _ = api(f"/repos/{self.owner}/{self.name}", self.token)
        created = False
        if status == 404:
            status, data = api(
                "/user/repos", self.token, "POST",
                {
                    "name": self.name,
                    "description": "Paperboy — daily and weekly news briefs.",
                    "private": private,
                    "auto_init": True,
                    "has_issues": False,
                    "has_wiki": False,
                    "has_projects": False,
                },
            )
            if status not in (200, 201):
                raise RuntimeError(f"could not create repo: {data.get('message')}")
            created = True
        elif status != 200:
            raise RuntimeError(f"could not read repo ({status})")

        status, data = api(f"/repos/{self.owner}/{self.name}/pages", self.token)
        if status == 404:
            status, data = api(
                f"/repos/{self.owner}/{self.name}/pages", self.token, "POST",
                {"source": {"branch": "main", "path": "/"}},
            )
            if status not in (200, 201, 409):
                raise RuntimeError(f"could not enable Pages: {data.get('message')}")
        return created, self.url

    @property
    def url(self):
        return f"https://{self.owner}.github.io/{self.name}/"

    # -- the work --

    def publish(self, brief, pdf_path=None, push=True):
        """File one issue, rebuild index and archive, commit, push.

        Returns the public URL of the issue.
        """
        kind, date = brief["kind"], brief["date"]
        slug = f"{date}-{kind}"
        work = self.path

        for sub in ("issues", "pdf"):
            os.makedirs(os.path.join(work, sub), exist_ok=True)

        pdf_href = None
        if pdf_path and os.path.exists(pdf_path):
            pdf_href = f"pdf/{slug}.pdf"
            shutil.copy(pdf_path, os.path.join(work, pdf_href))

        # Two renders of the same content, differing only in how they reach
        # the other pages: the landing copy sits at the root, the permanent
        # copy one directory down. Getting this wrong is how archive and PDF
        # links quietly 404.
        with open(os.path.join(work, "issues", f"{slug}.html"), "w") as fh:
            fh.write(render_issue(
                dict(brief, pdf=f"../{pdf_href}" if pdf_href else None), root="../"))

        # index.html is the latest daily, so the home-screen icon always opens
        # today's brief with no navigation.
        landing = "index.html" if kind == "daily" else "weekly.html"
        with open(os.path.join(work, landing), "w") as fh:
            fh.write(render_issue(dict(brief, pdf=pdf_href), root=""))

        # -- manifest drives the archive; never parse the HTML back --
        manifest = os.path.join(work, "issues.json")
        issues = []
        if os.path.exists(manifest):
            with open(manifest) as fh:
                issues = json.load(fh)
        issues = [i for i in issues if not (i["date"] == date and i["kind"] == kind)]
        issues.append({
            "date": date,
            "kind": kind,
            "dateline": brief["dateline"],
            "month": _month_label(date),
            "href": f"issues/{slug}.html",
            "pdf": pdf_href,
            "standfirst": brief.get("standfirst", ""),
        })
        issues.sort(key=lambda i: (i["date"], i["kind"]), reverse=True)
        with open(manifest, "w") as fh:
            json.dump(issues, fh, indent=1)

        with open(os.path.join(work, "archive.html"), "w") as fh:
            fh.write(render_archive(issues))

        open(os.path.join(work, ".nojekyll"), "w").close()
        icon = os.path.join(work, "icon.png")
        if not os.path.exists(icon):
            try:
                make_icon(icon)
            except Exception:
                pass  # an icon is a nicety; never fail a run over it

        if not (push and self.token):
            return f"file://{work}/{landing}"

        _run(["git", "add", "-A"], cwd=work)
        if _run(["git", "status", "--porcelain"], cwd=work):
            _run(["git", "commit", "-m", f"{kind}: {brief['dateline']}"],
                 cwd=work, secret=self.token)
            _run(["git", "push", "origin", "HEAD"], cwd=work, secret=self.token)
        return f"https://{self.owner}.github.io/{self.name}/issues/{slug}.html"
