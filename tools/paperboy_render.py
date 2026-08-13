"""
Paperboy — screen-first HTML renderer.

House style: Financial Times paper stock, Economist structure.
One data structure in, a self-contained responsive page out.

Public API:
    render_issue(brief)  -> str   the brief as a standalone HTML page
    render_archive(idx)  -> str   the archive index page

Nothing here touches the network or the filesystem. Keep it that way so it
stays trivially testable.
"""

from html import escape

# ---------------------------------------------------------------- palette

PAPER = "#FFF1E5"
INK = "#33302E"
MUTED = "#66605C"
ACCENT = "#E3120B"
HAIRLINE = "#E0D5CB"
LINK = "#0D7680"
LINK_RULE = "#C5D9DB"

SERIF = "Georgia, 'Iowan Old Style', 'Times New Roman', Times, serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Helvetica Neue', Helvetica, Arial, sans-serif"

# Georgia ships on iOS, macOS and Windows, so the phone gets the real face
# rather than a substitute. This is the one place the web version beats the
# PDF, where Georgia is absent from the sandbox and Charter stands in.

STYLE = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{
  margin: 0; background: {PAPER}; color: {INK};
  font-family: {SERIF}; font-size: 17px; line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}}
.wrap {{ max-width: 680px; margin: 0 auto; padding: 28px 24px 64px; }}
a {{ color: {LINK}; text-decoration: none; border-bottom: 1px solid {LINK_RULE}; }}
a:hover {{ border-bottom-color: {LINK}; }}

/* ---- masthead ---- */
.rule-hair {{ border: 0; border-top: 1px solid {HAIRLINE}; margin: 0; }}
.rule-heavy {{ border: 0; border-top: 2px solid {INK}; margin: 0; }}
.masthead {{ text-align: center; padding: 14px 0 10px; }}
.masthead h1 {{
  font-family: {SERIF}; font-size: 40px; font-weight: 700;
  letter-spacing: -0.5px; margin: 0 0 6px;
}}
.dateline {{
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  letter-spacing: 2px; color: {MUTED}; margin: 0;
}}
.standfirst {{
  font-style: italic; font-size: 18px; color: {MUTED};
  margin: 22px 0 0; line-height: 1.5;
}}

/* ---- jump links ---- */
.jump {{
  display: flex; flex-wrap: wrap; gap: 8px;
  margin: 22px 0 0; padding: 0; list-style: none;
}}
.jump a {{
  display: inline-block; font-family: {SANS}; font-size: 11px;
  text-transform: uppercase; letter-spacing: 1.2px; font-weight: 700;
  color: {ACCENT}; border: 1px solid {HAIRLINE}; border-radius: 2px;
  padding: 7px 11px; min-height: 34px; line-height: 20px;
}}
.jump a:hover {{ border-color: {ACCENT}; }}

/* ---- sections ---- */
.section {{ margin-top: 40px; scroll-margin-top: 12px; }}
.topic {{
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  font-weight: 700; letter-spacing: 2px; color: {ACCENT};
  margin: 18px 0 0;
}}
.item {{ margin-top: 26px; }}
.item h2 {{
  font-size: 22px; font-weight: 700; line-height: 1.25;
  margin: 0 0 10px;
}}
.item h2 .num {{
  font-family: {SANS}; font-size: 12px; color: {ACCENT};
  letter-spacing: 1px; vertical-align: 3px; margin-right: 8px;
}}
/* .item p resets margins below, so this needs the extra class to win */
.item p.field, .field {{
  font-family: {SANS}; font-size: 10px; text-transform: uppercase;
  letter-spacing: 1.5px; color: {MUTED}; margin: 20px 0 4px;
}}
.item p {{ margin: 0; }}
.quiet {{ color: {MUTED}; font-style: italic; }}

/* ---- long-form (weekly) ---- */
.longform p {{ margin: 0 0 16px; }}
.longform p.drop::first-letter {{
  font-size: 54px; float: left; line-height: 0.85;
  padding: 4px 7px 0 0; color: {ACCENT}; font-weight: 700;
}}
.pull {{
  font-style: italic; font-size: 21px; line-height: 1.4;
  border-left: 3px solid {ACCENT}; padding-left: 16px;
  margin: 24px 0; color: {INK};
}}
.cal {{ list-style: none; padding: 0; margin: 12px 0 0; }}
.cal li {{ padding: 8px 0; border-bottom: 1px solid {HAIRLINE}; }}
.cal .when {{
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  letter-spacing: 1.2px; color: {ACCENT}; display: block;
}}

