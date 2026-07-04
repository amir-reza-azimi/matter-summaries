#!/usr/bin/env python3
"""
publish_x_digest.py — turn a weekly X-digest record into a GitHub Pages article.

Usage:
    python3 scripts/publish_x_digest.py --page-only path/to/record.json
    cat record.json | python3 scripts/publish_x_digest.py --page-only -

Sibling of publish_video.py, for the matter-x-digest skill. Instead of one page per
video it hosts ONE combined brief per week. The brief is pushed to Matter directly via
the Matter API (POST /items with the hosted page URL), so --page-only is the normal path.

A "record" is JSON with these fields (produced by the matter-x-digest skill):

    {
      "week": "2026-W27",                                   # ISO year-week (required, used as id/filename)
      "title": "X digest — week of 2026-07-06",              # required
      "date_range": "2026-06-30 – 2026-07-06",
      "summary_html": "<p>...the ~850-1000 word combined brief as HTML...</p>",  # required
      "source_list": [
        {"author": "bcherny", "permalink": "https://x.com/bcherny/status/123", "label": "Claude Code code review"},
        ...
      ]
    }

The script writes docs/x/<week>.html — a clean reader page Matter can parse as an article.
It is idempotent: re-running with the same week overwrites that one page. Nothing else is touched.
"""

import sys
import os
import json
import html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
X_DIR = os.path.join(DOCS_DIR, "x")

SITE_BASE = "https://amir-reza-azimi.github.io/matter-summaries"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def source_list_html(rec):
    items = rec.get("source_list") or []
    if not items:
        return ""
    rows = []
    for s in items:
        author = esc(s.get("author", ""))
        handle = f"@{author}" if author and not author.startswith("@") else author
        label = esc(s.get("label", ""))
        link = esc(s.get("permalink", ""))
        rows.append(f'<li><strong>{handle}</strong> &mdash; {label} '
                    f'(<a href="{link}">open on X</a>)</li>')
    return "<h2>Sources</h2>\n<ul>\n" + "\n".join(rows) + "\n</ul>"


def article_inner_html(rec):
    parts = []
    dr = rec.get("date_range", "")
    n = len(rec.get("source_list") or [])
    meta = f'<p><strong>Week:</strong> {esc(rec.get("week", ""))}'
    if dr:
        meta += f' &middot; <strong>Window:</strong> {esc(dr)}'
    if n:
        meta += f' &middot; <strong>Sources:</strong> {n} posts'
    meta += "</p>"
    parts.append(meta)
    parts.append(rec.get("summary_html", ""))
    sl = source_list_html(rec)
    if sl:
        parts.append(sl)
    return "\n".join(parts)


def write_page(rec):
    inner = article_inner_html(rec)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(rec["title"])}</title>
<meta name="description" content="{esc(rec.get("date_range", ""))}">
<style>
  body {{ max-width: 720px; margin: 2rem auto; padding: 0 1rem;
         font: 18px/1.6 -apple-system, system-ui, sans-serif; color: #1a1a1a; }}
  h1 {{ font-size: 1.7rem; line-height: 1.25; }}
  h2 {{ margin-top: 2rem; }}
  a {{ color: #3b5bdb; }}
</style>
</head>
<body>
<article>
<h1>{esc(rec["title"])}</h1>
{inner}
</article>
</body>
</html>
"""
    with open(os.path.join(X_DIR, f'{rec["week"]}.html'), "w") as f:
        f.write(page)


def main():
    # --page-only: write just docs/x/<week>.html. This is the normal workflow — the brief
    # is pushed to Matter directly via the API (POST /items with the page URL).
    args = [a for a in sys.argv[1:] if a != "--page-only"]
    page_only = "--page-only" in sys.argv[1:]
    if len(args) != 1:
        sys.exit("usage: publish_x_digest.py [--page-only] <record.json | ->")

    raw = sys.stdin.read() if args[0] == "-" else open(args[0]).read()
    rec = json.loads(raw)
    for field in ("week", "title", "summary_html"):
        if not rec.get(field):
            sys.exit(f"record is missing required field: {field}")

    os.makedirs(X_DIR, exist_ok=True)
    write_page(rec)

    if not page_only:
        # Keep a system-of-record copy alongside the video digest's data/ dir.
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, f'x-{rec["week"]}.json'), "w") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)

    print(f'wrote docs/x/{rec["week"]}.html '
          f'({"page-only" if page_only else "page + data record"}) — push to Matter via API')


if __name__ == "__main__":
    main()
