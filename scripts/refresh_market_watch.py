#!/usr/bin/env python3
"""Strict repository-side publisher for NasDecode Market Watch.

Raw discovery remains in data/semiconductor-catalysts.json. This script admits only
fresh, event-like, high-materiality candidates from credible sources into the
canonical curated archive at data/history/market-watch-events.json.
"""
import datetime as dt
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path

from market_watch_global import discover_global_candidates, GLOBAL_SOURCE_DOMAINS

ROOT = Path(__file__).resolve().parents[1]
CATALYST_PATH = ROOT / "data" / "semiconductor-catalysts.json"
HISTORY_PATH = ROOT / "data" / "history" / "market-watch-events.json"
ACTIVE_PATH = ROOT / "public" / "data" / "market-watch.json"
STATUS_PATH = ROOT / "data" / "research" / "market-watch-monitor-status.json"
TAVILY_URL = "https://api.tavily.com/search"

ACTIVE_DAYS = 4
MIN_SCORE = 8

TRUSTED_DOMAINS = {
    "reuters.com", "cnbc.com", "wsj.com", "ft.com", "bloomberg.com",
    "sec.gov", "federalreserve.gov", "bls.gov", "bea.gov", "treasury.gov",
    "iea.org", "eia.gov",
} | set(GLOBAL_SOURCE_DOMAINS)

# These are discovery noise, not discrete market-moving events.
REJECT_HEADLINE_PATTERNS = [
    r"better buy", r"should you buy", r"time to buy", r"stock price",
    r"quote and history", r"price target", r"stock forecast",
    r"moved (up|down) by", r"what investors need to know",
    r"what signal does it send", r"largest companies by market cap",
    r"expected to announce earnings", r"stocks making the biggest moves",
    r"what you can learn from", r"heads for \$?\d+ trillion",
    r"stock rises to new highs", r"stock tests all-time highs",
    r"\bvs\.?\b.*\b(which|better|contrasting)\b",
    r"etfs? to buy", r"job[s]?$", r"production engineer",
    r"live updates", r"latest news and analysis", r"latest .* market news",
    r"selected interest rates", r"\bh\.15\b", r"jim cramer",
    r"subindex", r"daily rates?", r"market wrap", r"market recap",
]

EVENT_TERMS = {
    "earnings", "reports", "reported", "guidance", "forecast", "outlook",
    "raises", "raised", "cuts", "cut", "buyback", "repurchase",
    "acquire", "acquires", "acquisition", "merger", "partnership",
    "contract", "deal", "agreement", "investment", "invests", "launch",
    "product", "order", "customer", "capacity", "production", "supply",
    "export", "restriction", "sanction", "license", "investigation",
    "lawsuit", "settlement", "ceo", "cfo", "resign", "appoint",
    "fed", "federal reserve", "treasury", "yield", "inflation", "cpi",
    "pce", "payroll", "unemployment", "jobs", "gdp", "oil", "brent",
    "wti", "opec", "iea", "war",
}

