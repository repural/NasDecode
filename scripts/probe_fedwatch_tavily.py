#!/usr/bin/env python3
"""Hourly FedWatch Tavily source probe. Never treat undated search results as live market data."""
# A probe failure must never update published Fed expectations.
import datetime as dt
import json
import os
import re
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

CME_URL = "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html"
OUT = Path("data/research/fedwatch-tavily-probe.json")
NY = ZoneInfo("America/New_York")
HEADERS = {"Authorization": "Bearer " + os.environ.get("TAVILY_API_KEY", ""),
           "Content-Type": "application/json"}


def request(endpoint, payload):
    req = urllib.request.Request(
        "https://api.tavily.com/" + endpoint,
        data=json.dumps(payload).encode(),
        headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=75) as res:
        return json.load(res)


def parse_table(raw, today=None):
    """Only parse complete meeting rows aligned to a rate-range table header."""
    today = today or dt.datetime.now(NY).date()
    lines = raw.splitlines()
    header = None
    for index, line in enumerate(lines):
        normalized = re.sub(r"\s+", " ", line.strip().strip("|"))
        if re.search(r"MEETING DATE", normalized, re.I) and len(re.findall(r"\d{3,4}\s*[-–]\s*\d{3,4}", normalized)) >= 2:
            header = index
            break
    if header is None:
        return []
    ranges = re.findall(r"(\d{3,4})\s*[-–]\s*(\d{3,4})", lines[header])
    if len(ranges) < 2:
        return []
    rows = []
    for line in lines[header+1:header+22]:
        if re.fullmatch(r"\s*[\|\-\s:]+", line):
            continue
        cols = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(cols) != len(ranges)+1:
            continue
        try:
            day = dt.datetime.strptime(cols[0], "%m/%d/%Y").date()
            values = [float(re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*%\s*", p).group(1)) for p in cols[1:]]
        except (ValueError, AttributeError):
            continue
        if not 99.5 <= sum(values) <= 100.5 or any(not 0 <= v <= 100 for v in values):
            continue
        if day < today:
            continue
        rows.append({"date": day.isoformat(), "targetProbabilities":
                     {f"{lo}-{hi}": p for (lo,hi),p in zip(ranges,values)}})
    return rows


def main():
    now = dt.datetime.now(dt.timezone.utc)
    report = {"schemaVersion": 1, "collectedAtUTC": now.isoformat(),
              "provider": "Tavily extract/search", "primarySource": CME_URL,
              "status": "unverified", "meetings": [], "sources": [], "errors": [],
              "note": "An extraction timestamp is not a CME quote timestamp. Never promote undated extracted probabilities."}
    if not os.environ.get("TAVILY_API_KEY"):
        report["status"] = "missing_api_key"
    else:
        results = []
        try:
            extracted = request("extract", {"urls": [CME_URL], "extract_depth": "advanced",
                                          "format": "markdown", "include_images": False})
            results.extend(extracted.get("results") or [])
            report["errors"].extend(str(x.get("error", ""))[:250] for x in extracted.get("failed_results") or [])
        except Exception as exc:
            report["errors"].append(type(exc).__name__ + ": " + str(exc)[:180])
        # Search provides discovery diagnostics, never independently establishes a live quote time.
        if not any(parse_table(x.get("raw_content") or "") for x in results):
            try:
                found = request("search", {"query": "site:cmegroup.com CME FedWatch Tool aggregated meeting probabilities",
                                            "search_depth": "advanced", "include_raw_content": True,
                                            "max_results": 3, "include_domains": ["cmegroup.com"]})
                for item in found.get("results") or []:
                    results.append({"url": item.get("url"), "raw_content": item.get("raw_content") or item.get("content") or ""})
            except Exception as exc:
                report["errors"].append(type(exc).__name__ + ": " + str(exc)[:180])
        for source in results:
            url = source.get("url", "")
            if not str(url).startswith("https://www.cmegroup.com/"):
                continue
            raw = source.get("raw_content") or ""
            parsed = parse_table(raw)
            report["sources"].append({"url": url, "contentLength": len(raw),
                                      "aggregatedTableFound": bool(parsed),
                                      "meetingCount": len(parsed)})
            if parsed and not report["meetings"]:
                report["meetings"] = parsed
                report["status"] = "table_found_timestamp_unverified"
        if not report["meetings"] and report["status"] != "missing_api_key":
            report["status"] = "no_verified_table"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"status": report["status"], "meetings": len(report["meetings"]),
                      "sources": report["sources"], "errors": report["errors"]}))
    return report


if __name__ == "__main__":
    main()
