#!/usr/bin/env python3
"""Validate the canonical Open Watch event archive before publishing."""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

DEFAULT = Path("data/history/market-watch-events.json")
REQUIRED = ("id", "eventTime", "firstReported", "category", "companyMarket",
            "headline", "source", "sourceUrl", "whyItMatters",
            "expectedImpact", "marketConfirmation", "status")
IMPACT = ("stock", "sox", "nasdaq", "scope", "direction", "materiality")
CONFIRMATION = ("state", "summary")


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None and parsed.utcoffset() is not None
    except (ValueError, TypeError, AttributeError):
        return False


def validate(data):
    errors = []
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]
    if data.get("schemaVersion") != 1:
        errors.append("schemaVersion must equal 1")
    events = data.get("events")
    if not isinstance(events, list):
        return errors + ["events must be an array"]
    seen = {}
    for i, event in enumerate(events):
        label = f"events[{i}]"
        if not isinstance(event, dict):
            errors.append(f"{label}: must be an object")
            continue
        for field in REQUIRED:
            if field not in event:
                errors.append(f"{label}: missing {field}")
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            errors.append(f"{label}: id must be a nonempty string")
        elif event_id in seen:
            errors.append(f"{label}: duplicate id {event_id!r} (first at events[{seen[event_id]}])")
        else:
            seen[event_id] = i
        for field in ("category", "companyMarket", "headline", "source", "whyItMatters", "status"):
            if field in event and (not isinstance(event[field], str) or not event[field].strip()):
                errors.append(f"{label}: {field} must be a nonempty string")
        if "sourceUrl" in event and event["sourceUrl"] is not None and not isinstance(event["sourceUrl"], str):
            errors.append(f"{label}: sourceUrl must be a string or null")
        if "eventTime" in event and not timestamp(event["eventTime"]):
            errors.append(f"{label}: eventTime must be ISO-8601 with timezone")
        if "firstReported" in event:
            try:
                dt.date.fromisoformat(event["firstReported"])
            except (TypeError, ValueError):
                errors.append(f"{label}: firstReported must be YYYY-MM-DD")
        for key, fields in (("expectedImpact", IMPACT), ("marketConfirmation", CONFIRMATION)):
            obj = event.get(key)
            if not isinstance(obj, dict):
                errors.append(f"{label}: {key} must be an object")
                continue
            for field in fields:
                if field not in obj:
                    errors.append(f"{label}: {key}.{field} is required")
                elif not isinstance(obj[field], str) or not obj[field].strip():
                    errors.append(f"{label}: {key}.{field} must be a nonempty string")
        if "autoDetected" in event and not isinstance(event["autoDetected"], bool):
            errors.append(f"{label}: autoDetected must be boolean")
    return errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=DEFAULT)
    args = parser.parse_args()
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Open Watch validation FAILED: {exc}", file=sys.stderr)
        return 1
    errors = validate(data)
    if errors:
        print(f"Open Watch validation FAILED: {len(errors)} error(s)", file=sys.stderr)
        for error in errors[:60]:
            print(" - " + error, file=sys.stderr)
        return 1
    print(f"Open Watch validation OK: {len(data['events'])} events; IDs unique")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
