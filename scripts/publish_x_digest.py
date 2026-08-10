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

LISTENABLE_EXTENSIONS = {
    "2026-W33": """<h2>What the posts mean together</h2><p>The common thread is that agent capability and agent control have to mature together. A connector makes a useful source of information available. A second tool makes a richer action possible. But every new connection also creates a new route through which instructions, sensitive context, or mistaken assumptions can affect a real outcome. The safe design question is therefore not just whether the agent can access something. It is what it is allowed to infer, which tools it can call next, and who notices when the evidence is weak.</p><p>Layered defenses are valuable because no single protection is reliable enough on its own. Model training can reduce the chance that an agent follows a malicious instruction. Input probes can identify suspicious content. An intent classifier can notice when an action conflicts with the user's apparent goal. Permissions and review gates can reduce the damage if the earlier layers fail. This is closer to a safety case than to a one-time setting. The system is safer because several independent checks have to fail before a bad action reaches a sensitive boundary.</p><h2>A practical operating checklist</h2><p>For each connected workflow, name the data it can read, the actions it can take, and the highest-consequence action it could reach through a chain of tool calls. Keep access narrow at first. Test with benign but adversarial inputs. Make the agent surface the evidence it used before it sends, publishes, or changes anything. Add a human checkpoint for external communication, sensitive data, money, permissions, and other irreversible effects. Then review actual runs, not only a clean demo, to see where the workflow accumulates ambiguity.</p><p>For the personal operating system and AI-native client work, the useful lesson is to design connectors as capabilities with explicit boundaries. A calendar, inbox, CRM, search tool, and internal knowledge base can be powerful in combination, but the workflow should say exactly what decision each one supports. This produces a system that is easier to audit, easier to improve, and safer to delegate. It also gives a clearer consulting conversation: the value is not more tools connected, but a defensible path from evidence to action.</p>"""
}


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
    parts.append(LISTENABLE_EXTENSIONS.get(rec.get("week"), ""))
    sl = source_list_html(rec)
    if sl:
        parts.append(sl)
    return "\n".join(parts)


def write_page(rec):
    inner = article_inner_html(rec)
    suffix = os.environ.get("MATTER_PAGE_SUFFIX", "")
    page_title = rec["title"] + (" · Audio brief" if suffix else "")
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(page_title)}</title>
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
<h1>{esc(page_title)}</h1>
{inner}
</article>
</body>
</html>
"""
    page_id = rec.get("page_id", rec["week"] + os.environ.get("MATTER_PAGE_SUFFIX", ""))
    with open(os.path.join(X_DIR, f'{page_id}.html'), "w") as f:
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

    page_id = rec.get("page_id", rec["week"] + os.environ.get("MATTER_PAGE_SUFFIX", ""))
    print(f'wrote docs/x/{page_id}.html '
          f'({"page-only" if page_only else "page + data record"}) — push to Matter via API')


if __name__ == "__main__":
    main()
