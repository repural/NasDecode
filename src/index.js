// Read-only short-TTL market quote proxy. Never changes model scores.
const BASE='https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol';
const SYMBOLS=['US10Y','US2Y','@CL.1','@LCO.1'];
const numeric=v=>{const n=Number(String(v??'').replace(/[,%$]/g,''));return Number.isFinite(n)?n:null};
export default {
 async fetch(request,env,ctx){
  const url=new URL(request.url);
  if(url.pathname!=='/api/live-macro')return env.ASSETS.fetch(request);
  if(request.method!=='GET')return new Response('Method not allowed',{status:405});
  const cache= caches.default;
  const cacheKey=new Request(url.origin+'/api/live-macro');
  const hit=await cache.match(cacheKey);
  if(hit)return hit;
  try{
   const qs=new URLSearchParams({symbols:SYMBOLS.join('|'),requestMethod:'itv',noform:'1',partnerId:'2',fund:'1',exthrs:'1',output:'json',events:'1'});
   const upstream=await fetch(BASE+'?'+qs.toString(),{headers:{'Accept':'application/json','Referer':'https://www.cnbc.com/','User-Agent':'Mozilla/5.0'}});
   if(!upstream.ok)throw Error('Quote upstream '+upstream.status);
   const raw=await upstream.json();
   let quotes=raw?.FormattedQuoteResult?.FormattedQuote||[];
   if(!Array.isArray(quotes))quotes=[quotes];
   const items={};
   for(const q of quotes){
    if(!SYMBOLS.includes(q.symbol)||Number(q.code)!==0)continue;
    const value=numeric(q.last),previous=numeric(q.previous_day_closing);
    if(value===null)continue;
    items[q.symbol]={value,previous,change:previous===null?null:value-previous,
      observationTime:q.last_timedate||q.last_time||q.lastTradeTime||q.tradeTime||null,
      source:'CNBC / Tradeweb or futures quote',session:q.market_status||null};
   }
   if(Object.keys(items).length===0)throw Error('No valid quotes returned');
   const response=new Response(JSON.stringify({retrievedAt:new Date().toISOString(),items}),{headers:{'Content-Type':'application/json','Cache-Control':'public, max-age=60, s-maxage=60','Access-Control-Allow-Origin':'*'}});
   ctx.waitUntil(cache.put(cacheKey,response.clone()));
   return response;
  }catch(e){return new Response(JSON.stringify({error:'Live quotes unavailable',details:String(e)}),{status:503,headers:{'Content-Type':'application/json','Cache-Control':'no-store'}})}
 }
};
