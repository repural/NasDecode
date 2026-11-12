#!/usr/bin/env python3
"""NasDecode Resilience Engine — Phase 2 walk-forward expected-SOX model.

Produces a strictly out-of-sample daily expectation for SOX using only information
from PRIOR sessions. This is a shadow model and does not change any production score.

Model A (macro baseline):
  SOX return = f(QQQ return, parallel rates shock, 10s-2s steepening shock, VXN return, Brent return)

Method:
- rolling 120 valid training sessions
- minimum 60 prior valid sessions before first prediction
- standardized ridge regression (lambda=5)
- feature scaling and coefficients fitted independently for every prediction date
- prediction-date observations are never included in that date's fit
- residual = actual SOX return - expected SOX return
- residual z-score uses PRIOR residuals only

Model B (macro + Hype) is deliberately NOT fitted until enough genuine point-in-time
Hype observations accumulate. Missing Hype history is never reconstructed from price.
"""
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/"data"/"history"/"resilience-daily.json"
OUT=ROOT/"data"/"history"/"resilience-model.json"

TRAIN_WINDOW=120
MIN_TRAIN=60
RIDGE_LAMBDA=5.0
RESIDUAL_Z_WINDOW=60
MIN_RESIDUAL_Z=20

FEATURES=[
    ("qqqReturn1dPct","QQQ daily return","pct"),
    ("ratesParallelShockBp","Parallel 2Y/10Y rate shock","bp"),
    ("curveSteepeningShockBp","10Y minus 2Y steepening shock","bp"),
    ("vxnReturn1dPct","VXN daily return","pct"),
    ("brentReturn1dPct","Brent daily return","pct"),
]

def finite(x):
    return isinstance(x,(int,float)) and math.isfinite(x)

def mean(xs): return sum(xs)/len(xs)

def sample_sd(xs):
    if len(xs)<2: return 0.0
    m=mean(xs)
    return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))

def solve(a,b):
    """Gaussian elimination with partial pivoting; small dense systems only."""
    n=len(b)
    m=[list(map(float,a[i]))+[float(b[i])] for i in range(n)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda r:abs(m[r][col]))
        if abs(m[pivot][col])<1e-12: return None
        m[col],m[pivot]=m[pivot],m[col]
        div=m[col][col]
        m[col]=[v/div for v in m[col]]
        for r in range(n):
            if r==col: continue
            fac=m[r][col]
            if fac:
                m[r]=[m[r][j]-fac*m[col][j] for j in range(n+1)]
    return [m[i][-1] for i in range(n)]

def feature_row(r):
    d=r.get("derived") or {}; m=r.get("macro") or {}
    y10=(m.get("US10Y") or {}).get("changeBp")
    y2=(m.get("US2Y") or {}).get("changeBp")
    parallel=(y10+y2)/2 if finite(y10) and finite(y2) else None
    steepening=y10-y2 if finite(y10) and finite(y2) else None
    return {
        "qqqReturn1dPct":d.get("qqqReturn1dPct"),
        "ratesParallelShockBp":parallel,
        "curveSteepeningShockBp":steepening,
        "vxnReturn1dPct":(m.get("VXN") or {}).get("return1dPct"),
        "brentReturn1dPct":(m.get("Brent") or {}).get("return1dPct"),
    }

def target(r): return (r.get("derived") or {}).get("soxReturn1dPct")

def valid_observation(r):
    x=feature_row(r); y=target(r)
    return finite(y) and all(finite(x[k]) for k,_,_ in FEATURES)

def fit_ridge(rows):
    keys=[k for k,_,_ in FEATURES]
    xs=[feature_row(r) for r in rows]; ys=[target(r) for r in rows]
    centers={k:mean([x[k] for x in xs]) for k in keys}
    scales={k:sample_sd([x[k] for x in xs]) for k in keys}
    if any(scales[k]<1e-12 for k in keys): return None
    z=[[ (x[k]-centers[k])/scales[k] for k in keys] for x in xs]
    ym=mean(ys); yc=[y-ym for y in ys]; p=len(keys)
    xtx=[[sum(row[i]*row[j] for row in z) for j in range(p)] for i in range(p)]
    xty=[sum(z[n][i]*yc[n] for n in range(len(z))) for i in range(p)]
    for i in range(p): xtx[i][i]+=RIDGE_LAMBDA
    beta=solve(xtx,xty)
    if beta is None: return None
    raw={k:beta[i]/scales[k] for i,k in enumerate(keys)}
    intercept=ym-sum(raw[k]*centers[k] for k in keys)
    return {"centers":centers,"scales":scales,"standardized":dict(zip(keys,beta)),
            "raw":raw,"intercept":intercept,"targetMean":ym}

def predict(model,r):
    x=feature_row(r)
    return model["intercept"]+sum(model["raw"][k]*x[k] for k,_,_ in FEATURES)

def metrics(rows):
    if not rows: return {}
    actual=[r["actualSoxReturnPct"] for r in rows]; pred=[r["expectedSoxReturnPct"] for r in rows]
    err=[a-p for a,p in zip(actual,pred)]
    mae=mean([abs(e) for e in err]); rmse=math.sqrt(mean([e*e for e in err]))
    am=mean(actual); sst=sum((a-am)**2 for a in actual); sse=sum(e*e for e in err)
    r2=1-sse/sst if sst>0 else None
    direction=sum((a>0)==(p>0) for a,p in zip(actual,pred))/len(rows)*100
    return {"observations":len(rows),"maePct":round(mae,4),"rmsePct":round(rmse,4),
            "outOfSampleR2":round(r2,4) if r2 is not None else None,
            "directionAccuracyPct":round(direction,1),"meanResidualPct":round(mean(err),4)}

