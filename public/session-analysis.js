(()=>{
  const stages=[
    {key:'premarket',label:'Pre-Market',time:'Before 09:30 ET'},
    {key:'early_market',label:'Early Market',time:'10:30 ET checkpoint'},
    {key:'mid_market',label:'Mid-Market',time:'13:00 ET checkpoint'},
    {key:'near_close',label:'Near-Close',time:'15:30 ET checkpoint'}
  ];
  let sessionData={records:{}}, premarketData=null, dashboard=null, manualTab=null;

  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const metricRe=/\b(NasDecode Score|Consolidation Risk|Opportunity Score|SOXL Buy Score|Inflation · Labor · Growth|Semiconductor Leadership|Mega-cap Leadership|Earnings AVWAP Leadership|S&P 500 50D Breadth|Nasdaq(?:-100| 100)?|SOXX|SOX|SMH|Semiconductor(?:s)?|Mega-cap(?:s)?|Market breadth|Breadth|VIX volatility|VIX|VXN|10Y Treasury(?: Yield)?|2Y Treasury(?: Yield)?|Treasury yields?|Treasuries|Fed(?: expectations)?|Federal Reserve|Options positioning|WTI|Brent|Oil|Core CPI|CPI|Core PCE|PCE|Payrolls?|Nonfarm payrolls?|Unemployment|Wages?|Average Hourly Earnings|ISM(?: Manufacturing| Services)?|PMI|Retail Sales|GDP)\b/gi;
  const analysisText=s=>esc(s).replace(metricRe,'<span class="analysis-metric">$1</span>');

  function etParts(){
    const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit',weekday:'short',hour:'2-digit',minute:'2-digit',hour12:false}).formatToParts(new Date());
    const g=t=>p.find(x=>x.type===t)?.value;
    return {date:`${g('year')}-${g('month')}-${g('day')}`,weekday:g('weekday'),minutes:Number(g('hour'))*60+Number(g('minute'))};
  }
  function automaticTab(){
    const {minutes}=etParts();
    if(minutes<570)return 'premarket';
    if(minutes<780)return 'early_market';
    if(minutes<930)return 'mid_market';
    return 'near_close';
  }
  function installStyle(){
    if(document.getElementById('session-tabs-style'))return;
    const s=document.createElement('style');s.id='session-tabs-style';s.textContent=`
      .session-tabs-shell{margin:0}
      .session-tabs-head{display:flex;justify-content:space-between;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:14px}
      .session-tabs-head h2{margin:0}.session-tabs-head .muted{font-size:12px}
      .session-tabbar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);border-radius:11px;overflow:hidden;background:#091626;margin-bottom:18px}
      .session-tab{appearance:none;border:0;border-right:1px solid var(--line);border-radius:0;background:#091626;color:var(--muted);padding:12px 10px;cursor:pointer;text-align:left}
      .session-tab:last-child{border-right:0}.session-tab:hover{background:#10233a}.session-tab.active{background:#15304f;color:var(--text);box-shadow:inset 0 -3px 0 #65b9ff}
      .session-tab b{display:block;font-size:13px}.session-tab span{display:block;font-size:10px;margin-top:3px;color:inherit;opacity:.82}
      .session-tab.has-data b:after{content:' •';color:var(--green)}.session-tab.awaiting b:after{content:' •';color:var(--amber)}
      .session-tab-panel{border-top:1px solid #182b44;padding-top:16px}
      .session-analysis-title{display:flex;justify-content:space-between;gap:16px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px}
      .session-analysis-title h3{margin:0;font-size:20px}.session-analysis-time{font-size:11px;color:var(--muted)}
      .session-analysis-metrics{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 12px}.session-pill{border:1px solid #29415e;background:#10233a;border-radius:999px;padding:5px 9px;font-size:11px;font-weight:750}
      .session-tab-panel p{color:#e5edf7;line-height:1.6;margin:10px 0}.session-tab-panel .analysis-metric{color:#65b9ff;font-weight:750}
      .session-awaiting{padding:18px 0;color:var(--muted);line-height:1.55}.session-current-note{font-size:11px;color:#65b9ff;font-weight:750}
      @media(max-width:700px){.session-tabbar{grid-template-columns:1fr 1fr}.session-tab:nth-child(2){border-right:0}.session-tab:nth-child(-n+2){border-bottom:1px solid var(--line)}}`;
    document.head.appendChild(s);
  }
  function metric(label,v,suffix=''){
    return v===null||v===undefined||v===''?'':`<span class="session-pill">${esc(label)} ${esc(v)}${suffix}</span>`;
  }
  function premarketView(){
    const a=premarketData||{};
    const today=etParts().date;
    const inferred=a.tradingDate||String(a.updated||a.updatedET||'').match(/\b20\d{2}-\d{2}-\d{2}\b/)?.[0];
    if(!a||inferred!==today){
      return {available:false,title:'Pre-Market Analysis',meta:'Today’s analysis is being prepared.',body:'<div class="session-awaiting">The current pre-market brief has not been published yet.</div>'};
    }
    const ns=dashboard?.nasdaqScore||{};
    const sig=ns.signal==='positive'?'Positive':ns.signal==='negative'?'Negative':'Mixed';
    const score=a.score!==null&&a.score!==undefined?(a.score>0?'+':'')+a.score:'—';
    const metrics=[metric('Score',score,' / 100')].join('');
    const paras=(a.paragraphs||a.summary||[]).map(p=>`<p>${analysisText(p)}</p>`).join('');
    const catalysts=(a.catalysts||a.events||[]).map(e=>`<li><b>${esc(e.date?e.date+' · ':'')}${analysisText(e.title||'')}</b>${e.detail?' — '+analysisText(e.detail):''}</li>`).join('');
    const watch=a.watchIntoOpen?`<p>${analysisText(a.watchIntoOpen)}</p>`:'';
    const keyTimes=a.keyTimes?`<p>${analysisText(a.keyTimes)}</p>`:'';
    const bias=a.bias?`<div class="bias"><b>Pre-market bias:</b> ${esc(a.bias)}${a.confidence?' &nbsp; · &nbsp; <b>Confidence:</b> '+esc(a.confidence):''}</div>`:`<div class="bias"><b>Nasdaq Score:</b> ${sig} &nbsp; · &nbsp; <b>Score:</b> ${score} / 100</div>`;
    return {available:true,title:'Pre-Market Analysis',meta:'Analysis updated: '+esc(a.updatedET||a.updated||'—'),body:bias+(metrics?`<div class="session-analysis-metrics">${metrics}</div>`:'')+paras+(catalysts?`<h3>Major events to watch today</h3><ol>${catalysts}</ol>`:'')+watch+keyTimes};
  }
  function checkpointView(key){
    const day=etParts().date;
    const a=(sessionData?.records||{})[day]?.[key];
    const def=stages.find(x=>x.key===key);
    if(!a){
      return {available:false,title:(def?.label||key)+' Analysis',meta:def?.time||'',body:`<div class="session-awaiting">Scheduled analysis will appear here after the ${esc(def?.time||'checkpoint')} is captured.</div>`};
    }
    const score=a.nasdaqScore!==null&&a.nasdaqScore!==undefined?(a.nasdaqScore>0?'+':'')+a.nasdaqScore:'—';
    const metrics=[
      metric('Score',score,' / 100'),metric('Nasdaq',a.nasdaqChangePct,'%'),metric('QQQ',a.qqqChangePct,'%'),
      metric('Risk',a.consolidationRisk,' / 100'),metric('Opportunity',a.opportunityScore,' / 100'),
      metric('Internal',a.internalConfirmation,' / 100'),metric('Semi',a.semiconductorLeadership,' / 100')
    ].join('');
    const paras=(a.paragraphs||[]).map(p=>`<p>${analysisText(p)}</p>`).join('');
    const captured=a.capturedET?new Date(a.capturedET).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'}):'—';
    return {available:true,title:a.label||((def?.label||key)+' Analysis'),meta:`${esc(a.scheduledET||def?.time||'')} · captured ${esc(captured)}`,body:`<div class="session-analysis-metrics">${metrics}</div>${paras}`};
  }
  function viewFor(key){return key==='premarket'?premarketView():checkpointView(key)}
  function paint(){
    installStyle();
    const host=document.getElementById('premarket');if(!host)return;
    host.className='premarket session-tabs-shell';
    const auto=automaticTab(), selected=manualTab||auto, view=viewFor(selected);
    const tabs=stages.map(s=>{
      const v=viewFor(s.key), cls=['session-tab',s.key===selected?'active':'',v.available?'has-data':'awaiting'].filter(Boolean).join(' ');
      const current=s.key===auto?'<span class="session-current-note">Current window</span>':'';
      return `<button type="button" class="${cls}" data-session-tab="${s.key}" aria-selected="${s.key===selected?'true':'false'}"><b>${esc(s.label)}</b><span>${esc(s.time)}</span>${current}</button>`;
    }).join('');
    host.innerHTML=`<div class="session-tabs-head"><div><div class="section-kicker">Session analysis</div><h2>NasDecode Analysis</h2></div><div class="muted">Automatically follows New York market time · click any tab to review</div></div><div class="session-tabbar" role="tablist">${tabs}</div><div class="session-tab-panel" role="tabpanel"><div class="session-analysis-title"><h3>${esc(view.title)}</h3><div class="session-analysis-time">${view.meta}</div></div>${view.body}</div>`;
    host.querySelectorAll('[data-session-tab]').forEach(btn=>btn.addEventListener('click',()=>{manualTab=btn.dataset.sessionTab;paint()}));
    const old=document.getElementById('session-analysis');if(old)old.remove();
  }
  async function refreshData(d){
    if(d)dashboard=d;
    const t=Date.now();
    const [p,s]=await Promise.all([
      fetch('data/premarket.json?t='+t,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('data/session-analyses.json?t='+t,{cache:'no-store'}).then(r=>r.ok?r.json():{records:{}}).catch(()=>({records:{}}))
    ]);
    premarketData=p;sessionData=s||{records:{}};paint();
  }
  window.NasDecodeSessionTabs={render:refreshData,select:key=>{manualTab=key;paint()},followTime:()=>{manualTab=null;paint()}};
  const boot=()=>refreshData(window.currentDashboard||null);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
  setInterval(()=>{if(!manualTab)paint()},60000);
})();
