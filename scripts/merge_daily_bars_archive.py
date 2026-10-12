"""Reconcile independently collected daily bars with a concurrent dashboard writer.

Usage: python -m scripts.merge_daily_bars_archive /tmp/archive-bars
The archive directory contains captured data/history/*.json from the finished job.
"""
import json
import sys
from pathlib import Path

HISTORY=Path("data/history")
FIELDS=("date","open","high","low","close","volume","vwap","sma20","sma50",
        "sma20Source","sma50Source","sma20ValidationStatus","sma50ValidationStatus")

def load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError,ValueError):
        return None

def reconcile(current,collected):
    if not current:
        return collected
    if not collected:
        return current
    cur_time=str(current.get("updatedET") or "")
    new_time=str(collected.get("updatedET") or "")
    prefer_collected=new_time>=cur_time
    old={b["date"]:dict(b) for b in current.get("bars",[]) if isinstance(b,dict) and b.get("date")}
    for rec in collected.get("bars",[]):
        if not isinstance(rec,dict) or not rec.get("date"):
            continue
        date=rec["date"]
        if date not in old:
            old[date]=dict(rec)
            continue
        merged=old[date]
        for key,value in rec.items():
            if key=="date" or value is None:
                continue
            if prefer_collected or merged.get(key) is None:
                merged[key]=value
        old[date]=merged
    doc=dict(current)
    for key,value in collected.items():
        if key!="bars" and (prefer_collected or key not in doc):
            doc[key]=value
    doc["updatedET"]=max(cur_time,new_time)
    doc["bars"]=[old[date] for date in sorted(old)]
    return doc

def merge_directory(captured,current_dir=HISTORY):
    captured=Path(captured)
    current_dir=Path(current_dir)
    current_dir.mkdir(parents=True,exist_ok=True)
    merged_files=[]
    for source in sorted(captured.glob("*-daily.json")):
        destination=current_dir/source.name
        data=reconcile(load(destination),load(source))
        if data is None:
            continue
        destination.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        merged_files.append(destination.name)
    manifest_source=captured/"daily-bars-coverage.json"
    manifest_target=current_dir/"daily-bars-coverage.json"
    fresh=load(manifest_source)
    prior=load(manifest_target)
    if fresh:
        # Keep the most recently collected coverage manifest. Merge ticker entries
        # so independent partial collections don't discard earlier diagnostics.
        merged=dict(prior or {})
        if str(fresh.get("asOfET",""))>=str((prior or {}).get("asOfET","")):
            merged.update({k:v for k,v in fresh.items() if k!="tickers"})
        merged["tickers"]={**(prior or {}).get("tickers",{}),**fresh.get("tickers",{})}
        manifest_target.write_text(json.dumps(merged,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Reconciled",len(merged_files),"historical bar files",flush=True)

if __name__=="__main__":
    if len(sys.argv)!=2:
        raise SystemExit("Pass path to captured archive")
    merge_directory(sys.argv[1])
