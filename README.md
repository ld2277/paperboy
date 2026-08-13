# Paperboy

Daily and weekly news briefs, researched and written by the `paperboy` Claude
skill, published here as a web edition.

- **Latest daily:** https://ld2277.github.io/paperboy/
- **Latest weekly:** https://ld2277.github.io/paperboy/weekly.html
- **Archive:** https://ld2277.github.io/paperboy/archive.html

## How it gets here

The Claude run that writes the brief cannot push to GitHub — its sandbox
proxies git and refuses credentials for repos outside the session's authorised
set. So the brief travels as JSON through a shared Google Drive folder, and
`.github/workflows/publish.yml` collects it on a schedule and publishes.

    Claude run (06:00 ET)  ->  Drive outbox/brief-YYYY-MM-DD-daily.json
    GitHub Action (06:20)  ->  issues/*.html + pdf/*.pdf + index + archive

`tools/paperboy_render.py` owns the house style. Change the layout there, not
in the skill — both the web edition and the PDF render from it.

## Configuration

- Repository **variable** `PAPERBOY_OUTBOX` — the Drive folder id holding the
  brief JSON. The folder must be shared "anyone with the link".
- Repository **secret** `GDRIVE_API_KEY` — optional. Without it the relay
  reads the folder's public listing, which works but is unofficial. With it,
  the relay uses the Drive API proper.
