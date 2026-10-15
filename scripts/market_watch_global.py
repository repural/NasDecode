#!/usr/bin/env python3
"""Global semiconductor intelligence helpers for NasDecode Market Watch.

This module is intentionally dependency-light so it can be unit tested without
network access. Discovery still uses the repository's Tavily integration; this
module classifies results, extracts observed moves, and applies materiality gates.
"""
from __future__ import annotations

import datetime as dt
import re
import urllib.parse
from email.utils import parsedate_to_datetime
from typing import Callable, Iterable

GLOBAL_SEARCHES = [
    ("South Korea", 'Samsung Electronics SK Hynix KOSPI KOSDAQ semiconductor chip selloff circuit breaker earnings guidance'),
    ("Taiwan", 'TSMC MediaTek TAIEX semiconductor chip selloff packaging foundry earnings guidance'),
    ("Japan", 'Tokyo Electron Advantest Renesas SCREEN Holdings Disco Nikkei TOPIX semiconductor chip selloff earnings guidance'),
    ("China", 'China semiconductor export controls sanctions chipmaking SMIC CXMT Huawei lithography memory restrictions'),
    ("Global", 'global semiconductor chip stocks selloff AI infrastructure debt supply chain export restrictions Asia Europe'),
]

GLOBAL_SOURCE_DOMAINS = {
    "reuters.com", "cnbc.com", "bloomberg.com", "wsj.com", "ft.com",
    "asia.nikkei.com", "nikkei.com", "digitimes.com",
    "tsmc.com", "samsung.com", "skhynix.com", "tel.com", "advantest.com",
}

ENTITY_MAP = {
    "samsung": ("Samsung Electronics", "South Korea", ["MU", "NVDA"]),
    "sk hynix": ("SK Hynix", "South Korea", ["MU", "NVDA"]),
    "kospi": ("KOSPI", "South Korea", []),
    "kosdaq": ("KOSDAQ", "South Korea", []),
    "tsmc": ("TSMC", "Taiwan", ["TSM", "NVDA", "AMD", "AVGO"]),
    "taiwan semiconductor": ("TSMC", "Taiwan", ["TSM", "NVDA", "AMD", "AVGO"]),
    "mediatek": ("MediaTek", "Taiwan", ["QCOM"]),
    "taiex": ("TAIEX", "Taiwan", []),
    "tokyo electron": ("Tokyo Electron", "Japan", ["AMAT", "LRCX", "KLAC"]),
    "advantest": ("Advantest", "Japan", ["TER"]),
    "renesas": ("Renesas", "Japan", ["NXPI", "ON"]),
    "screen holdings": ("SCREEN Holdings", "Japan", ["AMAT", "LRCX"]),
    "disco": ("Disco", "Japan", []),
    "nikkei": ("Nikkei 225", "Japan", []),
    "topix": ("TOPIX", "Japan", []),
    "smic": ("SMIC", "China", []),
    "cxmt": ("CXMT", "China", ["MU"]),
    "huawei": ("Huawei", "China", ["NVDA", "AMD"]),
}

