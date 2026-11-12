(()=>{'use strict';
const pages={overview:'Overview',analysis:'Pre-Market',assessment:'Assessment',threeDay:'3-Day Watch',watch:'Open Watch',calendar:'Calendar'};
const rawView=new URLSearchParams(location.search).get('view')||'overview';
const requested=['macro','internals'].includes(rawView)?'overview':rawView;
const view=Object.prototype.hasOwnProperty.call(pages,requested)?requested:'overview';
document.documentElement.dataset.ndPage=view;
document.title='NasDecode — '+pages[view];
const nav=document.querySelector('.nd-nav');
if(nav){nav.setAttribute('aria-label','NasDecode pages');nav.innerHTML=Object.entries(pages).map(([key,name])=>'<a href="/'+(key==='overview'?'':'?view='+key)+'"'+(key===view?' class="nd-current" aria-current="page"':'')+'>'+name+'</a>').join('')}
const cards=document.getElementById('factorCards');
function markGroups(){
 if(!cards)return;
 let group='';
 [...cards.children].forEach(el=>{
   if(el.classList.contains('scorecard-category')){
     const t=el.textContent.toLowerCase();
     group=t.includes('macro')?'macro':(t.includes('internals')||t.includes('indicators'))?'internals':(t.includes('assessment')||t.includes('technical analysis'))?'assessment':'';
   }
   if(group&&el.dataset.ndSection!==group)el.dataset.ndSection=group;
 });
}
if(cards){
 new MutationObserver(markGroups).observe(cards,{childList:true});
 markGroups();
}
const style=document.createElement('style');
style.textContent=`
html[data-nd-page="overview"] #factorCards > :not([data-nd-section="macro"]):not([data-nd-section="internals"]),
html[data-nd-page="overview"] #premarket,
html[data-nd-page="overview"] .signal-details{display:none!important}
html[data-nd-page="assessment"] #factorCards > :not([data-nd-section="assessment"]){display:none!important}
html[data-nd-page="assessment"] #premarket,html[data-nd-page="assessment"] .lower-intel,html[data-nd-page="assessment"] #marketMovingDevelopments,
html[data-nd-page="analysis"] #factorCards,html[data-nd-page="analysis"] .signal-details,html[data-nd-page="analysis"] #marketSetup,html[data-nd-page="analysis"] .lower-intel,html[data-nd-page="analysis"] #marketMovingDevelopments,
html[data-nd-page="watch"] #factorCards,html[data-nd-page="watch"] #premarket,html[data-nd-page="watch"] .signal-details,html[data-nd-page="watch"] #marketSetup{display:none!important}
html[data-nd-page="threeDay"] #dashboard > :not(.nd-page-title):not(#nd-three-day-watch){display:none!important}
html[data-nd-page="overview"] .lower-intel{margin-top:18px}\nhtml[data-nd-page="overview"] #marketMovingDevelopments .nd-earnings-section{display:none!important}
.nd-three-day{max-width:1020px;margin:14px 0 60px}.nd-three-day .nd-watch-meta{color:#aab3be;margin-bottom:18px}.nd-three-day .nd-watch-card{border:1px solid #34383f;border-top:3px solid #27d17f;border-radius:12px;background:#171a20;padding:22px;margin:0 0 18px}.nd-three-day .nd-watch-card.unchanged{border-top-color:#7d8998}.nd-three-day h2{font-size:22px;margin:0 0 8px}.nd-three-day h3{font-size:15px;margin:22px 0 8px}.nd-three-day p,.nd-three-day li{color:#d2d8e0;line-height:1.65}.nd-three-day .nd-watch-bias{color:#6ee7ad;font-weight:700}.nd-three-day .nd-watch-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.nd-three-day .nd-watch-box{border:1px solid #30343b;border-radius:9px;padding:14px}.nd-three-day .nd-watch-box b{display:block;margin-bottom:6px}.nd-three-day .nd-watch-archive{margin-top:24px}.nd-three-day details{border-bottom:1px solid #34383f;padding:12px 0}.nd-three-day summary{cursor:pointer;color:#e6e9ee;font-weight:600}.nd-three-day .nd-watch-observations{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:10px}
.nd-three-day .nd-observation-card{min-width:0;padding:14px 15px;border:1px solid #333840;border-radius:10px;background:#191c20}
.nd-three-day .nd-observation-label{font-size:12px;font-weight:650;color:#dfe5ea;margin-bottom:8px}
.nd-three-day .nd-observation-value{font-size:12px;color:#c9d1d8;line-height:1.55;overflow-wrap:anywhere}
.nd-three-day .nd-observation-fields{display:grid;gap:7px;margin:0}
.nd-three-day .nd-observation-fields>div{min-width:0;display:flex;flex-wrap:wrap;justify-content:space-between;gap:3px 10px;border-top:1px solid #30343b;padding-top:6px}
.nd-three-day .nd-observation-fields dt{color:#9faab5}
.nd-three-day .nd-observation-fields dd{margin:0;color:#e5eaf0;font-weight:600;overflow-wrap:anywhere}
.nd-three-day .nd-observation-list{margin:0;padding-left:16px}
.nd-three-day .nd-observation-list li{margin-bottom:4px}
.nd-three-day .nd-observation-empty{color:#939da7;font-weight:400}@media(max-width:680px){.nd-three-day .nd-watch-grid{grid-template-columns:1fr}.nd-three-day .nd-watch-card{padding:16px}}
html[data-nd-page="analysis"] .nd-page-title{display:none!important}
html[data-nd-page="threeDay"] .nd-page-title{display:none!important}
html[data-nd-page="threeDay"] .nd-three-day{max-width:1280px;width:100%;margin:0 auto 60px;padding:28px clamp(20px,3vw,48px);border:1px solid #303236;border-radius:12px;background:#101113}
.nd-three-day .nd-three-day-title{display:flex;align-items:flex-end;justify-content:space-between;flex-wrap:wrap;gap:14px;margin:0 0 30px;max-width:1100px}
.nd-three-day .nd-three-day-kicker{font-size:12px;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:#aab2bb}
.nd-three-day .nd-three-day-title h2{font-size:clamp(28px,2.5vw,36px);font-weight:700;line-height:1.2;letter-spacing:-.035em;color:#f1f3f5;margin:7px 0 0}
.nd-three-day .nd-three-day-updated{font-size:12px;line-height:1.55;color:#aeb5bd}
.nd-three-day .nd-three-day-horizon{font-size:13px;line-height:1.6;color:#aeb5bd;margin:0 0 25px}
.nd-three-day .nd-watch-card{max-width:1100px;background:transparent;border:none;border-radius:0;border-top:none;padding:0;margin:0}
.nd-three-day .nd-watch-card.unchanged{border-top:none}
.nd-three-day .nd-watch-bias{font-size:clamp(22px,2vw,28px);font-weight:680;line-height:1.35;margin:0 0 20px;color:#f1f3f5}
.nd-three-day .nd-three-day-reading{max-width:1000px}
.nd-three-day .nd-three-day-reading p,.nd-three-day .nd-three-day-reading li{font-size:16px;line-height:1.8;color:#dbe0e4;font-weight:430}
.nd-three-day .nd-three-day-reading h3{font-size:21px;line-height:1.4;font-weight:680;letter-spacing:-.015em;color:#f1f3f5;margin:28px 0 15px}
.nd-three-day .nd-three-day-reading ul{padding-left:24px;margin:0 0 19px}
.nd-three-day .nd-three-day-reading li{padding-left:3px;margin:0 0 8px}
.nd-three-day .nd-watch-grid{max-width:1000px;gap:12px;margin:22px 0 28px}
.nd-three-day .nd-watch-box{padding:17px 19px;border:1px solid #34383f;border-radius:10px;font-size:16px;line-height:1.65;color:#dbe0e4}
.nd-three-day .nd-watch-box b{font-size:13px;line-height:1.5;color:#aeb5bd;margin-bottom:10px}
.nd-three-day .nd-watch-meta{font-size:12px;color:#aeb5bd}
@media(max-width:700px){html[data-nd-page="threeDay"] .nd-three-day{padding:20px 16px}.nd-three-day .nd-three-day-reading p,.nd-three-day .nd-three-day-reading li{font-size:15px;line-height:1.72}.nd-three-day .nd-watch-grid{grid-template-columns:1fr}.nd-three-day .nd-watch-box{padding:14px}}


html[data-nd-page="calendar"] #dashboard > :not(.nd-page-title):not(#nd-economic-calendar){display:none!important}
.nd-calendar{max-width:1390px;margin:0 0 70px;color:#e9edf1}
.nd-calendar .nd-cal-toolbar{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px;margin:0 0 18px}
.nd-calendar .nd-cal-intro{font-size:13px;color:#aeb4be;line-height:1.6;max-width:790px}
.nd-calendar .nd-cal-filter{display:flex;gap:7px;align-items:center;flex-wrap:wrap}
.nd-calendar .nd-cal-filter button{background:#191b1f;border:1px solid #35383e;border-radius:7px;padding:8px 13px;color:#ccd2d9;font:inherit;font-size:12px;cursor:pointer}
.nd-calendar .nd-cal-filter button[aria-pressed="true"]{background:#30343a;border-color:#6e777f;color:#fff}
.nd-calendar .nd-cal-filter button:focus-visible,.nd-calendar a:focus-visible{outline:2px solid #82cbd0;outline-offset:2px}
.nd-calendar .nd-cal-table-wrap{border:1px solid #32353a;border-radius:11px;overflow-x:auto;background:#101113}
.nd-calendar table{width:100%;border-collapse:collapse;min-width:820px;font-size:13px}
.nd-calendar thead{background:#1b1d20;position:sticky;top:0;z-index:1}
.nd-calendar th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#aeb5bd;font-weight:600;padding:13px 15px}
.nd-calendar td{padding:12px 15px;border-top:1px solid #2e3136;vertical-align:top;color:#d9dde2;font-variant-numeric:tabular-nums}
.nd-calendar .nd-cal-day td{font-size:13px;font-weight:700;background:#202226;color:#f0f2f4;padding:12px 15px;border-top:1px solid #3c4046}
.nd-calendar .nd-cal-day:first-child td{border-top:0}
.nd-calendar .nd-cal-day-toggle{width:100%;display:flex;align-items:center;gap:6px;text-align:left;border:0;background:transparent;color:inherit;font:inherit;font-weight:inherit;padding:0;cursor:pointer}
.nd-calendar .nd-cal-day-toggle:focus-visible{outline:2px solid #82cbd0;outline-offset:3px}
.nd-calendar .nd-cal-chevron{min-width:13px;color:#9eabb8}
.nd-calendar .nd-cal-day-count{color:#9da5af;font-weight:400}
.nd-calendar .nd-cal-entry[hidden]{display:none!important}
.nd-calendar .nd-cal-time{white-space:nowrap;color:#cad1d7}
.nd-calendar .nd-cal-report{font-weight:580;color:#f2f3f5}
.nd-calendar .nd-cal-report small{display:block;color:#9ca5ae;font-size:11px;font-weight:400;margin-top:5px}
.nd-calendar .nd-cal-report a{color:#82cbd0;text-decoration:none}
.nd-calendar .nd-cal-report a:hover{text-decoration:underline}
.nd-calendar .nd-cal-number{white-space:nowrap}
.nd-calendar .nd-cal-importance{display:inline-block;width:6px;height:6px;border-radius:50%;background:#707980;margin-right:7px;vertical-align:middle}
.nd-calendar .nd-cal-importance.high{background:#f5bd4b}
.nd-calendar .nd-cal-importance.critical{background:#ff6078}
.nd-calendar .nd-cal-note{font-size:12px;line-height:1.6;color:#a8b0ba;margin:12px 0 0}
.nd-calendar .nd-cal-loading{padding:25px 18px;color:#aeb5bd;border:1px solid #30343a;border-radius:9px}
@media(max-width:700px){.nd-calendar .nd-cal-toolbar{align-items:flex-start}.nd-calendar .nd-cal-table-wrap{margin:0 -5px}.nd-calendar td{padding:11px 12px}.nd-calendar th{padding:11px 12px}}

.nd-page-title{margin:22px 0 18px;font-size:26px;font-weight:690;letter-spacing:-.025em}
.nd-page-intro{color:#aeb4bc;font-size:13px;line-height:1.55;margin:-8px 0 20px}
@media(max-width:780px){.nd-nav{overflow-x:auto;flex-wrap:nowrap;scrollbar-width:thin}.nd-nav a{white-space:nowrap;flex:none}}
`;
document.head.appendChild(style);
const wrap=document.getElementById('dashboard');
if(wrap&&view!=='overview'){
 const h=document.createElement('h1');h.className='nd-page-title';h.textContent=pages[view];
 wrap.prepend(h);
}
if(wrap&&view==='threeDay'){
 const host=document.createElement('section');host.id='nd-three-day-watch';host.className='nd-three-day';host.innerHTML='<p class="nd-watch-meta">Loading latest 3-Day Watch…</p>';wrap.appendChild(host);
 const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const prettyKey=k=>String(k).replace(/([a-z0-9])([A-Z])/g,'$1 $2').replace(/([A-Z])([A-Z][a-z])/g,'$1 $2').replace(/_/g,' ');
 const observationValue=(v,depth=0)=>{
   if(v===null||v===undefined||v==='')return '<span class="nd-observation-empty">Not available</span>';
   if(typeof v==='boolean')return esc(v?'Yes':'No');
   if(typeof v!=='object')return esc(v);
   if(depth>=3)return '<span class="nd-observation-empty">Additional details available in source data</span>';
   if(Array.isArray(v))return v.length?'<ul class="nd-observation-list">'+v.slice(0,20).map(item=>'<li>'+observationValue(item,depth+1)+'</li>').join('')+'</ul>':'<span class="nd-observation-empty">No entries</span>';
   const pairs=Object.entries(v).filter(([k])=>!['raw','debug','html'].includes(k));
   return pairs.length?'<dl class="nd-observation-fields">'+pairs.map(([key,val])=>'<div><dt>'+esc(prettyKey(key))+'</dt><dd>'+observationValue(val,depth+1)+'</dd></div>').join('')+'</dl>':'<span class="nd-observation-empty">No details</span>';
 };
 const obs=e=>Object.entries(e.observations||{}).map(([k,v])=>'<div class="nd-observation-card"><div class="nd-observation-label">'+esc(prettyKey(k))+'</div><div class="nd-observation-value">'+observationValue(v)+'</div></div>').join('')||'<p class="nd-watch-meta">No market observations recorded.</p>';
 const editorial=e=>{const x=e.editorial;if(!x)return '<h3>Market interpretation</h3><p>'+esc(e.summary||'Editorial analysis pending next update.')+'</p>';if(typeof x==='string')return '<h3>Market interpretation</h3><p>'+esc(x)+'</p>';const sections=[['marketOverview','Market overview'],['whatChanged','What changed'],['marketInterpretation','Market interpretation'],['threeDayPath','Expected three-day path'],['bullCase','Bullish scenario'],['bearCase','Bearish scenario'],['watchNext','What to watch']];return sections.filter(([k])=>x[k]).map(([k,title])=>'<h3>'+title+'</h3><p>'+esc(x[k])+'</p>').join('')||'<h3>Market interpretation</h3><p>'+esc(e.summary||'')+'</p>';};
 const render=e=>'<div class="nd-three-day-title"><div><div class="nd-three-day-kicker">NasDecode research</div><h2>3-Day Watch</h2></div><div class="nd-three-day-updated">Assessment '+esc(e.date)+' · '+esc(e.timeET)+' ET</div></div><div class="nd-watch-card '+(e.materialChange?'':'unchanged')+'"><div class="nd-three-day-reading"><div class="nd-watch-meta">'+(e.materialChange?'Material outlook change':'No material change')+'</div><h3>Nasdaq outlook</h3><h2 class="nd-watch-bias">'+esc(e.bias)+'</h2>'+editorial(e)+'<div class="nd-watch-grid"><div class="nd-watch-box"><b>Strongest bullish evidence</b>'+esc(e.bullish)+'</div><div class="nd-watch-box"><b>Strongest bearish evidence</b>'+esc(e.bearish)+'</div></div>'+(e.conditions?.length?'<h3>Confirmation / invalidation</h3><ul>'+e.conditions.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+'<h3>Upcoming catalysts</h3><ul>'+(e.upcomingEvents||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><p class="nd-watch-meta">'+esc(e.provenance)+'</p></div></div>';
 async function loadWatch(){try{const r=await fetch('/data/three-day-watch.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();const entries=(data.entries||[]).slice().sort((a,b)=>(b.date+'T'+b.timeET).localeCompare(a.date+'T'+a.timeET));if(!entries.length)throw Error('No saved assessments');host.innerHTML=render(entries[0]); const h=host.querySelector('.nd-three-day-title');if(h&&data.horizon?.length)h.insertAdjacentHTML('afterend','<p class="nd-three-day-horizon">Next three trading sessions: '+esc(data.horizon.join(' → '))+'</p>');;}catch(e){host.textContent='3-Day Watch history is temporarily unavailable: '+e.message;}}
 loadWatch();setInterval(()=>{if(!document.hidden)loadWatch()},120000);
}
if(wrap&&view==='calendar'){
 const host=document.createElement('section');host.id='nd-economic-calendar';host.className='nd-calendar';
 host.innerHTML='<div class="nd-cal-loading">Loading the next two weeks of U.S. economic releases…</div>';wrap.appendChild(host);
 const safe=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const dateText=x=>new Date(x+'T12:00:00Z').toLocaleDateString('en-US',{timeZone:'UTC',weekday:'long',month:'short',day:'numeric'});
 const timeText=e=>{if(!e.timeET)return safe(e.timeLabel||'TBA');const [h,m]=e.timeET.split(':').map(Number);return (h%12||12)+':'+String(m).padStart(2,'0')+(h>=12?' PM':' AM')};
 const txt=x=>x===null||x===undefined||x===''?'—':safe(x);
 let feed=null,filter='all';
 const dayOverrides=new Map();
 const nyToday=()=>new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
 const render=()=>{
  if(!feed)return;
  const list=(feed.events||[]).filter(e=>filter==='all'||(filter==='high'?['Critical','High'].includes(e.importance):e.category===filter));
  const start=feed.windowStart,end=feed.windowEnd,today=nyToday();
  let body='';
  for(let day=new Date(start+'T12:00:00Z');day<=new Date(end+'T12:00:00Z');day.setUTCDate(day.getUTCDate()+1)){
    if(day.getUTCDay()===0||day.getUTCDay()===6)continue; // Business-day calendar: omit Saturday and Sunday.
    const key=day.toISOString().slice(0,10),items=list.filter(e=>e.date===key);
    const past=key<today,opened=dayOverrides.has(key)?dayOverrides.get(key):!past;
    body+='<tr class="nd-cal-day"><td colspan="6"><button type="button" class="nd-cal-day-toggle" data-cal-day="'+key+'" aria-expanded="'+opened+'"><span class="nd-cal-chevron">'+(opened?'▾':'▸')+'</span>'+safe(dateText(key))+' <span class="nd-cal-day-count"> · '+items.length+' event'+(items.length===1?'':'s')+(past?' · Passed':'')+'</span></button></td></tr>';
    if(!items.length){body+='<tr class="nd-cal-entry" data-cal-entry-day="'+key+'"'+(opened?'':' hidden')+'><td colspan="6" style="color:#9ca5ae">No tracked releases scheduled</td></tr>';continue}
    for(const e of items){
      const src=e.sourceUrl&&/^https:\/\//.test(e.sourceUrl)?'<a href="'+safe(e.sourceUrl)+'" target="_blank" rel="noopener noreferrer">Source ↗</a>':'';
      body+='<tr class="nd-cal-entry" data-cal-entry-day="'+key+'"'+(opened?'':' hidden')+'><td class="nd-cal-time">'+timeText(e)+'</td><td class="nd-cal-report"><span class="nd-cal-importance '+safe(String(e.importance||'').toLowerCase())+'"></span>'+safe(e.report)+'<small>'+safe(e.category||'Macro')+' · '+safe(e.importance||'High')+(e.forecastType?' · Forecast: '+safe(e.forecastType):'')+' · '+src+'</small></td><td>'+txt(e.period)+'</td><td class="nd-cal-number">'+txt(e.actual)+'</td><td class="nd-cal-number">'+txt(e.forecast)+'</td><td class="nd-cal-number">'+txt(e.previous)+'</td></tr>';
    }
  }
  host.innerHTML='<div class="nd-cal-toolbar"><div class="nd-cal-intro">U.S. economic releases, Fed events and technology earnings · '+safe(dateText(start))+' – '+safe(dateText(end))+' · All times Eastern (ET)</div><div class="nd-cal-filter">'+[['all','All events'],['high','High impact'],['Macro','Economic'],['Inflation','Inflation'],['Rates','Rates'],['Fed','Fed'],['Earnings','Earnings']].map(([v,label])=>'<button type="button" data-cal-filter="'+v+'" aria-pressed="'+(filter===v)+'">'+label+'</button>').join('')+'</div></div><div class="nd-cal-table-wrap"><table><thead><tr><th>Time (ET)</th><th>Report</th><th>Period</th><th>Actual</th><th>Forecast</th><th>Previous</th></tr></thead><tbody>'+body+'</tbody></table></div><p class="nd-cal-note">Sources: NasCal official-source research (read-only), a dated MarketWatch factual snapshot, and NasDecode’s Nasdaq earnings feed. MarketWatch observations are from '+safe(feed.marketwatchObservedAt||'an undated capture')+' and are not a live licensed feed. Earnings forecasts are EPS estimates. Missing readings show “—”. Updated '+safe(feed.updatedAt||'unknown')+'.</p>';
  host.querySelectorAll('[data-cal-filter]').forEach(btn=>btn.addEventListener('click',()=>{filter=btn.dataset.calFilter;render()}));
  host.querySelectorAll('[data-cal-day]').forEach(btn=>btn.addEventListener('click',()=>{const day=btn.dataset.calDay;dayOverrides.set(day,btn.getAttribute('aria-expanded')!=='true');render()}));
 };
 const load=async()=>{try{const r=await fetch('/data/economic-calendar.json?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(!Array.isArray(d.events)||!d.windowStart||!d.windowEnd)throw Error('Invalid calendar data');const changed=!feed||JSON.stringify(d.events)!==JSON.stringify(feed.events)||d.windowStart!==feed.windowStart||d.windowEnd!==feed.windowEnd;if(changed){feed=d;render()}}catch(e){if(!feed)host.innerHTML='<div class="nd-cal-loading">Economic calendar is temporarily unavailable: '+safe(e.message)+'</div>';else console.warn('Calendar refresh temporarily unavailable',e)}};
 load();
 setInterval(()=>{if(!document.hidden)load()},120000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)load()});
}

})();