#!/usr/bin/env node
// Historical price responses, with separate timestamps for composite events.
// Reads ../public/event-results.json and writes ../public/market-reactions.json.
import { readFile, writeFile } from 'node:fs/promises';

const source = new URL('../public/event-results.json', import.meta.url);
const output = new URL('../public/market-reactions.json', import.meta.url);
const archive = JSON.parse(await readFile(source, 'utf8'));
const key = process.env.MASSIVE_API_KEY;
if (!key) throw new Error('MASSIVE_API_KEY must be configured in GitHub Actions');
const extraWindows = {
  '2026-09-10-PPI + 30Y': [
    { label: 'Producer Price Index', timeET: '08:30', scheduleSource: 'https://www.bls.gov/schedule/2026/09_sched_list.htm' },
    { label: '30-year Treasury auction', timeET: '13:00', scheduleSource: 'https://www.treasurydirect.gov/auctions/announcements-data-results/' }
  ],
  '2026-09-16-FED + Retail': [
    { label: 'Retail sales', timeET: '08:30', scheduleSource: 'https://www.census.gov/retail/release_schedule.html' },
    { label: 'FOMC statement', timeET: '14:00', scheduleSource: 'https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm', caveat: 'The +1h window overlaps the 14:30 ET Fed press conference.' }
  ]
};
const onlyDate = process.env.BACKFILL_DATE;
const windows = archive.results.flatMap(record => {
  const indexed = archive.eventIndex[record.eventId];
  const date = indexed.eventDate;
  if (!/^2026-09-/.test(date) || (onlyDate && date !== onlyDate)) return [];
  const components = extraWindows[record.eventId] ??
    (/^\d{2}:\d{2}$/.test(indexed.timeET) ? [{label: record.eventId.slice(11), timeET: indexed.timeET, scheduleSource: record.sourceUrl}] : []);
  return components.map(component => ({eventId: record.eventId, date, ...component}));
});
const tickerDates = new Map();
for (const ticker of ['QQQ', 'NVDA', 'SMH']) {
  for (const date of [...new Set(windows.map(w => w.date))]) {
    if (ticker === 'QQQ' && !windows.some(w => w.date === date &&
      (extraWindows[w.eventId] || !archive.results.find(r => r.eventId === w.eventId)?.qqqReaction))) continue;
    tickerDates.set(`${ticker}/${date}`, {ticker, date});
  }
}
const formatter = new Intl.DateTimeFormat('en-US', {timeZone:'America/New_York', year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'});
function et(ms) {
  const p = Object.fromEntries(formatter.formatToParts(new Date(ms)).map(x => [x.type,x.value]));
  return {date:`${p.year}-${p.month}-${p.day}`,time:`${p.hour}:${p.minute}`};
}
function timestamp(date, time) {
  const noon = Date.parse(`${date}T${time}:00Z`);
  for(let utc = noon; utc < noon + 7*3600000; utc += 60000) {
    const p = et(utc);
    if(p.date===date && p.time===time) return utc;
  }
  throw new Error(`Could not resolve ${date} ${time} ET`);
}
const delay = ms => new Promise(r => setTimeout(r,ms));
async function fetchBars(ticker,date) {
  const url = new URL(`https://api.massive.com/v2/aggs/ticker/${ticker}/range/1/minute/${date}/${date}`);
  url.searchParams.set('adjusted','true');
  url.searchParams.set('sort','asc');
  url.searchParams.set('limit','5000');
  for (let attempt=0; attempt<4; attempt++) {
    const response = await fetch(url,{headers:{Authorization:`Bearer ${key}`}});
    if (response.status === 429 && attempt<3) {
      const retryAfter = Number(response.headers.get('retry-after'));
      const wait = Number.isFinite(retryAfter) && retryAfter>0 ? Math.min(90000,retryAfter*1000) : 30000*(attempt+1);
      console.log(`${ticker}/${date}: rate limited; retry in ${Math.ceil(wait/1000)}s`);
      await delay(wait);
      continue;
    }
    if (!response.ok) throw new Error(`Massive HTTP ${response.status} for ${ticker}/${date}`);
    const json = await response.json();
    if (json.status !== 'OK' || json.next_url) throw new Error(`Incomplete minute aggregates for ${ticker}/${date}`);
    return json.results ?? [];
  }
}
function measure(bars,utc,minutes) {
  const before = bars.find(b=>b.t===utc-60000 && Number.isFinite(b.c));
  const after = bars.find(b=>b.t===utc+(minutes-1)*60000 && Number.isFinite(b.c));
  if(!before || !after) return null;
  const pct=Math.round((after.c/before.c-1)*10000)/100;
  return {pct,before:{minuteET:et(before.t).time,close:before.c},after:{minuteET:et(after.t).time,close:after.c}};
}
const barCache = new Map(), errors=[];
let i=0;
for(const [id,{ticker,date}] of tickerDates) {
  if(i++) await delay(14000);
  try { barCache.set(id,await fetchBars(ticker,date)); }
  catch(err) { errors.push({ticker,date,error:String(err.message)});barCache.set(id,[]); }
  console.log(`${id}: ${barCache.get(id).length} minute bars`);
}
const out={schemaVersion:1,lastUpdated:new Date().toISOString().slice(0,10),source:'Massive adjusted one-minute aggregate bars',sourceUrl:'https://massive.com/docs/rest/stocks/aggregates/custom-bars',method:'Last completed one-minute bar before the scheduled release versus last completed one-minute bar at +15m or +60m; percent change rounded to 0.01 percentage points. Null if an exact bar is unavailable. These are observed price windows, not causal estimates.',events:{},errors};
for(const w of windows) {
  const archived=archive.results.find(x=>x.eventId===w.eventId);
  const simple=!extraWindows[w.eventId];
  const utc=timestamp(w.date,w.timeET);
  const assets={};
  for(const ticker of ['QQQ','NVDA','SMH']) {
    if(ticker==='QQQ' && simple && archived.qqqReaction) {
      assets.QQQ={at15:archived.qqqReaction.at15,at60:archived.qqqReaction.at60,source:'Existing verified Massive backfill'};
    } else {
      const bars=barCache.get(`${ticker}/${w.date}`)??[];
      assets[ticker]={at15:measure(bars,utc,15),at60:measure(bars,utc,60)};
    }
  }
  (out.events[w.eventId]??=[]).push({label:w.label,releaseTimeET:w.timeET,scheduleSource:w.scheduleSource,caveat:w.caveat??null,assets});
}
await writeFile(output,JSON.stringify(out,null,2)+'\n');
console.log(`Saved ${windows.length} release windows across ${Object.keys(out.events).length} historical records; ${errors.length} fetch failures.`);