/* ---- footer ---- */
.sources {{
  font-family: {SANS}; font-size: 12.5px; color: {MUTED}; line-height: 1.9;
  list-style: none; padding: 0; margin: 12px 0 0;
}}
.sources li {{ margin-bottom: 2px; }}
.foot {{
  margin-top: 48px; padding-top: 14px; border-top: 1px solid {HAIRLINE};
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  letter-spacing: 1.5px; color: {MUTED};
  display: flex; justify-content: space-between; gap: 14px; flex-wrap: wrap;
}}
.foot a {{ color: {MUTED}; border-bottom-color: {HAIRLINE}; }}

/* ---- archive ---- */
.issue {{ padding: 16px 0; border-bottom: 1px solid {HAIRLINE}; }}
.issue a.t {{ font-size: 20px; font-weight: 700; color: {INK}; border: 0; }}
.issue .meta {{
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  letter-spacing: 1.5px; color: {MUTED}; margin-top: 6px;
}}
.issue .peek {{
  font-style: italic; color: {MUTED}; font-size: 16px;
  line-height: 1.5; margin: 6px 0 0;
}}
.badge {{ color: {ACCENT}; font-weight: 700; }}
.month {{
  font-family: {SANS}; font-size: 11px; text-transform: uppercase;
  font-weight: 700; letter-spacing: 2px; color: {MUTED};
  margin: 36px 0 0; padding-bottom: 8px; border-bottom: 2px solid {INK};
}}

/* ---- phone ---- */
@media (max-width: 480px) {{
  body {{ font-size: 17px; }}
  .wrap {{ padding: 20px 18px 56px; }}
  .masthead h1 {{ font-size: 31px; }}
  .dateline {{ font-size: 10px; letter-spacing: 1.4px; }}
  .standfirst {{ font-size: 17px; }}
  .item h2 {{ font-size: 20px; }}
  .section {{ margin-top: 34px; }}
}}

/* ---- print: ⌘P from the page still behaves ---- */
@media print {{
  body {{ font-size: 11pt; }}
  .jump, .foot {{ display: none; }}
  .item, .issue {{ break-inside: avoid; page-break-inside: avoid; }}
  .item h2, .topic, .field {{ break-after: avoid; page-break-after: avoid; }}
  p, div {{ orphans: 3; widows: 3; }}
  a {{ border: 0; }}
}}
"""

HEAD = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Paperboy">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="theme-color" content="{paper}">
<link rel="apple-touch-icon" href="{root}icon.png">
<title>{title}</title>
<style>{style}</style>
</head><body><div class="wrap">
"""


