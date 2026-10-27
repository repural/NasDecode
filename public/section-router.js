(()=>{'use strict';
const pages={overview:'Overview',assessment:'Assessment',analysis:'Analysis',watch:'Open Watch',threeDay:'3-Day Watch'};
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
     group=t.includes('macro')?'macro':t.includes('internals')?'internals':(t.includes('assessment')||t.includes('technical analysis'))?'assessment':'';
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
html[data-nd-page="overview"] .signal-details,
html[data-nd-page="overview"] #marketMovingDevelopments{display:none!important}
html[data-nd-page="assessment"] #factorCards > :not([data-nd-section="assessment"]){display:none!important}
html[data-nd-page="assessment"] #premarket,html[data-nd-page="assessment"] .lower-intel,html[data-nd-page="assessment"] #marketMovingDevelopments,
html[data-nd-page="analysis"] #factorCards,html[data-nd-page="analysis"] .signal-details,html[data-nd-page="analysis"] #marketSetup,html[data-nd-page="analysis"] .lower-intel,html[data-nd-page="analysis"] #marketMovingDevelopments,
html[data-nd-page="watch"] #factorCards,html[data-nd-page="watch"] #premarket,html[data-nd-page="watch"] .signal-details,html[data-nd-page="watch"] #marketSetup{display:none!important}
html[data-nd-page="threeDay"] #dashboard > :not(.nd-page-title):not(#nd-three-day-watch){display:none!important}
html[data-nd-page="overview"] .lower-intel{margin-top:18px}
.nd-three-day{max-width:1020px;margin:14px 0 60px}.nd-three-day .nd-watch-meta{color:#aab3be;margin-bottom:18px}.nd-three-day .nd-watch-card{border:1px solid #34383f;border-top:3px solid #27d17f;border-radius:12px;background:#171a20;padding:22px;margin:0 0 18px}.nd-three-day .nd-watch-card.unchanged{border-top-color:#7d8998}.nd-three-day h2{font-size:22px;margin:0 0 8px}.nd-three-day h3{font-size:15px;margin:22px 0 8px}.nd-three-day p,.nd-three-day li{color:#d2d8e0;line-height:1.65}.nd-three-day .nd-watch-bias{color:#6ee7ad;font-weight:700}.nd-three-day .nd-watch-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}.nd-three-day .nd-watch-box{border:1px solid #30343b;border-radius:9px;padding:14px}.nd-three-day .nd-watch-box b{display:block;margin-bottom:6px}.nd-three-day .nd-watch-archive{margin-top:24px}.nd-three-day details{border-bottom:1px solid #34383f;padding:12px 0}.nd-three-day summary{cursor:pointer;color:#e6e9ee;font-weight:600}.nd-three-day .nd-watch-observations{display:flex;flex-wrap:wrap;gap:8px}.nd-three-day .nd-watch-observations span{padding:6px 9px;background:#242b33;border-radius:7px;font-size:12px;color:#d6dce4}@media(max-width:680px){.nd-three-day .nd-watch-grid{grid-template-columns:1fr}.nd-three-day .nd-watch-card{padding:16px}}
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
 const obs=e=>Object.entries(e.observations||{}).map(([k,v])=>'<span>'+esc(k.replace(/([a-z])([A-Z])/g,'$1 $2'))+': <b>'+esc(v)+'</b></span>').join('');
 const editorial=e=>{const x=e.editorial;if(!x)return '<h3>Market interpretation</h3><p>'+esc(e.summary||'Editorial analysis pending next update.')+'</p>';if(typeof x==='string')return '<h3>Market interpretation</h3><p>'+esc(x)+'</p>';const sections=[['marketOverview','Market overview'],['whatChanged','What changed'],['marketInterpretation','Market interpretation'],['threeDayPath','Expected three-day path'],['bullCase','Bullish scenario'],['bearCase','Bearish scenario'],['watchNext','What to watch']];return sections.filter(([k])=>x[k]).map(([k,title])=>'<h3>'+title+'</h3><p>'+esc(x[k])+'</p>').join('')||'<h3>Market interpretation</h3><p>'+esc(e.summary||'')+'</p>';};
 const render=e=>'<div class="nd-watch-card '+(e.materialChange?'':'unchanged')+'"><div class="nd-watch-meta">'+esc(e.date)+' · '+esc(e.timeET)+' ET · '+(e.materialChange?'Material outlook change':'No material change')+'</div><h2 class="nd-watch-bias">'+esc(e.bias)+'</h2>'+editorial(e)+'<div class="nd-watch-grid"><div class="nd-watch-box"><b>Strongest bullish evidence</b>'+esc(e.bullish)+'</div><div class="nd-watch-box"><b>Strongest bearish evidence</b>'+esc(e.bearish)+'</div></div><h3>Market observations</h3><div class="nd-watch-observations">'+obs(e)+'</div>'+(e.conditions?.length?'<h3>Confirmation / invalidation</h3><ul>'+e.conditions.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'')+'<h3>Upcoming catalysts</h3><ul>'+(e.upcomingEvents||[]).map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul><p class="nd-watch-meta">'+esc(e.provenance)+'</p></div>';
 async function loadWatch(){try{const r=await fetch('/data/three-day-watch.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const data=await r.json();const entries=(data.entries||[]).slice().sort((a,b)=>(b.date+'T'+b.timeET).localeCompare(a.date+'T'+a.timeET));if(!entries.length)throw Error('No saved assessments');host.innerHTML='<p class="nd-watch-meta">Current three-session horizon: '+esc((data.horizon||[]).join(' → '))+' · Latest published assessment</p>'+render(entries[0]);;}catch(e){host.textContent='3-Day Watch history is temporarily unavailable: '+e.message;}}
 loadWatch();setInterval(()=>{if(!document.hidden)loadWatch()},120000);
}
})();