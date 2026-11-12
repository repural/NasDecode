#!/usr/bin/env python3
"""NasDecode Resilience Engine — Phase 3.

Turns Phase 2 walk-forward SOX residuals into a point-in-time shadow resilience state.

No production score consumes this output.

Score architecture:
  60% Multi-horizon residual strength
      15% 1D, 25% 3D, 35% 5D, 25% 10D
  15% Residual persistence (positive residual share over last 10 model sessions)
  25% Internal semiconductor confirmation
      35% basket positive breadth
      35% basket outperform-Q Q Q breadth
      20% SOXX-vs-QQQ relative strength
      10% SMH-vs-QQQ relative strength

Residual horizons are standardized using ONLY residuals available before the evaluated
horizon, preventing future leakage in historical scores.

Sensitivities are diagnostics, not score inputs in v1.0. The engine also detects
resilience deterioration/breakdown from negative residual shocks plus confirmation.
"""
import json, math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MODEL=ROOT/"data"/"history"/"resilience-model.json"
HISTORY=ROOT/"data"/"history"/"resilience-daily.json"
OUT=ROOT/"data"/"history"/"resilience-engine.json"

HORIZON_WEIGHTS={1:.15,3:.25,5:.35,10:.25}
RESIDUAL_STRENGTH_WEIGHT=.60
PERSISTENCE_WEIGHT=.15
CONFIRMATION_WEIGHT=.25
BASELINE_WINDOW=60
MIN_BASELINE=20

def finite(x): return isinstance(x,(int,float)) and math.isfinite(x)
def clamp(x,lo=0,hi=100): return max(lo,min(hi,x))
def mean(xs): return sum(xs)/len(xs) if xs else None
def sample_sd(xs):
    if len(xs)<2:return None
    m=mean(xs); return math.sqrt(sum((x-m)**2 for x in xs)/(len(xs)-1))
def lerp(x,pts):
    pts=sorted(pts)
    if x<=pts[0][0]:return pts[0][1]
    if x>=pts[-1][0]:return pts[-1][1]
    for (x0,y0),(x1,y1) in zip(pts,pts[1:]):
        if x<=x1:return y0+(y1-y0)*(x-x0)/(x1-x0)
    return pts[-1][1]

# z=0 is neutral 50. +/-1 sigma is materially positive/negative; +/-2 is extreme.
def z_score_to_100(z): return round(clamp(50+22*z),1)

def breadth_score(v):
    if not finite(v): return None
    return round(lerp(v,[(0,0),(20,20),(40,40),(50,50),(60,65),(80,85),(100,100)]),1)

def rs_score(v):
    if not finite(v): return None
    return round(lerp(v,[(-2,0),(-1,20),(-.5,35),(0,50),(.5,65),(1,80),(2,100)]),1)

def weighted(parts):
    good=[(v,w) for v,w in parts if finite(v)]
    if not good:return None
    sw=sum(w for _,w in good)
    return sum(v*w for v,w in good)/sw if sw else None

def label(score):
    if score>=80:return "Exceptional"
    if score>=65:return "Strong"
    if score>=55:return "Positive"
    if score>=45:return "Neutral"
    if score>=35:return "Weakening"
    if score>=20:return "Weak"
    return "Broken"

def sensitivity_state(cur,history,key,scale=1.0):
    vals=[x.get("sensitivities",{}).get(key) for x in history if finite(x.get("sensitivities",{}).get(key))]
    if not finite(cur) or len(vals)<20:return {"value":cur,"state":"Insufficient history"}
    prior=vals[-60:]; m=mean(prior); sd=sample_sd(prior)
    z=(cur-m)/sd if sd and sd>1e-12 else 0
    return {"value":round(cur*scale,3),"priorMean":round(m*scale,3),
            "zVsPrior":round(z,2),
            "state":"High" if abs(z)>=1.25 else ("Elevated" if abs(z)>=.6 else "Stable")}

