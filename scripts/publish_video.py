#!/usr/bin/env python3
"""
publish_video.py — turn a video-summary record into a GitHub Pages article + RSS item.

Usage:
    python3 scripts/publish_video.py path/to/record.json
    cat record.json | python3 scripts/publish_video.py -

A "record" is JSON with these fields (produced by the matter-video-digest skill):

    {
      "id": "dQw4w9WgXcQ",                       # YouTube video id (required)
      "title": "How agents actually work",        # required
      "channel": "Simon Scrapes",                 # required
      "channel_url": "https://www.youtube.com/@simonscrapes",
      "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # canonical YouTube watch URL (required)
      "published": "2026-06-18",                  # YYYY-MM-DD (video publish date)
      "duration_minutes": 22,
      "description": "One-line summary for the feed item subtitle.",
      "summary_html": "<p>...the ~850-1000 word listenable summary as HTML...</p>",
      "watch_list": [ {"t": 134, "label": "The eval loop they use"}, ... ]
    }

The script:
  1. Saves the record to data/<id>.json (system of record for the feed).
  2. Writes docs/videos/<id>.html (a clean reader page Matter can parse).
  3. Rebuilds docs/feed.xml from every data/*.json, newest first.

It is idempotent: re-running with the same id overwrites that one record/page
and regenerates the feed. Nothing else is touched.
"""

import sys
import os
import json
import glob
import html
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
DOCS_DIR = os.path.join(ROOT, "docs")
VIDEOS_DIR = os.path.join(DOCS_DIR, "videos")

SITE_BASE = "https://amir-reza-azimi.github.io/matter-summaries"
FEED_TITLE = "AI Video Digest"
FEED_DESC = "Listenable summaries of AI YouTube videos, filtered for Amir's projects."


def esc(s):
    return html.escape(str(s or ""), quote=True)


def watch_list_html(rec):
    items = rec.get("watch_list") or []
    if not items:
        return ""
    vid = rec["id"]
    rows = []
    for w in items:
        t = int(w.get("t", 0))
        mm, ss = divmod(t, 60)
        stamp = f"{mm:d}:{ss:02d}"
        deep = f"https://youtu.be/{esc(vid)}?t={t}"
        rows.append(f'<li><a href="{deep}">{stamp}</a> &mdash; {esc(w.get("label", ""))}</li>')
    return "<h2>Watch these moments</h2>\n<ul>\n" + "\n".join(rows) + "\n</ul>"


def article_inner_html(rec):
    """The body shared by the standalone page and the RSS content:encoded."""
    parts = []
    parts.append(
        f'<p><strong>Channel:</strong> '
        f'<a href="{esc(rec.get("channel_url", rec["url"]))}">{esc(rec["channel"])}</a>'
        f' &middot; <strong>Published:</strong> {esc(rec.get("published", ""))}'
    )
    if rec.get("duration_minutes"):
        parts[-1] += f' &middot; <strong>Length:</strong> {esc(rec["duration_minutes"])} min'
    parts[-1] += (
        f' &middot; <a href="{esc(rec["url"])}">Watch on YouTube</a></p>'
    )
    parts.append(rec.get("summary_html", ""))
    wl = watch_list_html(rec)
    if wl:
        parts.append(wl)
    parts.append(f'<p><a href="{esc(rec["url"])}">Watch the full video on YouTube</a></p>')
    return "\n".join(parts)


def write_page(rec):
    inner = article_inner_html(rec)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(rec["title"])}</title>
<meta name="description" content="{esc(rec.get("description", ""))}">
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
    with open(os.path.join(VIDEOS_DIR, f'{rec["id"]}.html'), "w") as f:
        f.write(page)


def rfc822(date_str):
    """YYYY-MM-DD -> RFC 822 (RSS pubDate). Falls back to now."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        dt = datetime.now(timezone.utc)
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def load_records():
    recs = []
    for p in glob.glob(os.path.join(DATA_DIR, "*.json")):
        with open(p) as f:
            recs.append(json.load(f))
    # newest first; records without a published date sort last
    recs.sort(key=lambda r: r.get("published", ""), reverse=True)
    return recs


def build_feed(records):
    now = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    items = []
    for rec in records:
        content = article_inner_html(rec)
        # Link to our own hosted summary page, NOT the YouTube URL. If the link is a
        # YouTube URL, Matter treats the item as a video and parses YouTube's own page
        # (ignoring our summary). Pointing at our page makes Matter render the summary.
        page_url = f'{SITE_BASE}/videos/{rec["id"]}.html'
        items.append(f"""    <item>
      <title>{esc(rec["title"])}</title>
      <link>{page_url}</link>
      <guid isPermaLink="true">{page_url}</guid>
      <pubDate>{rfc822(rec.get("published"))}</pubDate>
      <dc:creator>{esc(rec.get("channel", ""))}</dc:creator>
      <description>{esc(rec.get("description", ""))}</description>
      <content:encoded><![CDATA[
{content}
]]></content:encoded>
    </item>""")
    feed = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
     xmlns:content="http://purl.org/rss/1.0/modules/content/"
     xmlns:dc="http://purl.org/dc/elements/1.1/"
     xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{FEED_TITLE}</title>
    <link>{SITE_BASE}/</link>
    <atom:link href="{SITE_BASE}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>{FEED_DESC}</description>
    <language>en</language>
    <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
  </channel>
</rss>
"""
    with open(os.path.join(DOCS_DIR, "feed.xml"), "w") as f:
        f.write(feed)


def build_index(records):
    rows = []
    for rec in records:
        rows.append(
            f'<li><a href="videos/{esc(rec["id"])}.html">{esc(rec["title"])}</a>'
            f' <small>&mdash; {esc(rec.get("channel", ""))}, {esc(rec.get("published", ""))}</small></li>'
        )
    body = "\n".join(rows) if rows else "<li><em>No summaries yet.</em></li>"
    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{FEED_TITLE}</title>
<style>body{{max-width:720px;margin:2rem auto;padding:0 1rem;font:18px/1.6 system-ui,sans-serif}}a{{color:#3b5bdb}}</style>
</head><body>
<h1>{FEED_TITLE}</h1>
<p>{FEED_DESC} <a href="feed.xml">RSS feed</a>.</p>
<ul>
{body}
</ul>
</body></html>
"""
    with open(os.path.join(DOCS_DIR, "index.html"), "w") as f:
        f.write(page)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: publish_video.py <record.json | ->")
    raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1]).read()
    rec = json.loads(raw)
    for field in ("id", "title", "channel", "url"):
        if not rec.get(field):
            sys.exit(f"record is missing required field: {field}")

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(VIDEOS_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f'{rec["id"]}.json'), "w") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)

    write_page(rec)
    records = load_records()
    build_feed(records)
    build_index(records)
    print(f'published {rec["id"]} -> docs/videos/{rec["id"]}.html ; feed now has {len(records)} item(s)')


if __name__ == "__main__":
    main()