def main():
    doc=json.loads(INPUT.read_text(encoding="utf-8"))
    records=doc.get("records") or {}; dates=sorted(records)
    valid_dates=[d for d in dates if valid_observation(records[d])]
    results={}; prior_residuals=[]

    for d in dates:
        r=records[d]
        if not valid_observation(r):
            results[d]={"status":"unavailable","reason":"Missing target or one/more baseline features."}
            continue
        prior=[pd for pd in valid_dates if pd<d]
        train_dates=prior[-TRAIN_WINDOW:]
        if len(train_dates)<MIN_TRAIN:
            results[d]={"status":"warming_up","validPriorSessions":len(train_dates),
                        "minimumRequired":MIN_TRAIN}
            continue
        model=fit_ridge([records[pd] for pd in train_dates])
        if model is None:
            results[d]={"status":"unavailable","reason":"Ridge fit failed."}; continue
        expected=predict(model,r); actual=target(r); residual=actual-expected
        z_hist=prior_residuals[-RESIDUAL_Z_WINDOW:]
        z=None
        if len(z_hist)>=MIN_RESIDUAL_Z:
            sd=sample_sd(z_hist)
            if sd>1e-12: z=(residual-mean(z_hist))/sd
        x=feature_row(r)
        contributions={k:round(model["raw"][k]*x[k],4) for k,_,_ in FEATURES}
        raw_coef={k:round(model["raw"][k],6) for k,_,_ in FEATURES}
        results[d]={
            "status":"predicted","model":"macroBaseline","trainStart":train_dates[0],
            "trainEnd":train_dates[-1],"trainingSessions":len(train_dates),
            "actualSoxReturnPct":round(actual,4),"expectedSoxReturnPct":round(expected,4),
            "residualPct":round(residual,4),"residualZ":round(z,3) if z is not None else None,
            "inputs":{k:round(x[k],4) for k,_,_ in FEATURES},
            "regimeContext":{
                "us10yLevelPct":(r.get("macro") or {}).get("US10Y",{}).get("close"),
                "us2yLevelPct":(r.get("macro") or {}).get("US2Y",{}).get("close"),
                "vxnLevel":(r.get("macro") or {}).get("VXN",{}).get("close"),
                "brentLevel":(r.get("macro") or {}).get("Brent",{}).get("close")
            },
            "featureContributionsPct":contributions,
            "sensitivities":raw_coef,
            "interceptPct":round(model["intercept"],4)
        }
        prior_residuals.append(residual)

    predicted=[{"date":d,**v} for d,v in results.items() if v.get("status")=="predicted"]
    latest=predicted[-1] if predicted else None
    # Current coefficient interpretation in natural market units.
    interpretation=None
    if latest:
        s=latest["sensitivities"]
        interpretation={
            "qqqBeta":round(s["qqqReturn1dPct"],3),
            "soxPctPer10BpParallelRates":round(s["ratesParallelShockBp"]*10,3),
            "soxPctPer10Bp10s2sSteepening":round(s["curveSteepeningShockBp"]*10,3),
            "soxPctPer10PctVxnMove":round(s["vxnReturn1dPct"]*10,3),
            "soxPctPer5PctBrentMove":round(s["brentReturn1dPct"]*5,3)
        }

    hype_days=sum(1 for d in dates if ((records[d].get("hype") or {}).get("provenance")=="prospective_point_in_time"))
    curated_hype_days=sum(1 for d in dates if (records[d].get("hype") or {}).get("candidateInputs"))
    payload={
        "schemaVersion":1,"enginePhase":2,"modelVersion":"resilience-phase2-ridge-1.1",
        "status":"shadow / validation only; no production NasDecode score consumes this output",
        "methodology":{
            "target":"SOX adjusted close-to-close daily return (%)",
            "features":[{"key":k,"label":label,"unit":unit} for k,label,unit in FEATURES],
            "training":"Walk-forward rolling ridge regression using prior valid sessions only.",
            "trainingWindowSessions":TRAIN_WINDOW,"minimumTrainingSessions":MIN_TRAIN,
            "ridgeLambda":RIDGE_LAMBDA,"standardization":"Training-window mean/sample SD only.",
            "residual":"Actual SOX return minus macro-baseline expected SOX return.",
            "residualZ":"Current residual standardized against up to 60 PRIOR model residuals only.",
            "rateTransform":"Parallel shock = (10Y bp change + 2Y bp change)/2; steepening shock = 10Y bp change - 2Y bp change. This reduces 2Y/10Y collinearity and makes rate sensitivity interpretable.",
            "important":"Same-day QQQ/macro changes make this a measured-response model, not a pre-open forecast."
        },
        "modelA":{
            "name":"Macro baseline","available":bool(predicted),
            "outOfSampleMetrics":metrics(predicted),
            "latest":latest,"latestSensitivityInterpretation":interpretation
        },
        "modelB":{
            "name":"Macro + Hype","available":False,"status":"collecting_point_in_time_hype_history",
            "candidateHypeDays":curated_hype_days,"prospectiveHypeDays":hype_days,
            "minimumProspectiveHypeDaysBeforeFit":60,
            "note":"Not fitted yet. Historical Hype is sparse and is not fabricated from future knowledge or price response."
        },
        "records":results
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Phase 2 predicted sessions:",len(predicted))
    if latest:
        print("Latest",latest["date"],"actual",latest["actualSoxReturnPct"],
              "expected",latest["expectedSoxReturnPct"],"residual",latest["residualPct"],
              "z",latest["residualZ"])
        print("OOS",payload["modelA"]["outOfSampleMetrics"])
        print("Sensitivity",interpretation)

if __name__=="__main__":
    main()
