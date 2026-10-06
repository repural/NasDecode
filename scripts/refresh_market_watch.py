#!/usr/bin/env python3
import datetime as dt
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALYST_PATH = ROOT / "data" / "semiconductor-catalysts.json"
HISTORY_PATH = ROOT / "data" / "history" / "market-watch-events.json"
ACTIVE_PATH = ROOT / "public" / "data" / "market-watch.json"
TAVILY_URL = "https://api.tavily.com/search"

ACTIVE_DAYS = 4
HIGH_SCORE = 8
MEDIUM_HIGH_SCORE = 6
TRUSTED_DOMAINS = (
    "reuters.com", "bloomberg.com", "cnbc.com", "wsj.com", "ft.com",
    "marketwatch.com", "federalreserve.gov", "bls.gov", "bea.gov",
    "treasury.gov", "iea.org", "eia.gov",
)
MACRO_QUERIES = (
    (
        "fed-rates",
        'Federal Reserve Treasury yields rate hike rate cut inflation Nasdaq Reuters',
        ("federal reserve", "fed ", "treasury", "yield", "rate hike", "rate cut"),
    ),
    (
        "macro",
        'US CPI PCE payrolls unemployment jobs inflation growth Nasdaq Reuters',
        ("cpi", "pce", "payroll", "unemployment", "employment", "jobs", "inflation", "gdp"),
    ),
    (
        "oil-geopolitics",
        'oil Brent WTI IEA OPEC sanctions Middle East geopolitical inflation Nasdaq Reuters',
        ("brent", "wti", "oil", "iea", "opec", "sanction", "middle east", "iran"),
    ),
    (
        "regulatory",
        'US semiconductor export controls China AI chips restrictions sanctions Reuters',
        ("export control", "chip restriction", "semiconductor restriction", "sanction", "china chips", "ai chips"),
    ),
)


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return default


def tavily_search(query, days=2, max_results=10):
    key = os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")
    if not key:
        return []
    payload = json.dumps({
        "api_key": key,
        "query": query,
        "topic": "news",
        "search_depth": "advanced",
        "days": days,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
    }).encode()
    req = urllib.request.Request(
        TAVILY_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "NasDecode/1.0"},
    )
    with urllib.request.urlopen(req, timeout=45) as response:
        return json.load(response).get("results", [])


def slugify(text, max_len=72):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].rstrip("-") or "event"


def stable_id(date, ticker, title):
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
    negative = (
        "cuts", "cut ", "restriction", "sanction", "investigation", "lawsuit",
        "delay", "warning", "miss", "surge in yields", "higher yields", "hot inflation",
    )
    positive = (
        "raises", "raise ", "wins", "launch", "buyback", "repurchase", "acquire",
        "partnership", "contract", "beats", "beat ", "lower yields", "rate cut",
    )
    if any(x in text for x in negative) and not any(x in text for x in positive):
        return "Negative"
    if any(x in text for x in positive) and not any(x in text for x in negative):
        return "Positive"
    return "Mixed"


def normalize_date(value):
    if not value:
        return dt.datetime.now(dt.timezone.utc).date().isoformat()
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return dt.datetime.now(dt.timezone.utc).date().isoformat()


def trusted(url):
    low = (url or "").lower()
    return any(domain in low for domain in TRUSTED_DOMAINS)


def macro_score(title, content, url, required_terms):
    text = f"{title} {content}".lower()
    title_low = (title or "").lower()
    score = 0
    if any(term in title_low for term in required_terms):
        score += 4
    elif any(term in text for term in required_terms):
        score += 2
    if trusted(url):
        score += 3
    for term, weight in (
        ("surge", 2), ("plunge", 2), ("record", 2), ("emergency", 3),
        ("unexpected", 2), ("unexpectedly", 2), ("hike", 2), ("cut", 2),
        ("sanction", 3), ("restriction", 3), ("release", 2), ("war", 3),
    ):
        if term in title_low:
            score += weight
    return score


def discover_macro_events():
    discovered = []
    for category, query, required_terms in MACRO_QUERIES:
        try:
            results = tavily_search(query)
        except Exception as exc:
            print("macro Tavily search failed", category, type(exc).__name__, str(exc))
            continue
        for result in results:
            title = str(result.get("title") or "").strip()
            content = str(result.get("content") or "").strip()
            url = str(result.get("url") or "").strip()
            score = macro_score(title, content, url, required_terms)
            if score < MEDIUM_HIGH_SCORE:
                continue
            discovered.append({
                "date": normalize_date(result.get("published_date")),
                "ticker": "MARKET",
                "type": category,
                "scope": "macro",
                "title": title[:180],
                "source": url,
                "autoDetected": True,
                "materialityScore": score,
                "discoveredAtUTC": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            })
    return discovered


def company_market(event):
    ticker = event.get("ticker") or "Market"
    if ticker == "MARKET":
        mapping = {
            "fed-rates": "Federal Reserve / U.S. Treasuries / Nasdaq",
            "macro": "U.S. macro / Nasdaq",
            "oil-geopolitics": "Oil / Geopolitics / Nasdaq",
            "regulatory": "U.S. policy / Semiconductor sector",
        }
        return mapping.get(event.get("type"), "Market / Nasdaq")
    title = event.get("title") or "Major catalyst"
    return f"{ticker} / {title[:96]}"


def expected_scope(event):
    scope = event.get("scope")
    if scope == "sector":
        return "Semiconductor sector"
    if scope == "mega_cap":
        return "Mega-cap / Nasdaq"
    if scope == "macro":
        return "Nasdaq-wide macro"
    return "Single stock"


def why_it_matters(event):
    if event.get("scope") == "macro":
        return "Repository Market Watch classified this as a material macro/policy catalyst capable of affecting yields, inflation expectations, semiconductor leadership or Nasdaq risk appetite. Market reaction must be verified before treating it as confirmed momentum."
    return "Repository catalyst monitor classified this as a material event in the SOX/mega-cap universe. Market reaction must be verified before treating it as confirmed momentum."


def to_history_event(event):
    score = int(event.get("materialityScore") or 0)
    date = event.get("date") or dt.datetime.now(dt.timezone.utc).date().isoformat()
    ticker = event.get("ticker") or "MARKET"
    title = event.get("title") or "Major market catalyst"
    direction = infer_direction(event)
    scope = expected_scope(event)
    is_macro = event.get("scope") == "macro"
    return {
        "id": stable_id(date, ticker, title),
        "eventTime": f"{date}T12:00:00-04:00",
        "firstReported": date,
        "category": event.get("type") or "company_specific",
        "companyMarket": company_market(event),
        "headline": title,
        "source": event.get("source") or None,
        "sourceUrl": event.get("source") or None,
        "whyItMatters": why_it_matters(event),
        "expectedImpact": {
            "stock": "Broad technology" if is_macro else ticker,
            "sox": "Potentially material",
            "nasdaq": "Potentially material",
            "scope": scope,
            "direction": direction,
            "materiality": materiality_label(score),
        },
        "marketConfirmation": {
            "state": "Unconfirmed",
            "summary": "Auto-persisted by the repository Market Watch. Await QQQ, SOX, SMH/SOXX, breadth and persistence confirmation.",
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
    candidates.extend(discover_macro_events())

    added = 0
    for candidate in candidates:
        normalized = to_history_event(candidate)
        event_id = normalized["id"]
        if event_id in by_id:
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