def _slug(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-")


def _link(source):
    return '<a href="{}" target="_blank" rel="noopener">{}</a>'.format(
        escape(source["url"], quote=True), escape(source["title"])
    )


def _para(text):
    """Body text may arrive with inline <a> tags already in it; trust it."""
    return text if "<" in text else escape(text)


def _item(item, number=None):
    num = f'<span class="num">{number}</span>' if number else ""
    out = ['<div class="item">']
    out.append(f'<h2>{num}{_para(item["headline"])}</h2>')
    for label, key in (
        ("What happened", "happened"),
        ("Context", "context"),
        ("Who's affected", "affected"),
        ("What it means", "means"),
        ("Watch next", "watch"),
    ):
        if item.get(key):
            out.append(f'<p class="field">{label}</p><p>{_para(item[key])}</p>')
    out.append("</div>")
    return "\n".join(out)


def _head(title, root=""):
    return HEAD.format(title=escape(title), style=STYLE, paper=PAPER, root=root)


def _masthead(dateline, standfirst, root=""):
    return f"""<hr class="rule-hair">
<div class="masthead"><h1>PAPERBOY</h1><p class="dateline">{escape(dateline)}</p></div>
<hr class="rule-heavy">
<p class="standfirst">{_para(standfirst)}</p>"""


def _foot(root="", extra=""):
    return f"""<div class="foot">
<span><a href="{root}archive.html">Archive</a></span>
<span>{extra}</span>
</div></div></body></html>"""


def render_issue(brief, root=""):
    """brief: see SAMPLE at the bottom of this file for the shape."""
    kind = brief.get("kind", "daily")
    title = f"Paperboy — {brief['dateline']}"
    parts = [_head(title, root), _masthead(brief["dateline"], brief["standfirst"], root)]

    # jump links — the thing that makes six sections navigable by thumb
    sections = brief.get("sections", [])
    jumps = []
    if brief.get("top_story"):
        jumps.append(("Top story", "top-story"))
    jumps += [(s["topic"], _slug(s["topic"])) for s in sections]
    if brief.get("profile"):
        jumps.append(("Profile", "profile"))
    if brief.get("calendar"):
        jumps.append(("Calendar", "calendar"))
    if jumps:
        links = "".join(
            f'<li><a href="#{anchor}">{escape(label)}</a></li>' for label, anchor in jumps
        )
        parts.append(f'<ul class="jump">{links}</ul>')

    if brief.get("top_story"):
        ts = brief["top_story"]
        parts.append('<div class="section" id="top-story">')
        parts.append('<hr class="rule-hair"><p class="topic">Top story of the week</p>')
        parts.append(f'<div class="item"><h2>{_para(ts["headline"])}</h2></div>')
        parts.append('<div class="longform">')
        for i, para in enumerate(ts["body"]):
            cls = ' class="drop"' if i == 0 else ""
            parts.append(f"<p{cls}>{_para(para)}</p>")
            if ts.get("pull") and i == ts.get("pull_after", 1):
                parts.append(f'<p class="pull">{_para(ts["pull"])}</p>')
        parts.append("</div></div>")

    for section in sections:
        anchor = _slug(section["topic"])
        parts.append(f'<div class="section" id="{anchor}">')
        parts.append(f'<hr class="rule-hair"><p class="topic">{escape(section["topic"])}</p>')
        if section.get("note"):
            parts.append(f'<p class="quiet" style="margin-top:16px">{_para(section["note"])}</p>')
        for n, item in enumerate(section.get("items", []), 1):
            parts.append(_item(item, number=n if kind == "weekly" else None))
        parts.append("</div>")

    if brief.get("profile"):
        pr = brief["profile"]
        parts.append('<div class="section" id="profile">')
        parts.append('<hr class="rule-hair"><p class="topic">Profile</p>')
        parts.append(f'<div class="item"><h2>{_para(pr["headline"])}</h2></div>')
        parts.append('<div class="longform">')
        for i, para in enumerate(pr["body"]):
            cls = ' class="drop"' if i == 0 else ""
            parts.append(f"<p{cls}>{_para(para)}</p>")
        parts.append("</div></div>")

    if brief.get("calendar"):
        parts.append('<div class="section" id="calendar">')
        parts.append('<hr class="rule-hair"><p class="topic">On the calendar</p><ul class="cal">')
        for entry in brief["calendar"]:
            parts.append(
                f'<li><span class="when">{escape(entry["when"])}</span>{_para(entry["what"])}</li>'
            )
        parts.append("</ul></div>")

    if brief.get("sources"):
        parts.append('<div class="section" id="sources">')
        parts.append('<hr class="rule-hair"><p class="topic">Sources</p>')
        parts.append('<ul class="sources">')
        for source in brief["sources"]:
            parts.append(f"<li>{_link(source)}</li>")
        parts.append("</ul></div>")

    extra = ""
    if brief.get("pdf"):
        extra = f'<a href="{escape(brief["pdf"], quote=True)}">PDF</a>'
    parts.append(_foot(root, extra))
    return "\n".join(parts)


def render_archive(issues, root=""):
    """issues: newest first, each {date, dateline, kind, href, pdf?, standfirst}"""
    parts = [
        _head("Paperboy — Archive", root),
        '<hr class="rule-hair">',
        '<div class="masthead"><h1>PAPERBOY</h1>'
        '<p class="dateline">Archive</p></div>',
        '<hr class="rule-heavy">',
    ]
    current_month = None
    for issue in issues:
        month = issue["dateline"].split(",")[-1].strip() if "," in issue["dateline"] else ""
        month = issue.get("month", month)
        if month != current_month:
            parts.append(f'<p class="month">{escape(month)}</p>')
            current_month = month
        badge = "Weekly" if issue["kind"] == "weekly" else "Daily"
        pdf = (
            f' · <a href="{escape(issue["pdf"], quote=True)}">PDF</a>'
            if issue.get("pdf")
            else ""
        )
        peek = issue.get("standfirst", "")
        if len(peek) > 150:
            peek = peek[:150].rsplit(" ", 1)[0] + "…"
        peek_html = f'<p class="peek">{_para(peek)}</p>' if peek else ""
        parts.append(
            f'<div class="issue">'
            f'<a class="t" href="{escape(issue["href"], quote=True)}">{escape(issue["dateline"])}</a>'
            f"{peek_html}"
            f'<div class="meta"><span class="badge">{badge}</span>{pdf}</div>'
            f"</div>"
        )
    parts.append(
        f'<div class="foot"><span><a href="{root}index.html">Latest brief</a></span><span></span></div>'
        "</div></body></html>"
    )
    return "\n".join(parts)