MACRO_SEARCHES = [
    ("fed-rates", "Federal Reserve Treasury yields rate hike rate cut Nasdaq"),
    ("macro", "US CPI PCE payrolls unemployment jobs inflation GDP Nasdaq"),
    ("oil-geopolitics", "Brent WTI IEA OPEC sanctions Middle East oil inflation Nasdaq"),
    ("regulatory", "US semiconductor export controls China AI chips restrictions sanctions"),
]


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def parse_datetime(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except ValueError:
        return None


def parse_date(value):
    parsed = parse_datetime(value)
    return parsed.date() if parsed else None


def date_from_url(url):
    m = re.search(r"\b(20\d{2})[-/](\d{2})[-/](\d{2})\b", url or "")
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def host(url):
    try:
        return urllib.parse.urlparse(url).hostname.lower().removeprefix("www.")
    except Exception:
        return ""


def trusted_source(url):
    h = host(url or "")
    return any(h == d or h.endswith("." + d) for d in TRUSTED_DOMAINS)


def rejected_headline(title):
    low = (title or "").strip().lower()
    return any(re.search(p, low, re.I) for p in REJECT_HEADLINE_PATTERNS)


def event_like(title):
    low = (title or "").lower()
    return any(term in low for term in EVENT_TERMS)


def category_title_match(category, title):
    low = (title or "").lower()
    patterns = {
        "fed-rates": r"\b(fed|federal reserve|treasur(?:y|ies)|yield|rate hike|rate cut|rates?)\b",
        "macro": r"\b(cpi|pce|payrolls?|unemployment|employment|jobs report|inflation|gdp|retail sales|ism|pmi)\b",
        "oil-geopolitics": r"\b(brent|wti|oil|opec|iea|iran|hormuz|sanction|energy supply|crude)\b",
        "regulatory": r"\b(export control|export restriction|chip restriction|semiconductor restriction|sanction|ban|license|ai chip|china chip)\b",
    }
    return bool(re.search(patterns.get(category, r".+"), low, re.I))


def event_action_match(title):
    low = (title or "").lower()
    return bool(re.search(
        r"\b(announce(?:s|d)?|agree(?:s|d)?|sign(?:s|ed)?|raise(?:s|d)?|cut(?:s)?|"
        r"acquire(?:s|d)?|report(?:s|ed)?|forecast(?:s|ed)?|warn(?:s|ed)?|"
        r"approve(?:s|d)?|restrict(?:s|ed)?|ban(?:s|ned)?|release(?:s|d)?|"
        r"rise(?:s|n)?|fall(?:s|en)?|surge(?:s|d)?|plunge(?:s|d)?|hit(?:s)?|"
        r"order(?:s|ed)?|launch(?:es|ed)?|invest(?:s|ed)?|investigation|sanction(?:s|ed)?|"
        r"minutes show|data show|payrolls|cpi|pce|unemployment)\b", low, re.I
    ))


def fresh(event_date):
    today = now_utc().date()
    return event_date is not None and dt.timedelta(days=0) <= (today - event_date) <= dt.timedelta(days=1)


def normalize_headline(text):
    text = re.sub(r"\s*[-|–—]\s*(Reuters|CNBC|WSJ|Bloomberg|FT).*?$", "", text or "", flags=re.I)
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def stable_id(date, ticker, title):
    base = f"{date.isoformat()}|{ticker}|{normalize_headline(title)}"
    digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "-", normalize_headline(title)).strip("-")[:44].rstrip("-")
    return f"{date.isoformat()}-{ticker.lower()}-{slug}-{digest}"