SELL_WORDS = r"(?:fell|falls|falling|dropped|drops|slid|slides|slumped|slumps|plunged|plunges|tumbled|tumbles|down)"
RISE_WORDS = r"(?:rose|rises|rising|gained|gains|jumped|jumps|surged|surges|up)"
HARD_CATALYST = re.compile(
    r"\b(circuit breaker|trading halt|halted|export control|export restriction|sanction|"
    r"chip restriction|supply disruption|earthquake|fire|factory shutdown|production halt|"
    r"earnings|guidance|forecast|outlook|profit warning|government restriction|license)\b",
    re.I,
)
SECTOR_CONTEXT = re.compile(
    r"\b(semiconductor|chipmaker|chip stock|chip stocks|memory chip|foundry|ai chip|"
    r"technology stocks|tech stocks|lithography|wafer|packaging)\b",
    re.I,
)
SELL_CONTEXT = re.compile(
    r"\b(selloff|sell-off|rout|plunge|plunges|plunged|tumble|tumbles|tumbled|"
    r"slump|slumps|slumped|circuit breaker|trading halt)\b",
    re.I,
)


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def source_host(url: str) -> str:
    try:
        return (urllib.parse.urlparse(url).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def trusted_global_source(url: str) -> bool:
    h = source_host(url)
    return any(h == d or h.endswith("." + d) for d in GLOBAL_SOURCE_DOMAINS)


def parse_source_datetime(value):
    if not value:
        return None
    raw = str(value).strip()
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def rejected_global_headline(title: str) -> bool:
    low = (title or "").lower()
    patterns = (
        r"market talk", r"stock market news for", r"live updates",
        r"expected to report", r"earnings coming up", r"how should you play",
        r"stock forecast", r"what to expect",
    )
    return any(re.search(p, low, re.I) for p in patterns)


def extract_percent_moves(text: str) -> list[float]:
    """Extract explicitly reported directional percentage moves.

    Values are observations from source text, not inferred prices.
    """
    out: list[float] = []
    for m in re.finditer(rf"\b{SELL_WORDS}\s+(?:by\s+)?(?:more than\s+|over\s+|about\s+|nearly\s+|roughly\s+)?(\d+(?:\.\d+)?)\s*%", text or "", re.I):
        out.append(-float(m.group(1)))
    for m in re.finditer(rf"\b{RISE_WORDS}\s+(?:by\s+)?(?:more than\s+|over\s+|about\s+|nearly\s+|roughly\s+)?(\d+(?:\.\d+)?)\s*%", text or "", re.I):
        out.append(float(m.group(1)))
    return out


def move_is_material(move_pct: float, daily_vol_pct: float | None = None) -> bool:
    """Absolute safeguard plus optional volatility-normalized gate."""
    if move_pct <= -5.0 or move_pct >= 7.0:
        return True
    if daily_vol_pct and daily_vol_pct > 0:
        return abs(move_pct) / daily_vol_pct >= 2.5
    return False


def severity_from_moves(moves: Iterable[float], daily_vol_pct: float | None = None, market_count: int = 1) -> str | None:
    vals = list(moves)
    if not vals:
        return None
    normalized = max((abs(v) / daily_vol_pct for v in vals), default=0.0) if daily_vol_pct else None
    worst = min(vals)
    severe_count = sum(1 for v in vals if v <= -5.0)
    if worst <= -8.0 or severe_count >= 2 or (normalized is not None and normalized >= 4.0):
        return "Very High"
    if worst <= -5.0 or market_count >= 2 or (normalized is not None and normalized >= 2.5):
        return "High"
    if worst <= -3.0:
        return "Medium"
    return None


def affected_entities(text: str) -> tuple[list[str], list[str], list[str]]:
    low = (text or "").lower()
    entities, markets, tickers = [], [], []
    for needle, (name, market, reads) in ENTITY_MAP.items():
        if needle in low:
            if name not in entities:
                entities.append(name)
            if market not in markets:
                markets.append(market)
            for ticker in reads:
                if ticker not in tickers:
                    tickers.append(ticker)
    return entities, markets, tickers


def classify_transmission(text: str, markets: list[str]) -> str:
    low = (text or "").lower()
    us_link = any(p in low for p in (
        "overnight u.s.", "overnight us", "wall street", "nasdaq", "philadelphia semiconductor",
        "sox", "previous u.s. session", "u.s. selloff", "us selloff", "u.s. inflation",
        "higher-than-expected u.s. consumer inflation",
    ))
    global_link = any(p in low for p in ("global selloff", "globally", "worldwide", "across global markets"))
    asia_markets = [m for m in markets if m in {"South Korea", "Taiwan", "Japan", "China"}]
    if global_link or (us_link and len(set(asia_markets)) >= 2):
        return "globally-synchronized"
    if us_link:
        return "us-led-spillover"
    if asia_markets:
        return "asia-originated"
    return "global-external"


def event_type_for(text: str, transmission: str) -> str:
    low = (text or "").lower()
    if "circuit breaker" in low or "trading halt" in low or "halted" in low:
        return "circuit-breaker"
    if re.search(r"\b(export control|export restriction|sanction|chip restriction|license restriction)\b", low):
        return "export-restriction"
    if re.search(r"\b(earnings|guidance|forecast|outlook|profit warning)\b", low):
        return "earnings-guidance"
    if re.search(r"\b(supply disruption|factory shutdown|production halt|earthquake|fire)\b", low):
        return "supply-chain-disruption"
    if SELL_CONTEXT.search(low):
        return "global-selloff" if transmission == "globally-synchronized" else "regional-selloff"
    return "global-semiconductor-catalyst"


def qualify_global_result(region: str, result: dict, discovered_at: dt.datetime | None = None) -> dict | None:
    title = str(result.get("title") or "").strip()
    content = str(result.get("content") or "").strip()
    source = str(result.get("url") or "").strip()
    text = f"{title} {content}".strip()
    if not title or not source or not trusted_global_source(source) or rejected_global_headline(title):
        return None
    entities, markets, tickers = affected_entities(text)
    if region not in ("Global", "") and region not in markets:
        markets.append(region)
    semiconductor_context = bool(SECTOR_CONTEXT.search(text) or entities)
    if not semiconductor_context:
        return None

    published_raw = result.get("published_date")
    published_dt = parse_source_datetime(published_raw)
    observed = discovered_at or now_utc()
    if published_dt:
        age = observed.date() - published_dt.date()
        if age < dt.timedelta(days=0) or age > dt.timedelta(days=1):
            return None

    moves = extract_percent_moves(text)
    transmission = classify_transmission(text, markets)
    etype = event_type_for(text, transmission)
    hard = bool(HARD_CATALYST.search(text))
    selloff = bool(SELL_CONTEXT.search(text))
    severity = severity_from_moves(moves, market_count=max(1, len(set(markets))))

    # Routine market movement is deliberately rejected. A qualifying record must
    # have a hard catalyst or a broad/severe semiconductor selloff signal.
    if not hard and not selloff:
        return None
    if selloff and not hard and severity not in {"High", "Very High"}:
        return None

    score = 8
    if severity == "Very High":
        score += 4
    elif severity == "High":
        score += 2
    if len(set(markets)) >= 2:
        score += 2
    if etype == "circuit-breaker":
        score += 3
    if etype in {"export-restriction", "supply-chain-disruption", "earnings-guidance"}:
        score += 2
    if transmission == "globally-synchronized":
        score += 2

    published = published_dt.isoformat(timespec="seconds") if published_dt else None
    confidence = "High" if moves or hard else "Medium"
    return {
        "date": (published_dt.date() if published_dt else observed.date()).isoformat(),
        "release": "during_session",
        "ticker": "MARKET",
        "type": "global-semiconductor",
        "scope": "sector",
        "title": title[:220],
        "expectedReadThrough": "Global semiconductor event; evaluate SOX/Nasdaq transmission and U.S. confirmation.",
        "source": source,
        "autoDetected": True,
        "materialityScore": score,
        "materialityReasons": ["global-semiconductor", etype, transmission],
        "discoveredAtUTC": observed.isoformat(timespec="seconds"),
        "published_date": published,
        "eventType": etype,
        "region": "Asia" if any(m in {"South Korea", "Taiwan", "Japan", "China"} for m in markets) else region,
        "affectedMarkets": sorted(set(markets)),
        "affectedEntities": entities,
        "affectedTickers": tickers,
        "transmissionType": transmission,
        "severity": severity or ("High" if hard else "Medium"),
        "observedMovesPct": moves,
        "volatilityNormalized": None,
        "observationTimeUTC": published,
        "confidence": confidence,
        "informationNovelty": "New candidate; publisher deduplication required",
        "provenance": [{
            "sourceUrl": source,
            "headline": title,
            "publishedDate": published,
            "retrievedAtUTC": observed.isoformat(timespec="seconds"),
        }],
    }


def discover_global_candidates(search_fn: Callable[[str], list[dict]], discovered_at: dt.datetime | None = None):
    """Run bounded global searches and return candidates plus operational diagnostics."""
    when = discovered_at or now_utc()
    candidates: list[dict] = []
    diagnostics = {
        "searchesAttempted": 0,
        "searchesFailed": 0,
        "resultsReturned": 0,
        "resultsQualified": 0,
        "resultsRejected": 0,
        "failures": [],
    }
    for region, query in GLOBAL_SEARCHES:
        diagnostics["searchesAttempted"] += 1
        try:
            results = search_fn(query) or []
        except Exception as exc:
            diagnostics["searchesFailed"] += 1
            diagnostics["failures"].append({"region": region, "error": f"{type(exc).__name__}: {exc}"})
            continue
        diagnostics["resultsReturned"] += len(results)
        for result in results:
            candidate = qualify_global_result(region, result, discovered_at=when)
            if candidate:
                candidates.append(candidate)
                diagnostics["resultsQualified"] += 1
            else:
                diagnostics["resultsRejected"] += 1
    return candidates, diagnostics
