"""Collect a lightweight Brent/WTI quote snapshot without changing engine signals."""
import datetime as dt
import json
import math
import os
import pathlib
import re
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEST = ROOT / "public" / "data" / "live-oil.json"
SYMBOLS = {"brent": "@LCO.1", "wti": "@CL.1"}
BASE = "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol"


def finite_number(raw):
    if raw is None:
        return None
    try:
        value = float(str(raw).replace(",", "").replace("%", "").replace("$", "").strip())
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def change_percent(quote):
    raw = quote.get("change_pct")
    if isinstance(raw, str) and re.fullmatch(r"\s*(UNCH|UNCHANGED|UNCHG|0+(?:\.0+)?%?)\s*", raw, re.I):
        return 0.0
    parsed = finite_number(raw)
    if parsed is not None:
        return parsed
    price = finite_number(quote.get("last"))
    previous = finite_number(quote.get("previous_day_closing"))
    if price is not None and previous not in (None, 0):
        return (price / previous - 1) * 100
    return None


def parse_timestamp(raw):
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(str(raw)).astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def fetch_quotes():
    params = {
        "symbols": "|".join(SYMBOLS.values()), "requestMethod": "itv",
        "noform": "1", "partnerId": "2", "fund": "1",
        "exthrs": "1", "output": "json", "events": "1",
    }
    url = BASE + "?" + urllib.parse.urlencode(params, safe="|@.")
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json,text/plain,*/*",
        "Referer": "https://www.cnbc.com/",
    })
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    result = payload.get("FormattedQuoteResult", {}).get("FormattedQuote", [])
    if isinstance(result, dict):
        result = [result]
    return {q.get("symbol"): q for q in result if q.get("code") == 0}


def build_snapshot(quotes, collected_at=None):
    now = collected_at or dt.datetime.now(dt.timezone.utc)
    result = {"schemaVersion": 1, "provider": "CNBC quote feed",
              "collectedAt": now.isoformat(), "quotes": {}}
    for label, symbol in SYMBOLS.items():
        quote = quotes.get(symbol) or {}
        price = finite_number(quote.get("last"))
        quote_dt = parse_timestamp(quote.get("last_time"))
        # Never republish a stale/undated quote as a current live value.
        if price is None or price <= 0 or quote_dt is None:
            continue
        age_seconds = (now - quote_dt).total_seconds()
        if age_seconds < -120 or age_seconds > 900:
            continue
        result["quotes"][label] = {
            "symbol": symbol, "price": price, "changePct": change_percent(quote),
            "quoteTime": quote_dt.isoformat(), "ageSecondsAtCollection": round(age_seconds),
        }
    return result


def main():
    snapshot = build_snapshot(fetch_quotes())
    if not snapshot["quotes"]:
        raise SystemExit("No current, valid oil quotes: previous published snapshot unchanged")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = DEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, DEST)
    print("Live oil quote snapshot:", json.dumps(snapshot))


if __name__ == "__main__":
    main()
