#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALYST_PATH = ROOT / "data" / "semiconductor-catalysts.json"
HISTORY_PATH = ROOT / "history" / "market-watch-events.json"
ACTIVE_PATH = ROOT / "public" / "data" / "market-watch.json"

ACTIVE_DAYS = 4
HIGH_SCORE = 8
MEDIUM_HIGH_SCORE = 6


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def slugify(text, max_len=72):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].rstrip("-") or "event"


def stable_id(date, ticker, title):
    # Human-readable prefix plus a stable short digest prevents collisions while
    # remaining deterministic across repeated discovery runs.
    digest = hashlib.sha1(f"{date}|{ticker}|{title}".encode("utf-8")).hexdigest()[:8]
    return f"{date}-{ticker.lower()}-{slugify(title, 48)}-{digest}"


def materiality_label(score):
    if score >= HIGH_SCORE:
        return "High"
    if score >= MEDIUM_HIGH_SCORE:
        return "Medium-High"
    return "Medium"


def infer_direction(event):
    text = f"{event.get('title','')} {event.get('type','')}".lower()
    negative = ("cuts", "cut ", "restriction", "sanction", "investigation", "lawsuit", "delay", "warning", "miss", "down")
    positive = ("raises", "raise ", "wins", "launch", "buyback", "repurchase", "acquire", "partnership", "contract", "beats", "beat ", "up")
    if any(x in text for x in negative) and not any(x in text for x in positive):
        return "Negative"
    if any(x in text for x in positive) and not any(x in text for x in negative):
        return "Positive"
    return "Mixed"


def company_market(event):
    ticker = event.get("ticker") or "Market"
    title = event.get("title") or "Major catalyst"
    return f"{ticker} / {title[:96]}"


def expected_scope(event):
    scope = event.get("scope")
    if scope == "sector":
        return "Semiconductor sector"
    if scope == "mega_cap":
        return "Mega-cap / Nasdaq"
    return "Single stock"


def to_history_event(event):
    score = int(event.get("materialityScore") or 0)
    date = event.get("date") or dt.datetime.now(dt.timezone.utc).date().isoformat()
    ticker = event.get("ticker") or "MARKET"
    title = event.get("title") or "Major market catalyst"
    direction = infer_direction(event)
    scope = expected_scope(event)
    return {
        "id": stable_id(date, ticker, title),
        "eventTime": f"{date}T12:00:00-04:00",
        "firstReported": date,
        "category": event.get("type") or "company_specific",
        "companyMarket": company_market(event),
        "headline": title,
        "source": event.get("source") or None,
        "sourceUrl": event.get("source") or None,
        "whyItMatters": "Repository catalyst monitor classified this as a material event in the SOX/mega-cap universe. Market reaction must be verified before treating it as confirmed momentum.",
        "expectedImpact": {
            "stock": ticker,
            "sox": "Potentially material" if event.get("scope") == "sector" else "Indirect",
            "nasdaq": "Potentially material" if event.get("scope") in ("sector", "mega_cap") else "Limited",
            "scope": scope,
            "direction": direction,
            "materiality": materiality_label(score),
        },
        "marketConfirmation": {
            "state": "Unconfirmed",
            "summary": "Auto-persisted from the repository catalyst monitor. Await QQQ, SOX, SMH/SOXX, breadth and persistence confirmation.",
        },
        "status": "active",
        "autoDetected": True,
        "materialityScore": score,
        "discoveredAtUTC": event.get("discoveredAtUTC"),
    }


def active_projection(event):
    impact = event.get("expectedImpact") or {}
    conf = event.get("marketConfirmation") or {}
    return {
        "id": event.get("id"),
        "eventTime": event.get("eventTime"),
        "category": event.get("category"),
        "companyMarket": event.get("companyMarket"),
        "headline": event.get("headline"),
        "direction": impact.get("direction"),
        "materiality": impact.get("materiality"),
        "scope": impact.get("scope"),
        "marketConfirmation": conf.get("state"),
        "whyItMatters": event.get("whyItMatters"),
    }


def main():
    catalysts = load_json(CATALYST_PATH, {"events": []})
    history = load_json(HISTORY_PATH, {
        "schemaVersion": 1,
        "updated": None,
        "description": "Append-only history of material catalysts surfaced by the NasDecode Market Watch agent.",
        "events": [],
    })

    events = list(history.get("events") or [])
    by_id = {e.get("id"): e for e in events if e.get("id")}

    candidates = []
    for event in catalysts.get("events") or []:
        if not event.get("autoDetected"):
            continue
        score = int(event.get("materialityScore") or 0)
        if score < MEDIUM_HIGH_SCORE:
            continue
        candidates.append(event)

    added = 0
    for candidate in candidates:
        normalized = to_history_event(candidate)
        event_id = normalized["id"]
        if event_id in by_id:
            # Preserve curated fields/confirmation. Only refresh machine metadata.
            current = by_id[event_id]
            current["materialityScore"] = max(
                int(current.get("materialityScore") or 0),
                normalized["materialityScore"],
            )
            if normalized.get("discoveredAtUTC"):
                current["lastSeenUTC"] = normalized["discoveredAtUTC"]
            continue
        events.append(normalized)
        by_id[event_id] = normalized
        added += 1

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now.date() - dt.timedelta(days=ACTIVE_DAYS)

    # Age out only auto-detected active rows. Curated/manual lifecycle states remain authoritative.
    for event in events:
        if not event.get("autoDetected") or event.get("status") != "active":
            continue
        try:
            d = dt.date.fromisoformat(str(event.get("firstReported") or ""))
        except ValueError:
            continue
        if d < cutoff:
            event["status"] = "historical"

    events.sort(key=lambda e: (str(e.get("firstReported") or ""), str(e.get("eventTime") or "")), reverse=True)
    history["schemaVersion"] = int(history.get("schemaVersion") or 1)
    history["updated"] = now.isoformat(timespec="seconds")
    history["events"] = events
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    active = [e for e in events if e.get("status") == "active"]
    active.sort(key=lambda e: (
        1 if (e.get("expectedImpact") or {}).get("materiality") == "Very High" else 0,
        1 if (e.get("expectedImpact") or {}).get("materiality") == "High" else 0,
        str(e.get("eventTime") or ""),
    ), reverse=True)
    feed = {
        "schemaVersion": 1,
        "updated": now.isoformat(timespec="seconds"),
        "description": "Compact feed of currently active NasDecode Market Watch catalysts for UI and other apps. Full history is stored in history/market-watch-events.json.",
        "activeEvents": [active_projection(e) for e in active[:20]],
    }
    ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"market watch persistence: {added} added, {len(active)} active, {len(events)} total")


if __name__ == "__main__":
    main()
