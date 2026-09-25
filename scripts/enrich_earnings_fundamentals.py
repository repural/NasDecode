#!/usr/bin/env python3
"""Enrich NasBoard historical earnings events with Tavily-sourced fundamentals.

Research aid, not a blind scraper: uses separate pre-event consensus, reported-results,
and guidance searches; preserves provenance; only auto-accepts values explicitly parsed
from high-confidence snippets. Ambiguous values remain null for later review.
"""
import datetime,json,os,re,time,urllib.request,urllib.error
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES=[os.path.join(ROOT,'data','history','earnings_leadup_analysis.json'),os.path.join(ROOT,'data','history','megacap_earnings_analysis.json')]
API='https://api.tavily.com/search'
DOMAINS=['reuters.com','finance.yahoo.com','cnbc.com','investor.nvidia.com','investors.micron.com','microsoft.com','apple.com','amazon.com','abc.xyz','investor.fb.com','ir.amd.com','broadcom.com','investor.tsmc.com','ir.tesla.com']
def search(q,start=None,end=None):
 key=os.environ.get('TAVILY_KEY','').strip()
 if not key: raise RuntimeError('TAVILY_KEY missing')
 p={'query':q,'topic':'finance','search_depth':'advanced','max_results':8,'include_answer':False,'include_raw_content':False,'include_domains':DOMAINS}
 if start:p['start_date']=start
 if end:p['end_date']=end
 req=urllib.request.Request(API,data=json.dumps(p).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','User-Agent':'NasBoard/1.0'},method='POST')
 with urllib.request.urlopen(req,timeout=60) as r:return json.load(r).get('results',[])
def refs(rs):
 return [{'title':x.get('title'),'url':x.get('url'),'publishedDate':x.get('published_date'),'score':x.get('score'),'excerpt':x.get('content')} for x in rs[:8]]
def money(s):
 s=s.replace(',','').strip(); mult=1
 if s[-1:].lower()=='b':mult=1e9;s=s[:-1]
 elif s[-1:].lower()=='m':mult=1e6;s=s[:-1]
 try:return float(s)*mult
 except:return None
def candidates(rs,kind):
 out=[]
 pats={
 'eps_estimate':[r'(?:consensus|estimate(?:d)?|expected)[^.$]{0,80}(?:EPS|earnings per share)[^$]{0,30}\$?(-?\d+(?:\.\d+)?)',r'(?:EPS|earnings per share)[^$]{0,50}(?:consensus|estimate(?:d)?|expected)[^$]{0,30}\$?(-?\d+(?:\.\d+)?)'],
 'eps_actual':[r'(?:reported|posted|earned|adjusted EPS|EPS)[^$]{0,40}\$(-?\d+(?:\.\d+)?)'],
 'rev_estimate':[r'(?:consensus|estimate(?:d)?|expected)[^$]{0,80}(?:revenue|sales)[^$]{0,30}\$([\d,.]+\s*[BM]?)',r'(?:revenue|sales)[^$]{0,50}(?:consensus|estimate(?:d)?|expected)[^$]{0,30}\$([\d,.]+\s*[BM]?)'],
 'rev_actual':[r'(?:reported|posted|revenue|sales)[^$]{0,40}\$([\d,.]+\s*[BM]?)']}
 for x in rs:
  txt=x.get('content') or ''
  for p in pats[kind]:
   m=re.search(p,txt,re.I)
   if m:
    v=money(m.group(1)) if kind.startswith('rev') else float(m.group(1))
    if v is not None:out.append({'value':v,'url':x.get('url'),'title':x.get('title'),'score':x.get('score')});break
 return out
def choose(cs):
 if not cs:return None,'insufficient'
 # Require two independently returned pages agreeing within tolerance.
 for i,a in enumerate(cs):
  agree=[b for j,b in enumerate(cs) if j!=i and abs(b['value']-a['value'])<=max(abs(a['value'])*0.015,0.01)]
  if agree:return a['value'],'high' if len(agree)>=2 else 'medium'
 return None,'insufficient'
def enrich(ev,ticker):
 d=datetime.date.fromisoformat(ev['earningsDate']); pre_end=(d-datetime.timedelta(days=1)).isoformat(); pre_start=(d-datetime.timedelta(days=21)).isoformat(); post_end=(d+datetime.timedelta(days=4)).isoformat()
 pre=search(f'{ticker} earnings {d} analyst consensus EPS estimate revenue estimate',pre_start,pre_end);time.sleep(.3)
 actual=search(f'{ticker} earnings {d} reported EPS actual revenue actual results',d.isoformat(),post_end);time.sleep(.3)
 guide=search(f'{ticker} earnings {d} guidance outlook consensus revenue EPS next quarter',d.isoformat(),post_end)
 eps_e,ce=choose(candidates(pre,'eps_estimate')); eps_a,ca=choose(candidates(actual,'eps_actual')); rev_e,cr=choose(candidates(pre,'rev_estimate')); rev_a,cra=choose(candidates(actual,'rev_actual'))
 def surprise(a,e):return round((a/e-1)*100,4) if a is not None and e not in (None,0) else None
 f=ev.setdefault('earningsFundamentals',{})
 f['eps']={'estimate':eps_e,'actual':eps_a,'surprisePct':surprise(eps_a,eps_e)}
 f['revenue']={'estimate':rev_e,'actual':rev_a,'surprisePct':surprise(rev_a,rev_e),'currency':'USD' if rev_e or rev_a else None}
 f['guidance']=f.get('guidance') or []
 f['status']='enriched' if all(x is not None for x in (eps_e,eps_a,rev_e,rev_a)) else 'needs_review'
 f['confidence']={'epsEstimate':ce,'epsActual':ca,'revenueEstimate':cr,'revenueActual':cra,'guidance':'research_only'}
 f['sources']={'consensus':refs(pre),'actuals':refs(actual),'guidanceResearch':refs(guide),'consensusAsOf':pre_end}
 f['researchPolicy']='Auto-accepted numeric fields require agreement across at least two returned sources; otherwise null/needs_review. Guidance is preserved as sourced research for structured review.'
 print(ticker,d,f['status'],eps_e,eps_a,rev_e,rev_a)
def main():
 for path in FILES:
  with open(path,encoding='utf-8') as fh:data=json.load(fh)
  for ticker,events in data.get('events',{}).items():
   for ev in events:enrich(ev,ticker)
  data['fundamentalsEnrichment']={'provider':'Tavily Search API','generatedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'policy':'Separate date-bounded consensus, actual-results and guidance searches; preserve source provenance; ambiguous values remain null.'}
  with open(path,'w',encoding='utf-8') as fh:json.dump(data,fh,ensure_ascii=False,indent=2);fh.write('\n')
if __name__=='__main__':main()
