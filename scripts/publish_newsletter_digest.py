#!/usr/bin/env python3
"""Render a weekly newsletter digest as a Matter-readable GitHub Pages article.

Usage:
  python3 scripts/publish_newsletter_digest.py --page-only record.json

The input record requires ``week``, ``kind`` (``tools`` or ``news``), ``title``,
and ``summary_html``. Optional ``entries`` provide visible source links.
"""

from __future__ import annotations

import html
import json
import os
import re
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(ROOT, "docs", "newsletters")
SITE_BASE = "https://amir-reza-azimi.github.io/matter-summaries"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def safe_id(value: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", value.lower()).strip("-")


def entry_html(entries: list[dict]) -> str:
    if not entries:
        return ""
    rows = []
    for entry in entries:
        title = esc(entry.get("title") or entry.get("name") or "Untitled")
        source = esc(entry.get("source"))
        detail = esc(entry.get("description"))
        url = esc(entry.get("url"))
        link = f'<a href="{url}">Open</a>' if url else ""
        meta = " · ".join(part for part in (source, link) if part)
        rows.append(f"<li><strong>{title}</strong>{': ' + detail if detail else ''}{'<br><small>' + meta + '</small>' if meta else ''}</li>")
    return "<h2>Links</h2><ul>" + "\n".join(rows) + "</ul>"


def render(record: dict) -> tuple[str, str]:
    week = record["week"]
    kind = record["kind"]
    page_id = record.get("page_id") or f"{week}-{safe_id(kind)}"
    title = record["title"]
    date_range = record.get("date_range", "")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(title)}</title>
  <meta name="description" content="{esc(date_range)}">
  <style>body {{ max-width: 720px; margin: 2rem auto; padding: 0 1rem; font: 18px/1.6 -apple-system, system-ui, sans-serif; color: #1a1a1a; }} h1 {{ font-size: 1.7rem; line-height: 1.25; }} h2 {{ margin-top: 2rem; }} a {{ color: #3b5bdb; }}</style>
</head>
<body><article>
  <h1>{esc(title)}</h1>
  <p><strong>Week:</strong> {esc(week)}{f' · <strong>Window:</strong> {esc(date_range)}' if date_range else ''}</p>
  {record["summary_html"]}
  {entry_html(record.get("entries") or [])}
</article></body></html>
"""
    return page_id, page


def main() -> None:
    args = [arg for arg in sys.argv[1:] if arg != "--page-only"]
    if len(args) != 1:
        raise SystemExit("usage: publish_newsletter_digest.py --page-only <record.json | ->")
    raw = sys.stdin.read() if args[0] == "-" else open(args[0], encoding="utf-8").read()
    record = json.loads(raw)
    for field in ("week", "kind", "title", "summary_html"):
        if not record.get(field):
            raise SystemExit(f"record is missing required field: {field}")
    if record["kind"] not in {"tools", "news"}:
        raise SystemExit("kind must be tools or news")
    page_id, page = render(record)
    os.makedirs(DOCS_DIR, exist_ok=True)
    output = os.path.join(DOCS_DIR, f"{page_id}.html")
    with open(output, "w", encoding="utf-8") as handle:
        handle.write(page)
    print(f"wrote docs/newsletters/{page_id}.html — push to Matter with {SITE_BASE}/newsletters/{page_id}.html")


if __name__ == "__main__":
    main()