def main():
    model=json.loads(MODEL.read_text(encoding="utf-8"))
    hist=json.loads(HISTORY.read_text(encoding="utf-8"))
    market=hist.get("records") or {}
    preds=[{"date":d,**v} for d,v in sorted((model.get("records") or {}).items()) if v.get("status")=="predicted"]
    out={}; prior_scored=[]

    for i,p in enumerate(preds):
        d=p["date"]; residual=p.get("residualPct")
        if not finite(residual): continue
        horizons={}
        for h in HORIZON_WEIGHTS:
            if i+1<h:
                horizons[str(h)]={"available":False}; continue
            window=preds[i-h+1:i+1]
            vals=[x.get("residualPct") for x in window]
            if not all(finite(x) for x in vals):
                horizons[str(h)]={"available":False}; continue
            # Baseline ends before this evaluated horizon: strict point-in-time normalization.
            base=[x.get("residualPct") for x in preds[max(0,i-h-BASELINE_WINDOW+1):i-h+1]
                  if finite(x.get("residualPct"))]
            if len(base)<MIN_BASELINE:
                horizons[str(h)]={"available":False,"cumulativeResidualPct":round(sum(vals),4),
                                  "baselineSessions":len(base)}; continue
            sd=sample_sd(base)
            z=(sum(vals)-h*mean(base))/(sd*math.sqrt(h)) if sd and sd>1e-12 else 0
            horizons[str(h)]={"available":True,"cumulativeResidualPct":round(sum(vals),4),
                              "z":round(z,3),"score":z_score_to_100(z),
                              "positiveDays":sum(x>0 for x in vals),"sessions":h,
                              "baselineSessions":len(base)}

        residual_strength=weighted([(horizons[str(h)].get("score"),w) for h,w in HORIZON_WEIGHTS.items()])

        p10=preds[max(0,i-9):i+1]
        pos=sum(x.get("residualPct",0)>0 for x in p10)
        persistence_pct=100*pos/len(p10)
        persistence_score=round(lerp(persistence_pct,[(0,0),(30,25),(40,40),(50,50),(60,65),(70,80),(80,90),(100,100)]),1)

        mr=market.get(d) or {}; der=mr.get("derived") or {}
        bp=breadth_score(der.get("basketPositiveBreadthPct"))
        bo=breadth_score(der.get("basketOutperformQqqPct"))
        sx=rs_score(der.get("soxxVsQqqRelative1dPp"))
        sm=rs_score(der.get("smhVsQqqRelative1dPp"))
        confirmation=weighted([(bp,.35),(bo,.35),(sx,.20),(sm,.10)])
        confirmation=round(confirmation,1) if finite(confirmation) else None

        # Do not renormalize around a missing 60% core component during warm-up.
        # A published Resilience Score requires all four residual horizons plus confirmation.
        horizons_ready=all(horizons[str(h)].get("available") for h in HORIZON_WEIGHTS)
        score=None
        if horizons_ready and finite(residual_strength) and finite(confirmation):
            score=weighted([(residual_strength,RESIDUAL_STRENGTH_WEIGHT),
                            (persistence_score,PERSISTENCE_WEIGHT),
                            (confirmation,CONFIRMATION_WEIGHT)])
            score=round(score,1) if finite(score) else None

        # Breakdown logic: require actual negative abnormal response; confirmation controls severity.
        one=horizons["1"]; three=horizons["3"]; five=horizons["5"]
        one_z=one.get("z"); three_z=three.get("z"); five_z=five.get("z")
        breakdown="None"; reasons=[]
        if horizons_ready and finite(one_z) and one_z<=-1.5:
            reasons.append("1D residual <= -1.5σ")
        if horizons_ready and finite(three_z) and three_z<=-1.25:
            reasons.append("3D residual <= -1.25σ")
        if horizons_ready and finite(five_z) and five_z<=-1.0:
            reasons.append("5D residual <= -1.0σ")
        if horizons_ready and finite(confirmation) and confirmation<35:
            reasons.append("semiconductor confirmation <35")
        if horizons_ready and ((finite(one_z) and one_z<=-2.0) or
            ((finite(three_z) and three_z<=-1.5) and finite(confirmation) and confirmation<40) or
            ((finite(five_z) and five_z<=-1.25) and persistence_pct<=40)):
            breakdown="Breakdown"
        elif horizons_ready and reasons and ((finite(one_z) and one_z<=-1.5) or
                          (finite(three_z) and three_z<=-1.25) or
                          (finite(five_z) and five_z<=-1.0)):
            breakdown="Warning"

        prior_models=preds[:i]
        sens=p.get("sensitivities") or {}
        sensitivity={
            "qqqBeta":sensitivity_state(sens.get("qqqReturn1dPct"),prior_models,"qqqReturn1dPct",1),
            "parallelRatesPer10Bp":sensitivity_state(sens.get("ratesParallelShockBp"),prior_models,"ratesParallelShockBp",10),
            "steepeningPer10Bp":sensitivity_state(sens.get("curveSteepeningShockBp"),prior_models,"curveSteepeningShockBp",10),
            "vxnPer10PctMove":sensitivity_state(sens.get("vxnReturn1dPct"),prior_models,"vxnReturn1dPct",10),
            "brentPer5PctMove":sensitivity_state(sens.get("brentReturn1dPct"),prior_models,"brentReturn1dPct",5)
        }

        out[d]={
            "date":d,"score":score,"label":label(score) if finite(score) else "Warming up",
            "components":{
                "residualStrength":round(residual_strength,1) if finite(residual_strength) else None,
                "persistence":persistence_score,"internalConfirmation":confirmation
            },
            "weights":{"residualStrength":60,"persistence":15,"internalConfirmation":25},
            "residualHorizons":horizons,
            "persistence":{"positiveDays":pos,"sessions":len(p10),"positivePct":round(persistence_pct,1)},
            "confirmation":{
                "basketPositiveBreadthPct":der.get("basketPositiveBreadthPct"),"basketPositiveScore":bp,
                "basketOutperformQqqPct":der.get("basketOutperformQqqPct"),"basketOutperformScore":bo,
                "soxxVsQqqRelative1dPp":der.get("soxxVsQqqRelative1dPp"),"soxxRelativeScore":sx,
                "smhVsQqqRelative1dPp":der.get("smhVsQqqRelative1dPp"),"smhRelativeScore":sm
            },
            "breakdown":{"state":breakdown,"reasons":reasons},
            "sensitivityDiagnostics":sensitivity,
            "phase2":{"actualSoxReturnPct":p.get("actualSoxReturnPct"),
                      "expectedSoxReturnPct":p.get("expectedSoxReturnPct"),
                      "residualPct":p.get("residualPct"),"residualZ":p.get("residualZ")}
        }
        prior_scored.append(out[d])

    latest=out[max(out)] if out else None
    payload={
        "schemaVersion":1,"enginePhase":3,"engineVersion":"resilience-engine-1.1",
        "status":"shadow / validation only; no production NasDecode score consumes this output",
        "architecture":{
            "score":"60% multi-horizon residual strength + 15% persistence + 25% internal semiconductor confirmation",
            "residualStrength":"1D 15% + 3D 25% + 5D 35% + 10D 25%",
            "normalization":"Each historical horizon uses only residuals available before that horizon as its baseline. Score remains unpublished during warm-up until all four horizons and confirmation are available.",
            "persistence":"Positive Phase 2 residual share over last 10 model sessions.",
            "confirmation":"35% basket positive breadth + 35% basket outperform-QQQ breadth + 20% SOXX/QQQ RS + 10% SMH/QQQ RS.",
            "sensitivities":"Published as diagnostics only in v1.0; they do not receive score points.",
            "hype":"Hype Pressure remains separate context until Model B has sufficient prospective point-in-time history."
        },
        "labels":{"80-100":"Exceptional","65-79.9":"Strong","55-64.9":"Positive","45-54.9":"Neutral",
                  "35-44.9":"Weakening","20-34.9":"Weak","0-19.9":"Broken"},
        "latest":latest,"records":out
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Phase 3 sessions:",len(out))
    if latest:
        print("Latest",latest["date"],latest["score"],latest["label"],
              "breakdown",latest["breakdown"]["state"])
        print("Components",latest["components"])
        print("Horizons",latest["residualHorizons"])

if __name__=="__main__":
    main()
