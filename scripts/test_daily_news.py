#!/usr/bin/env python3
"""Non-mutating multi-day acceptance test for the daily-news pipeline."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "daily-news" / "fixtures"
VALIDATOR = ROOT / "scripts" / "validate_daily_news.py"
RENDERER = ROOT / "scripts" / "publish_daily_news.py"
STATE_TOOL = ROOT / "scripts" / "daily_news_state.py"


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=True)
    if result.returncode != expect:
        raise SystemExit(f"expected exit {expect}, got {result.returncode}: {' '.join(args)}\n{result.stdout}\n{result.stderr}")
    return result


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)
        state = temp_path / "state.json"
        state.write_text(json.dumps({"story_ledger": {}}))
        for fixture in ("2026-09-01.json", "2026-09-02.json"):
            record = FIXTURES / fixture
            run(sys.executable, str(VALIDATOR), str(record), "--state", str(state))
            payload = json.loads(record.read_text())
            prior = json.loads(state.read_text())
            prior["story_ledger"].update({story["id"]: {"last_published": payload["date"]} for story in payload["stories"]})
            state.write_text(json.dumps(prior))
            run(sys.executable, str(RENDERER), str(record), "--output-dir", str(temp_path / "pages"))
            run(
                sys.executable,
                str(STATE_TOOL),
                "stage",
                "--state",
                str(state),
                "--date",
                payload["date"],
                "--item-id",
                f"itm_{payload['date']}",
                "--url",
                f"https://amir-reza-azimi.github.io/matter-summaries/daily-news/{payload['date']}-daily-brief.html",
            )
            run(sys.executable, str(STATE_TOOL), "promote", "--state", str(state), "--record", str(record))
        run(sys.executable, str(VALIDATOR), str(FIXTURES / "invalid-uncorroborated-major.json"), expect=1)
        english_required = json.loads((FIXTURES / "2026-09-01.json").read_text())
        english_required["stories"][0]["sources"][0].pop("language")
        english_record = temp_path / "invalid-non-english-source.json"
        english_record.write_text(json.dumps(english_required))
        language_failure = run(sys.executable, str(VALIDATOR), str(english_record), expect=1)
        if "language 'en'" not in language_failure.stdout:
            raise SystemExit("daily sources must fail closed unless declared English")
        pages = sorted((temp_path / "pages").glob("*.html"))
        if [page.name for page in pages] != ["2026-09-01-daily-brief.html", "2026-09-02-daily-brief.html"]:
            raise SystemExit("daily pages were not immutable date-based outputs")
        final_state = json.loads(state.read_text())
        if final_state["current"]["date"] != "2026-09-02" or final_state["pending"] is not None:
            raise SystemExit("replacement state did not promote the latest verified item")
    print("daily-news dry-run: 2 valid consecutive briefs rendered; uncorroborated major and non-English sources rejected")


if __name__ == "__main__":
    main()
