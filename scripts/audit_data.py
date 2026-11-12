#!/usr/bin/env python3
"""Read-only inventory, catalog and quality audit of NasDecode's tracked JSON."""
import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATE = re.compile(r"^20\d{2}-\d{2}-\d{2}$")
KNOWN_RECORD_KEYS = ("records", "observations", "bars", "events", "features", "sessions", "series")
PUBLIC_ROOTS = ("public/data/", "public/history/")

def tracked_paths():
    result = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT)
    return sorted(p.decode() for p in result.split(b"\0") if p and p.decode().endswith(".json")
                  and p.decode().startswith(("data/",) + PUBLIC_ROOTS)
                  and not p.decode().startswith(("data/catalog/", "data/audits/")))

def sample_records(obj):
    if isinstance(obj, list):
        return obj, "array", None
    if not isinstance(obj, dict):
        return [], "scalar", None
    for key in KNOWN_RECORD_KEYS:
        value = obj.get(key)
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value, "array", key
        if isinstance(value, dict) and value and all(isinstance(v, dict) for v in value.values()):
            return list(value.values()), "map", key
    return [], "object", None

def classify(path, obj):
    if path.startswith(PUBLIC_ROOTS): return "publication"
    if path.startswith("data/research/"): return "research"
    if path.startswith("data/history/intraday/"): return "raw_intraday_history"
    if re.search(r"/(?:soxl|soxx)-daily\.json$", path): return "raw_price_bars"
    if path == "data/history/daily.json": return "historical_market_snapshot"
    if path.startswith("data/history/"):
        if any(s in path for s in ("backtest", "engine", "model", "validation", "research", "audit")):
            return "derived_model_or_research"
        return "historical_or_derived"
    return "current_state_or_configuration"

def tally(rows):
    seen = collections.Counter()
    missing = collections.Counter()
    types = collections.defaultdict(collections.Counter)
    dates = []
    duplicate_keys = collections.Counter()
    key_candidates = []
    if rows and all(isinstance(x, dict) for x in rows):
        for choice in (("date", "ticker"), ("date", "symbol"), ("tradingDate", "stage"),
                       ("date",), ("id",), ("eventTime", "id")):
            if all(all(k in r and r[k] is not None for k in choice) for r in rows[:min(len(rows), 20)]):
                key_candidates.append(choice)
    key = key_candidates[0] if key_candidates else None
    for row in rows:
        if not isinstance(row, dict): continue
        for k,v in row.items():
            seen[k] += 1
            if v is None or v == "": missing[k] += 1
            types[k][type(v).__name__] += 1
        for k in ("date", "tradingDate", "eventDate"):
            d = row.get(k)
            if isinstance(d, str) and DATE.fullmatch(d):
                dates.append(d); break
        if key:
            try: duplicate_keys[tuple(str(row[k]) for k in key)] += 1
            except KeyError: pass
    n = len(rows)
    fields = {k: {"present": count, "missingOrEmpty": n-count+missing[k],
                  "completenessPct": round(100*(count-missing[k])/n, 2) if n else None,
                  "types": dict(types[k])} for k,count in sorted(seen.items())}
    dup = sum(v-1 for v in duplicate_keys.values() if v>1)
    return {"recordCount":n, "fields":fields,
            "primaryKeyCandidate":list(key) if key else None,
            "duplicateKeyRows":dup,
            "dateRange":{"min":min(dates), "max":max(dates)} if dates else None}

def audit():
    entries = []
    reports = []
    for path in tracked_paths():
        file = ROOT/path
        size = file.stat().st_size
        sha = hashlib.sha256(file.read_bytes()).hexdigest()
        record = {"path":path,"bytes":size,"sha256":sha}
        try:
            obj = json.loads(file.read_text(encoding="utf-8"))
            rows, shape, container = sample_records(obj)
            # Nested session and date maps must be reported as inferred maps, not invented flattened records.
            role = classify(path,obj)
            record.update({"classification":role,"shape":shape,"recordContainer":container,
                           "schemaVersion":obj.get("schemaVersion") if isinstance(obj,dict) else None,
                           "topLevelFields":list(obj.keys()) if isinstance(obj,dict) else [],
                           "source":obj.get("source") if isinstance(obj,dict) and isinstance(obj.get("source"),str) else None})
            quality=tally(rows)
            record.update({"recordCount":quality["recordCount"],"primaryKeyCandidate":quality["primaryKeyCandidate"],
                           "fieldNames":list(quality["fields"].keys())})
            reports.append({"path":path,"classification":role,**quality})
        except (ValueError,UnicodeError) as exc:
            record["error"]=str(exc)[:300]
            reports.append({"path":path,"error":str(exc)[:300]})
        entries.append(record)
    hashes=collections.defaultdict(list)
    for x in entries: hashes[x["sha256"]].append(x["path"])
    copies=[v for v in hashes.values() if len(v)>1]
    totals=collections.Counter(e.get("classification","invalid") for e in entries)
    now=dt.datetime.now(dt.timezone.utc).isoformat()
    catalog={"schemaVersion":1,"generatedUTC":now,"scope":"tracked data/public JSON files; read-only",
             "datasets":entries}
    result={"schemaVersion":1,"generatedUTC":now,"files":len(entries),"totalBytes":sum(e["bytes"] for e in entries),
            "classificationCounts":dict(totals),"exactDuplicateGroups":copies,
            "checks":reports,
            "limitations":["Candidate record containers and keys are inferred and require review.",
                "Nested/map-based and non-standard datasets may have zero recognized records despite containing data.",
                "Field completeness refers to recognized records only; no cross-dataset semantic equivalence is asserted.",
                "No original records are modified."]}
    return catalog,result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",default="audit-output")
    args=ap.parse_args()
    catalog,result=audit()
    dest=pathlib.Path(args.output)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/"datasets.json").write_text(json.dumps(catalog,indent=2,ensure_ascii=False)+"\n")
    (dest/"latest.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    ranked=sorted(result["checks"],key=lambda x:x.get("duplicateKeyRows",0),reverse=True)
    lines=["# NasDecode record-level data audit","",f"Generated UTC: {result['generatedUTC']}",
           "",f"- JSON files: **{result['files']}**",f"- Current data size: **{result['totalBytes']:,} bytes**",
           f"- Exact identical-copy groups: **{len(result['exactDuplicateGroups'])}**","",
           "## Classification", "",
           "| Classification | Files |","|---|---:|"]
    lines += [f"| {k} | {v} |" for k,v in sorted(result["classificationCounts"].items())]
    lines += ["","## Record structure and duplicate keys","","| File | Recognized records | Candidate key | Duplicate key rows | Date range |",
              "|---|---:|---|---:|---|"]
    for row in ranked:
        span=row.get("dateRange") or {}
        lines.append(f"| `{row['path']}` | {row.get('recordCount','—')} | {', '.join(row.get('primaryKeyCandidate') or []) or 'not inferred'} | {row.get('duplicateKeyRows','—')} | {span.get('min','—')} → {span.get('max','—')} |")
    lines+=["","## Exact-copy groups",""]
    for group in result["exactDuplicateGroups"]:
        lines.append("- "+", ".join("`"+p+"`" for p in group))
    lines+=["","## Limitations",""]
    lines += ["- "+x for x in result["limitations"]]
    (dest/"report.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"files":result["files"],"bytes":result["totalBytes"],"copies":len(result["exactDuplicateGroups"]),"output":str(dest)}))
if __name__=="__main__": main()