def tavily_search(query, max_results=8):
    key = os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY")
    if not key:
        return []
    payload = {
        "api_key": key,
        "query": query,
        "topic": "news",
        "search_depth": "advanced",
        "days": 1,
        "max_results": max_results,
        "include_answer": False,
        "include_raw_content": False,
        "include_domains": sorted(TRUSTED_DOMAINS),
    }
    req = urllib.request.Request(
        TAVILY_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "NasDecode/1.0"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.load(r).get("results", [])


def infer_direction(title):
    low = (title or "").lower()
    neg = ("cuts", "cut ", "restriction", "sanction", "investigation", "lawsuit",
           "delay", "warning", "misses", "miss ", "surge in yields", "higher yields",
           "hot inflation", "war", "attack")
    pos = ("raises", "raised", "wins", "launch", "buyback", "repurchase", "acquire",
           "partnership", "contract", "agreement", "beats", "beat ", "lower yields",
           "rate cut", "eases", "falls")
    has_neg = any(x in low for x in neg)
    has_pos = any(x in low for x in pos)
    if has_neg and not has_pos:
        return "Negative"
    if has_pos and not has_neg:
        return "Positive"
    return "Mixed"


def scope_for(candidate):
    if candidate.get("scope") == "macro":
        return "Nasdaq-wide macro"
    if candidate.get("scope") == "sector":
        return "Semiconductor sector"
    if candidate.get("scope") == "mega_cap":
        return "Mega-cap / Nasdaq"
    return "Single stock"


def company_market(candidate):
    if candidate.get("scope") == "macro":
        category = candidate.get("type")
        return {
            "fed-rates": "Federal Reserve / U.S. Treasuries / Nasdaq",
            "macro": "U.S. macro / Nasdaq",
            "oil-geopolitics": "Oil / Geopolitics / Nasdaq",
            "regulatory": "U.S. policy / Semiconductor sector",
        }.get(category, "Market / Nasdaq")
    return candidate.get("ticker") or "Market"


def materiality(score):
    return "Very High" if score >= 12 else "High"


def global_semantic_duplicate(candidate, events):
    """Deduplicate regional/global reports without hiding genuinely new escalation."""
    if candidate.get("type") != "global-semiconductor":
        return False
    c_markets = set(candidate.get("affectedMarkets") or [])
    c_type = candidate.get("eventType")
    c_transmission = candidate.get("transmissionType")
    c_date = candidate.get("date_obj")
    for event in events:
        if event.get("category") != "global-semiconductor":
            continue
        if parse_date(event.get("firstReported")) != c_date:
            continue
        if event.get("eventType") != c_type or event.get("transmissionType") != c_transmission:
            continue
        e_markets = set(event.get("affectedMarkets") or [])
        overlap = len(c_markets & e_markets)
        denom = max(1, min(len(c_markets), len(e_markets)))
        if overlap / denom >= 0.5:
            return True
    return False


def build_event(candidate):
    date = candidate["date_obj"]
    ticker = candidate.get("ticker") or "MARKET"
    title = candidate["title"].strip()
    is_macro = candidate.get("scope") == "macro"
    direction = infer_direction(title)
    published_dt = candidate.get("published_dt")
    event_time = published_dt.isoformat(timespec="seconds") if published_dt else f"{date.isoformat()}T00:00:00-04:00"
    expected_impact = {
        "stock": "Broad technology" if is_macro else ticker,
        "sox": "Negative" if candidate.get("type") == "global-semiconductor" and direction != "Positive" else "Potentially material",
        "nasdaq": "Negative" if candidate.get("type") == "global-semiconductor" and direction != "Positive" else "Potentially material",
        "scope": "Global semiconductor / Nasdaq" if candidate.get("type") == "global-semiconductor" else scope_for(candidate),
        "direction": "Negative" if candidate.get("type") == "global-semiconductor" and candidate.get("eventType") in {"regional-selloff", "global-selloff", "circuit-breaker"} else direction,
        "materiality": candidate.get("severity") or materiality(int(candidate.get("materialityScore") or MIN_SCORE)),
    }
    confirmation = {
        "state": "Unconfirmed",
        "summary": (
            "Asian/global semiconductor shock detected; awaiting U.S. SOX/QQQ confirmation."
            if candidate.get("type") == "global-semiconductor" else
            "Published by the strict GitHub Actions curation gate. Await QQQ, SOX, SMH/SOXX, breadth and persistence confirmation."
        ),
    }
    event = {
        "id": stable_id(date, ticker, title),
        "eventTime": event_time,
        "timePrecision": "exact" if published_dt else "date",
        "firstReported": date.isoformat(),
        "category": candidate.get("type") or "company_specific",
        "companyMarket": (
            "Global semiconductor markets / SOX / Nasdaq"
            if candidate.get("type") == "global-semiconductor" else company_market(candidate)
        ),
        "headline": title,
        "source": host(candidate["source"]) or "Credible source",
        "sourceUrl": candidate["source"],
        "whyItMatters": (
            "A material global semiconductor development can transmit into SOX, SOXL and Nasdaq through "
            "memory, foundry, equipment, AI-capex and risk-appetite channels."
            if candidate.get("type") == "global-semiconductor" else
            "Validated repository-side as a material macro/policy development capable of affecting "
            "Treasury yields, inflation expectations, semiconductor leadership or Nasdaq risk appetite."
            if is_macro else
            "Validated repository-side as a material company/semiconductor development with plausible "
            "read-through to the affected stock, SOX leadership or Nasdaq risk appetite."
        ),
        "expectedImpact": expected_impact,
        "marketConfirmation": confirmation,
        "status": "active",
        "autoDetected": False,
        "materialityScore": int(candidate.get("materialityScore") or MIN_SCORE),
        "firstDetectedAtUTC": candidate.get("discoveredAtUTC"),
        "observationTimeUTC": candidate.get("observationTimeUTC"),
        "confidence": candidate.get("confidence"),
        "informationNovelty": candidate.get("informationNovelty"),
        "initialAssessment": {
            "capturedAtUTC": candidate.get("discoveredAtUTC"),
            "expectedImpact": expected_impact.copy(),
            "marketConfirmation": confirmation.copy(),
        },
        "confirmationHistory": [],
    }
    if candidate.get("type") == "global-semiconductor":
        for field in (
            "eventType", "region", "affectedMarkets", "affectedEntities", "affectedTickers",
            "transmissionType", "severity", "observedMovesPct", "volatilityNormalized", "provenance",
        ):
            event[field] = candidate.get(field)
        if published_dt and candidate.get("discoveredAtUTC"):
            detected = parse_datetime(candidate.get("discoveredAtUTC"))
            event["retrospectivelyDiscovered"] = bool(detected and (detected - published_dt).total_seconds() > 7200)
        else:
            event["retrospectivelyDiscovered"] = False
    return event


def raw_company_candidates():
    data = load_json(CATALYST_PATH, {"events": []})
    for e in data.get("events") or []:
        score = int(e.get("materialityScore") or 0)
        date = parse_date(e.get("date"))
        title = str(e.get("title") or "").strip()
        source = str(e.get("source") or "").strip()
        if score < MIN_SCORE or not fresh(date):
            continue
        if not trusted_source(source) or rejected_headline(title) or not event_like(title) or not event_action_match(title):
            continue
        yield {
            **e,
            "date_obj": date,
            "published_dt": parse_datetime(e.get("published_date")),
            "title": title,
            "source": source,
        }


def macro_candidates():
    for category, query in MACRO_SEARCHES:
        try:
            results = tavily_search(query)
        except Exception as exc:
            print("macro search failed", category, type(exc).__name__, str(exc))
            continue
        for r in results:
            title = str(r.get("title") or "").strip()
            source = str(r.get("url") or "").strip()
            published_dt = parse_datetime(r.get("published_date"))
            date = published_dt.date() if published_dt else date_from_url(source)
            if date is None:
                continue
            if not fresh(date) or not trusted_source(source):
                continue
            if rejected_headline(title) or not event_like(title) or not category_title_match(category, title) or not event_action_match(title):
                continue
            yield {
                "date_obj": date,
                "published_dt": published_dt,
                "ticker": "MARKET",
                "type": category,
                "scope": "macro",
                "title": title,
                "source": source,
                "materialityScore": 10,
            }


def main():
    history = load_json(HISTORY_PATH, {
        "schemaVersion": 1,
        "updated": None,
        "description": "Curated history of material catalysts published by NasDecode Open Watch.",
        "events": [],
    })
    events = list(history.get("events") or [])

    existing_ids = {e.get("id") for e in events}
    existing_urls = {str(e.get("sourceUrl") or "").strip().lower() for e in events if e.get("sourceUrl")}
    existing_heads = {normalize_headline(e.get("headline")) for e in events if e.get("headline")}

    accepted = []
    seen_urls = set()
    seen_heads = set()

    global_candidates, global_diagnostics = discover_global_candidates(
        lambda query: tavily_search(query, max_results=10)
    )
    for c in global_candidates:
        c["date_obj"] = parse_date(c.get("published_date")) or parse_date(c.get("date"))
        c["published_dt"] = parse_datetime(c.get("published_date"))

    candidate_groups = [
        ("company", list(raw_company_candidates())),
        ("macro", list(macro_candidates())),
        ("global-semiconductor", global_candidates),
    ]
    acceptance = {"company": 0, "macro": 0, "global-semiconductor": 0, "duplicatesRejected": 0}
    for origin, group in candidate_groups:
        for c in group:
            url_key = c["source"].strip().lower()
            head_key = normalize_headline(c["title"])
            if url_key in existing_urls or head_key in existing_heads or global_semantic_duplicate(c, events):
                acceptance["duplicatesRejected"] += 1
                continue
            if url_key in seen_urls or head_key in seen_heads:
                acceptance["duplicatesRejected"] += 1
                continue
            accepted.append(c)
            acceptance[origin] += 1
            seen_urls.add(url_key)
            seen_heads.add(head_key)

    added = 0
    for c in accepted:
        e = build_event(c)
        if e["id"] in existing_ids:
            continue
        events.append(e)
        existing_ids.add(e["id"])
        added += 1

    # Age active events without deleting history.
    cutoff = now_utc().date() - dt.timedelta(days=ACTIVE_DAYS)
    for e in events:
        if e.get("status") != "active":
            continue
        d = parse_date(e.get("firstReported"))
        if d and d < cutoff:
            e["status"] = "historical"

    events.sort(key=lambda e: (str(e.get("firstReported") or ""), str(e.get("eventTime") or "")), reverse=True)
    history["schemaVersion"] = 1
    history["updated"] = now_utc().isoformat(timespec="seconds")
    history["description"] = (
        "Curated history of material catalysts published by NasDecode Open Watch. "
        "Repository-side GitHub Actions uses a strict freshness, source-quality and event-quality gate."
    )
    history["events"] = events
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(json.dumps(history, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    active = [e for e in events if e.get("status") == "active"]
    feed = {
        "schemaVersion": 1,
        "updated": history["updated"],
        "description": "Compact feed of currently active NasDecode Market Watch catalysts.",
        "activeEvents": [{
            "id": e["id"],
            "eventTime": e["eventTime"],
            "category": e["category"],
            "companyMarket": e["companyMarket"],
            "headline": e["headline"],
            "direction": e["expectedImpact"]["direction"],
            "materiality": e["expectedImpact"]["materiality"],
            "scope": e["expectedImpact"]["scope"],
            "marketConfirmation": e["marketConfirmation"]["state"],
            "whyItMatters": e["whyItMatters"],
        } for e in active[:20]],
    }
    ACTIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_PATH.write_text(json.dumps(feed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    status = {
        "schemaVersion": 1,
        "updated": history["updated"],
        "stage": "published" if added else "no-new-publication",
        "sourceRetrieval": global_diagnostics,
        "candidateAcceptance": acceptance,
        "acceptedForPublication": len(accepted),
        "newEventsPublished": added,
        "activeEvents": len(active),
        "totalEvents": len(events),
        "notes": {
            "sourceFailure": "See sourceRetrieval.searchesFailed/failures.",
            "noQualifyingEvents": bool(global_diagnostics["resultsReturned"] and not global_diagnostics["resultsQualified"]),
            "validation": "Performed by scripts/validate_open_watch.py in workflow.",
            "publication": "Git push result is determined by the workflow publish step.",
        },
    }
    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        f"strict Market Watch publisher: {added} new curated events; {len(active)} active; {len(events)} total; "
        f"global searches={global_diagnostics['searchesAttempted']} failed={global_diagnostics['searchesFailed']} "
        f"returned={global_diagnostics['resultsReturned']} qualified={global_diagnostics['resultsQualified']}"
    )


if __name__ == "__main__":
    main()
