#!/usr/bin/env python3
"""Render one validated Daily Brief as an immutable Matter-readable page."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from daily_news_common import validate_record


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "daily-news"
SITE_BASE = "https://amir-reza-azimi.github.io/matter-summaries/daily-news"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render(record: dict) -> str:
    rows = []
    for story in record["stories"]:
        source_links = " · ".join(
            f'<a href="{esc(source["url"])}">{esc(source["publisher"])} </a>'
            for source in story["sources"]
        )
        rows.append(
            "<section class=\"story\" "
            f'data-story-id="{esc(story["id"])}">'
            f'<p class="meta">{esc(story["category"])} · {esc(story["importance"])}</p>'
            f'<h2>{esc(story["title"])}</h2>'
            f'<p>{esc(story["summary"])}</p>'
            f'<p class="sources">Read more: {source_links}</p></section>'
        )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(record["title"])}</title>
<style>body{{max-width:720px;margin:2rem auto;padding:0 1rem;font:18px/1.6 -apple-system,system-ui,sans-serif;color:#1a1a1a}}h1{{font-size:1.8rem;line-height:1.25}}h2{{font-size:1.2rem;line-height:1.35;margin-bottom:.2rem}}.story{{border-top:1px solid #ddd;padding:1rem 0}}.meta,.sources{{font-size:.85rem;color:#555;margin:.1rem 0}}a{{color:#3b5bdb}}</style>
</head><body><article>{''.join(rows)}</article></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--page-suffix", help="Optional stable suffix for a user-requested replacement edition")
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    errors = validate_record(record)
    if errors:
        raise SystemExit("refusing to render invalid record:\n- " + "\n- ".join(errors))
    suffix = ""
    if args.page_suffix:
        if not re.fullmatch(r"[a-z0-9-]+", args.page_suffix):
            raise SystemExit("page suffix must use lowercase letters, numbers, and hyphens")
        suffix = f"-{args.page_suffix}"
    page_id = f"{record['date']}{suffix}-daily-brief"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"{page_id}.html"
    output.write_text(render(record))
    print(json.dumps({"page_id": page_id, "path": str(output), "url": f"{SITE_BASE}/{page_id}.html"}))


if __name__ == "__main__":
    main()
