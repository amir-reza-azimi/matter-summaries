#!/usr/bin/env python3
"""Validate a structured daily-news record before any page or Matter mutation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from daily_news_common import validate_record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("record", type=Path)
    parser.add_argument("--state", type=Path, help="Optional daily-news state for repeat detection")
    args = parser.parse_args()
    record = json.loads(args.record.read_text())
    prior_stories = {}
    if args.state and args.state.exists():
        prior_stories = (json.loads(args.state.read_text()).get("story_ledger") or {})
    errors = validate_record(record, prior_stories)
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        raise SystemExit(1)
    print(json.dumps({"valid": True, "story_count": len(record["stories"])}, indent=2))


if __name__ == "__main__":
    main()
