#!/usr/bin/env python3
"""Maintain resumable state for daily Matter brief replacement."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "current": None, "pending": None, "story_ledger": {}, "processed_annotation_ids": [], "preferences": {"overrides": {}, "weights": {}}}
    return json.loads(path.read_text())


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temp_name = handle.name
    os.replace(temp_name, path)


def add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--state", type=Path, required=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    stage = commands.add_parser("stage")
    add_common(stage)
    stage.add_argument("--date", required=True)
    stage.add_argument("--item-id", required=True)
    stage.add_argument("--url", required=True)
    promote = commands.add_parser("promote")
    add_common(promote)
    promote.add_argument("--record", type=Path, required=True, help="Validated record used to update the story ledger")
    abort = commands.add_parser("abort")
    add_common(abort)
    args = parser.parse_args()
    state = load(args.state)

    if args.command == "stage":
        if state.get("pending"):
            raise SystemExit("a verified new item is already pending; resolve it before staging another")
        state["pending"] = {"date": args.date, "item_id": args.item_id, "url": args.url, "previous": state.get("current")}
        save(args.state, state)
    elif args.command == "promote":
        if not state.get("pending"):
            raise SystemExit("no pending item to promote")
        record = json.loads(args.record.read_text())
        if record.get("date") != state["pending"]["date"]:
            raise SystemExit("record date does not match the staged Matter item")
        state["current"] = {key: state["pending"][key] for key in ("date", "item_id", "url")}
        state["pending"] = None
        for story in record.get("stories", []):
            state.setdefault("story_ledger", {})[story["id"]] = {
                "last_published": record["date"],
                "category": story["category"],
                "source_urls": [source["url"] for source in story["sources"]],
                "material_update": (story.get("continuation") or {}).get("material_update"),
            }
        save(args.state, state)
    else:
        state["pending"] = None
        save(args.state, state)
    print(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
