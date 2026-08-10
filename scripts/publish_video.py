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
  1. Saves the record to data/<id>.json (system of record for future harvests).
  2. Writes docs/videos/<id>.html (a clean reader page Matter can parse).
  3. Rebuilds docs/feed.xml from every data/*.json only in legacy full-feed mode.

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

# These editorial continuations make the short-source clips useful as spoken briefs.
# They are deliberately specific to the item, rather than generic filler, and are
# included in the hosted Matter page while the original record preserves the core
# video summary and timestamp list.
LISTENABLE_EXTENSIONS = {
    "mD7JpNHLT70": """<h2>What separates the system from outreach theatre</h2><p>The strongest part of the example is that every handoff has an observable output. The creator list gives a defined market lens. Engagement collection produces a lead pool. The enrichment waterfall produces a recoverable-contact rate. Verification produces a deliverability signal. And the content loop produces performance data. That is what makes this an operating system rather than a collection of AI tools. If any stage is weak, the next stage makes the weakness visible.</p><p>For a first test, the sensible move is not to reproduce the whole stack. Pick one narrow audience, ten source accounts, and a small number of recent posts. Measure how many people are relevant, how many can be enriched, how many emails verify, and whether the resulting messages lead to real conversations. Only then is it worth adding more providers, volumes, or automation. The decision is ultimately commercial: a system that increases list size but does not improve qualified conversations is merely producing activity.</p><h2>The strategic point</h2><p>There is a shared design principle between the outbound and content examples. Both begin with genuine signal rather than a model inventing demand. Engagement is a signal of attention. Calls, meetings, and internal expertise are signals of something worth saying. The agent helps capture, organise, and reuse those signals. It should not be asked to fabricate the source material or the judgement about what a market needs.</p>""",
    "JWhICz1QR8M": """<h2>What graph engineering changes in practice</h2><p>The useful shift is from a linear prompt to an explicit map of work. A linear prompt hides dependencies: what must be known before the next step, what can happen at the same time, where information should be saved, and where a human decision changes the route. A graph makes those choices visible. It can show a research branch running beside a data-quality branch, both feeding an analyst synthesis, followed by a check that either returns the work for revision or releases it for review.</p><p>That visibility matters because most agent failures are not failures of prose. They are failures of state and coordination. A task may use the wrong version of a brief, repeat a completed step, lose the outcome of a tool call, or treat a weak intermediate result as final. Mapping nodes, inputs, outputs, and transition rules gives each of those failures a place to be detected. It also makes it possible to test a workflow in pieces instead of only judging the final answer.</p><h2>A sensible way to apply it</h2><p>Start with a process that already has known stages and recurring friction. Draw the current human workflow first, including the exceptions, approval gates, and source systems. Then identify which steps are deterministic, which need model judgement, and which should remain human-owned. The graph should be conservative at first: limited tools, named stop conditions, and a written output at every handoff. Once the map works manually, parts of it can be automated without making the whole process opaque.</p><p>For BI and consulting work, this is most valuable when a request crosses research, data retrieval, analysis, writing, and action. The map can make the difference between an impressive one-off agent demo and a repeatable service with clear ownership.</p>""",
    "NClayXM8pU0": """<h2>How to test the promise instead of accepting the demo</h2><p>A credible trial would use a small set of deliberately chosen facts: one stable preference, one active project constraint, one corrected fact, and one fact that a tool must not access. Store them through one model, retrieve them through another, and test the permission boundary as carefully as the happy path. The key questions are whether recall is accurate, whether a correction overrides the old version everywhere, whether deletion is real, and whether the system can explain why a fact was returned.</p><p>This test also exposes a subtle risk. Cross-model memory can make an interaction feel more coherent while quietly importing an outdated assumption. A model that receives stale context may sound more confident, not less. That is why each stored item needs a date, a source, and ideally an expiry or review rule. Context that was true for a temporary project should not silently become a permanent instruction for every future agent.</p><h2>The architecture choice underneath the product</h2><p>The clip is really about a design choice between implicit and explicit context. Implicit context is convenient because the provider manages it, but the user cannot easily inspect the boundary. Explicit context is slower to assemble, but it can be versioned, reviewed, and reused across tools. A good personal system can use both: a human-readable vault as the canonical layer, concise machine-readable project files for reliable retrieval, and an optional service that provides convenient cross-model access.</p><p>That framing keeps the decision practical. The question is not whether one model has better memory. It is whether the work has a reliable source of truth, a permission model proportionate to sensitivity, and a low-friction way for the right agent to retrieve only the relevant context.</p>""",
    "MReIEoyTDB8": """<h2>What makes an evaluation loop operational</h2><p>The hard part is choosing the unit of judgement. Do not ask a reviewer whether an agent output feels good. Ask whether it reached the right conclusion, cited enough evidence, respected the relevant policy, and took an action that was appropriate for the risk. Each criterion should be simple enough that two qualified reviewers can usually agree. If they cannot, the rubric is still describing taste rather than an operational standard.</p><p>Sampling design matters as much as the rubric. A random sample is useful for detecting drift, but it should be supplemented by deliberate samples of high-risk, novel, and failed cases. Review the work that triggered a tool error, used a newly changed source, produced an unusually confident recommendation, or fell near a decision threshold. These cases create a much faster learning loop than reviewing only routine successes.</p><h2>From review to improvement</h2><p>Every correction should lead to one of four outcomes: update a source of truth, improve an instruction, constrain or repair a tool, or add a regression case. If a reviewed error does not change any of those, it will probably recur. The regression set should be kept small and representative at first. Its job is to catch known failures before a change ships, not to imitate an academic benchmark.</p><p>For a BI agent, the first candidate could be a weekly analytical brief. Keep a fixed set of past requests and expected evidence, compare the draft with an analyst review, and label the disagreement. Over a few weeks, this yields a grounded picture of where the agent is useful, where it needs a human, and which safeguards actually improve quality.</p>""",
    "h2C5UZGgUHs": """<h2>How to make the score earn trust</h2><p>A score should be treated as an explanation tool, not a permission slip. The reviewer needs to see the factors behind it: which files or systems were affected, why rollback may be difficult, which tests are relevant, and what the agent could not verify. A good output can be short but must be legible. “High risk because it changes authentication and has no integration coverage” is useful. “Score: 68” is not.</p><p>The thresholds also need calibration against real outcomes. For a period, run the score beside normal human review and record when reviewers disagree. If reviewers repeatedly approve medium-risk changes quickly, the policy may be too conservative. If they repeatedly catch issues in low-risk changes, the criteria are too narrow. The aim is not to remove judgement. It is to direct scarce judgement to the changes where it has the highest expected value.</p><h2>Beyond code review</h2><p>The same routing logic applies wherever an AI system recommends or executes work. A data agent might score an output by source reliability, sensitivity, customer impact, reversibility, and the gap between the claim and the available evidence. A marketing agent might score whether a draft uses approved claims, whether it is externally visible, and whether a factual assertion has a source. Low-risk work can move quickly, while higher-risk work gets a defined human checkpoint.</p><p>The important design constraint is that exceptions remain visible. A policy must say when a category requires review regardless of the total score. That preserves accountability for sensitive changes and prevents a collection of small points from accidentally normalising a serious risk.</p>""",
    "Bop3CJdF960": """<h2>What a responsible browser-run looks like</h2><p>Before the agent touches a live browser, give it a clear target state and a small permission envelope. It should know the application, the integration being configured, the intended scopes, the callback destination, and the actions that require a human. It should not be left to infer whether it is acceptable to grant broad workspace access or create a new credential. The more specific the target state, the easier it is to notice a wrong turn before it becomes a real configuration change.</p><p>During the run, the useful artifact is a concise change log. It should record pages visited, fields entered, scopes selected, identifiers created, and the exact point where approval is required. That protects against a practical problem with browser work: after ten screens, a person often cannot remember which choice was made on screen two. A short log turns supervision into a reviewable handoff rather than a vague feeling that the agent probably did the right thing.</p><h2>Choosing the boundary</h2><p>Browser automation should stop before it can create durable authority without review. Login, 2FA, consent to sensitive scopes, payment, legal terms, production deployment, and secret creation are natural boundaries. This is not a weakness in the workflow. It is the design that lets routine navigation be delegated while the consequences remain owned by the person or team with the authority to accept them.</p><p>The practical payoff is compounding setup speed. Once a safe path has been documented, the same pattern can be reused for future integrations: inspect, prepare, fill reversible details, pause for authority, confirm the resulting state, and record the configuration. The work becomes less annoying without turning a sensitive admin interface into an unattended automation surface.</p>""",
}


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
    summary_html = rec.get("summary_html", "")
    source_page = rec.get("summary_from_page")
    if source_page:
        with open(os.path.join(DOCS_DIR, source_page)) as f:
            rendered = f.read()
        summary_html = rendered.split("<article>", 1)[1].split("</article>", 1)[0]
        summary_html = summary_html.split("</h1>", 1)[1]
    parts.append(summary_html)
    parts.append(LISTENABLE_EXTENSIONS.get(rec.get("id"), ""))
    wl = watch_list_html(rec)
    if wl:
        parts.append(wl)
    if not rec.get("omit_source_link"):
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
    page_id = rec.get("page_id", rec["id"] + os.environ.get("MATTER_PAGE_SUFFIX", ""))
    with open(os.path.join(VIDEOS_DIR, f'{page_id}.html'), "w") as f:
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
    # --page-only: write the page and durable record, but skip the RSS feed/index.
    # This is the current workflow — summaries are pushed to Matter directly via the
    # Matter CLI/API (matter items save --url <page>), NOT via an RSS subscription.
    args = [a for a in sys.argv[1:] if a != "--page-only"]
    page_only = "--page-only" in sys.argv[1:]
    if len(args) != 1:
        sys.exit("usage: publish_video.py [--page-only] <record.json | ->")

    raw = sys.stdin.read() if args[0] == "-" else open(args[0]).read()
    rec = json.loads(raw)
    for field in ("id", "title", "channel", "url"):
        if not rec.get(field):
            sys.exit(f"record is missing required field: {field}")

    os.makedirs(VIDEOS_DIR, exist_ok=True)
    write_page(rec)

    if page_only:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, f'{rec["id"]}.json'), "w") as f:
            json.dump(rec, f, indent=2, ensure_ascii=False)
        page_id = rec.get("page_id", rec["id"] + os.environ.get("MATTER_PAGE_SUFFIX", ""))
        print(f'page-only: wrote data/{rec["id"]}.json and docs/videos/{page_id}.html '
              f'(feed.xml/index.html NOT rebuilt — push to Matter via CLI/API)')
        return

    # Legacy full-feed mode (RSS). Kept for back-compat; the digest skill no longer uses it.
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, f'{rec["id"]}.json'), "w") as f:
        json.dump(rec, f, indent=2, ensure_ascii=False)
    records = load_records()
    build_feed(records)
    build_index(records)
    print(f'published {rec["id"]} -> docs/videos/{rec["id"]}.html ; feed now has {len(records)} item(s)')


if __name__ == "__main__":
    main()
