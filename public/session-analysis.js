(()=>{
  const stages=[
    {key:'premarket',label:'Pre-Market',time:'Before 09:30 ET'},
    {key:'early_market',label:'Early Market',time:'10:30 ET checkpoint'},
    {key:'mid_market',label:'Mid-Market',time:'13:00 ET checkpoint'},
    {key:'near_close',label:'Near-Close',time:'15:30 ET checkpoint'}
  ];
  let sessionData={records:{}}, researchData={sessions:{}}, premarketData=null, dashboard=null, manualTab=null, manualDate=null;

  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const metricRe=/\b(NasDecode Score|Consolidation Risk|Opportunity Score|SOXL Buy Score|Inflation · Labor · Growth|Semiconductor Leadership|Mega-cap Leadership|Earnings AVWAP Leadership|S&P 500 50D Breadth|Nasdaq(?:-100| 100)?|SOXX|SOX|SMH|Semiconductor(?:s)?|Mega-cap(?:s)?|Market breadth|Breadth|VIX volatility|VIX|VXN|10Y Treasury(?: Yield)?|2Y Treasury(?: Yield)?|Treasury yields?|Treasuries|Fed(?: expectations)?|Federal Reserve|Options positioning|WTI|Brent|Oil|Core CPI|CPI|Core PCE|PCE|Payrolls?|Nonfarm payrolls?|Unemployment|Wages?|Average Hourly Earnings|ISM(?: Manufacturing| Services)?|PMI|Retail Sales|GDP)\b/gi;
  const analysisText=s=>esc(s).replace(metricRe,'<span class="analysis-metric">$1</span>');

  // Escape-first Markdown renderer for published research. No raw HTML is trusted.
  const mdInline=value=>{
    const links=[];
    let raw=String(value??'').replace(/\[([^\]\n]+)\]\((https?:\/\/[^\s)]+)\)/g,(_,label,url)=>{
      const token='NDLINKTOKEN'+links.length+'END';
      links.push({label,url});return token;
    });
    let t=esc(raw).replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>').replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g,'<em>$1</em>').replace(/`([^`\n]+)`/g,'<code>$1</code>');
    t=t.replace(metricRe,'<span class="analysis-metric">$1</span>');
    return t.replace(/NDLINKTOKEN(\d+)END/g,(_,i)=>{
      const item=links[Number(i)];if(!item)return '';
      const safeUrl=/^https?:\/\//i.test(item.url)?esc(item.url):'';
      return safeUrl?'<a href="'+safeUrl+'" target="_blank" rel="noopener noreferrer">'+esc(item.label)+'</a>':esc(item.label);
    });
  };
  function researchMarkdown(value){
    const lines=String(value??'').replace(/\r\n?/g,'\n').split('\n');
    const result=[];let list='',table=[];
    const flushList=()=>{if(list){result.push('</'+list+'>');list=''}};
    const flushTable=()=>{if(!table.length)return;const rows=table.filter(x=>!/^\s*\|?\s*:?-{3,}/.test(x));if(rows.length){result.push('<div class="nd-research-table-wrap"><table class="nd-research-table">'+rows.map((line,i)=>'<tr>'+line.trim().replace(/^\||\|$/g,'').split('|').map(cell=>'<'+(i?'td':'th')+'>'+mdInline(cell.trim())+'</'+(i?'td':'th')+'>').join('')+'</tr>').join('')+'</table></div>')}table=[]};
    for(const line of lines){
      const t=line.trim();
      if(t.includes('|')&&/^\|/.test(t)){flushList();table.push(t);continue}
      flushTable();
      if(!t){flushList();continue}
      const heading=t.match(/^#{1,4}\s+(.+)$/);
      if(heading){flushList();result.push('<h4 class="nd-research-heading">'+mdInline(heading[1])+'</h4>');continue}
      const bullet=t.match(/^(?:[-*]\s+|\d+\.\s+)(.+)$/);
      if(bullet){const kind=/^\d/.test(t)?'ol':'ul';if(list!==kind){flushList();result.push('<'+kind+'>');list=kind}result.push('<li>'+mdInline(bullet[1])+'</li>');continue}
      flushList();result.push('<p>'+mdInline(t)+'</p>');
    }
    flushList();flushTable();return result.join('');
  }
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
      /* Option 2: neutral charcoal session analysis, preserving existing content and tab logic. */
      .session-tabs-shell{margin:0;background:#101113;border:1px solid #303236;border-radius:12px;padding:22px 24px}
      .session-tabs-head{display:flex;justify-content:space-between;gap:14px;align-items:end;flex-wrap:wrap;margin-bottom:20px}
      .session-tabs-head h2{margin:3px 0 0;font-size:22px;letter-spacing:-.025em;font-weight:690}
      .session-tabs-head .section-kicker{font-size:11px;letter-spacing:.15em;color:#a8adb3}
      .session-tabs-head .muted{font-size:11px;color:#9fa4ab}
      .session-tabbar{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid #34363a;border-radius:10px;overflow:hidden;background:#151719;margin-bottom:20px}
      .session-tab{appearance:none;border:0;border-right:1px solid #34363a;border-radius:0;background:#151719;color:#a8adb3;padding:13px 14px;cursor:pointer;text-align:left;font-family:inherit}
      .session-tab:last-child{border-right:0}
      .session-tab:hover{background:#202225;color:#f3f4f5}
      .session-tab.active{background:#27292c;color:#f4f5f6;box-shadow:inset 0 -2px 0 #aeb4bd}
      .session-tab:focus-visible{outline:2px solid #b6bbc2;outline-offset:-2px}
      .session-tab b{display:block;font-size:12px;font-weight:670;letter-spacing:.015em}
      .session-tab span{display:block;font-size:10px;margin-top:5px;color:inherit;opacity:.87}
      .session-tab.has-data b:after{content:' •';color:var(--green)}
      .session-tab.awaiting b:after{content:' •';color:var(--amber)}
      .session-tab-panel{border-top:1px solid #313337;padding-top:19px}
      .session-analysis-title{display:flex;justify-content:space-between;gap:16px;align-items:baseline;flex-wrap:wrap;margin-bottom:16px}
      .session-analysis-title h3{margin:0;font-size:19px;font-weight:690;letter-spacing:-.015em}
      .session-analysis-time{font-size:11px;color:#aab0b7}
      .session-analysis-metrics{display:flex;flex-wrap:wrap;gap:7px;margin:10px 0 18px}
      .session-pill{border:1px solid #373a3e;background:#1c1e20;border-radius:999px;padding:5px 10px;font-size:11px;font-weight:680;color:#e8eaed}
      .session-tab-panel p{color:#dadddf;font-size:14px;font-weight:420;line-height:1.72;margin:0 0 15px;max-width:115ch}
      .session-tab-panel .analysis-metric{color:#82cbd0;font-weight:650;text-decoration:none}

      /* Align summary metrics and editorial copy to a shared readable measure. */
      .session-tab-panel{--nd-analysis-reading-width:950px}
      .session-tab-panel .nd-analysis-summary{width:100%;max-width:var(--nd-analysis-reading-width)}
      .session-tab-panel>p,.session-tab-panel>h3,.session-tab-panel>h4,
      .session-tab-panel>ol,.session-tab-panel>ul,
      .session-tab-panel>.session-analysis-metrics,
      .session-tab-panel>.session-awaiting{max-width:var(--nd-analysis-reading-width)}
      .session-tab-panel p{max-width:var(--nd-analysis-reading-width)}
      .nd-analysis-summary-card{padding:15px 16px;gap:9px}
      @media(max-width:700px){.nd-analysis-summary-card{padding:14px 15px}}
      /* Session overview cards share the Option 2 charcoal palette. */
      .session-analysis-title h3{font-size:30px;font-weight:700;line-height:1.2;letter-spacing:-.03em}
      .nd-analysis-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:8px 0 23px}
      .nd-analysis-summary-card{min-width:0;background:#151719;border:1px solid #34373b;border-radius:11px;padding:17px 19px;display:flex;flex-direction:column;gap:12px}
      .nd-summary-label{font-size:12px;font-weight:550;letter-spacing:.015em;color:#adb3bb}
      .nd-summary-value{font-size:22px;font-weight:650;line-height:1.23;letter-spacing:-.02em;color:#f1f3f4;overflow-wrap:anywhere}
      .nd-summary-cautious .nd-summary-value{color:#f3bd55}
      .nd-summary-negative .nd-summary-value{color:#ff6078}
      .nd-summary-positive .nd-summary-value{color:#37d68b}
      @media(max-width:700px){.session-analysis-title h3{font-size:25px}.nd-analysis-summary{grid-template-columns:repeat(2,minmax(0,1fr))}.nd-analysis-summary-card{padding:14px 15px}}
      @media(max-width:440px){.nd-analysis-summary{grid-template-columns:1fr}.nd-analysis-summary-card{gap:7px}.nd-summary-value{font-size:20px}}
      .session-tab-panel .nd-research-heading{font-size:17px;font-weight:670;line-height:1.4;margin:22px 0 10px;color:#f2f3f5}
      .session-tab-panel .nd-research-table-wrap{max-width:950px;overflow-x:auto;margin:12px 0 20px;border:1px solid #373a3e;border-radius:9px}
      .session-tab-panel .nd-research-table{border-collapse:collapse;width:100%;font-size:12px;line-height:1.55}
      .session-tab-panel .nd-research-table th,.session-tab-panel .nd-research-table td{padding:10px 12px;border-bottom:1px solid #34373b;text-align:left;vertical-align:top}
      .session-tab-panel .nd-research-table th{color:#edf0f3;background:#1b1d20;font-weight:650}
      .session-tab-panel a{color:#82cbd0;text-decoration:underline;text-underline-offset:2px;overflow-wrap:anywhere}
      .session-tab-panel p{overflow-wrap:anywhere}
      .session-tab-panel .bias{font-size:17px;font-weight:590;line-height:1.45;margin:0 0 10px;color:#f3f4f5}
      .session-tab-panel h3{font-size:15px;font-weight:680;margin:22px 0 11px}
      .session-tab-panel ol{padding-left:24px;margin:0 0 18px;max-width:120ch}
      .session-tab-panel li{font-size:13px;line-height:1.58;color:#dadddf;padding-left:3px;margin:0 0 8px;font-weight:430}
      .session-tab-panel li b{font-weight:630}
      .session-awaiting{padding:18px 0;color:var(--muted);line-height:1.55}
      .session-current-note{font-size:10px;color:#e1e4e7;font-weight:650}
      /* Shared Option 2 readability and tabular market figures. */
      .session-tabs-shell,.session-tab{font-family:var(--nd-font,"Inter",ui-sans-serif,system-ui,sans-serif)}
      .session-tab span,.session-analysis-time,.session-current-note{font-size:11px;font-variant-numeric:tabular-nums}
      .session-tab b{font-size:13px}
      .session-tab-panel p{font-size:14px;line-height:1.72}
      .session-tab-panel li{font-size:14px;line-height:1.65}
      .session-pill{font-size:12px;font-variant-numeric:tabular-nums lining-nums}
      .session-tab-panel .analysis-metric{font-weight:650}
      .session-tabs-head .muted,.session-tabs-head .section-kicker{font-size:12px}
      .session-analysis-title h3{font-weight:690}

      @media(max-width:700px){
        .session-tabs-shell{padding:16px 14px}
        .session-tabbar{grid-template-columns:1fr 1fr}
        .session-tab:nth-child(2){border-right:0}
        .session-tab:nth-child(-n+2){border-bottom:1px solid #34363a}
        .session-tab{padding:12px}
        .session-tab-panel p{font-size:13px}
      }`;
    document.head.appendChild(s);
  }
  function metric(label,v,suffix=''){
    return v===null||v===undefined||v===''?'':`<span class="session-pill">${esc(label)} ${esc(v)}${suffix}</span>`;
  }
  function summaryCards(a, fallback){
    const entries=[];
    const add=(label,value,kind)=>{
      if(value===null||value===undefined||String(value).trim()==='')return;
      entries.push('<div class="nd-analysis-summary-card'+(kind?' nd-summary-'+kind:'')+'"><div class="nd-summary-label">'+esc(label)+'</div><div class="nd-summary-value">'+esc(value)+'</div></div>');
    };
    if(a&&a.bias)add('Nasdaq Bias',a.bias,/cautious|mixed|neutral/i.test(String(a.bias))?'cautious':/bearish|negative/i.test(String(a.bias))?'negative':/bullish|positive/i.test(String(a.bias))?'positive':'');
    if(a&&a.confidence)add('Confidence',a.confidence,'');
    const risk=a?.eventRisk??a?.event_risk;
    if(typeof risk==='string'||typeof risk==='number')add('Event Risk',risk,/high|elevated|severe/i.test(String(risk))?'negative':/low/i.test(String(risk))?'positive':'');
    return entries.length?'<div class="nd-analysis-summary" aria-label="Session outlook">'+entries.join('')+'</div>':(fallback||'');
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
    const bias=summaryCards(a,`<div class="nd-analysis-summary"><div class="nd-analysis-summary-card"><div class="nd-summary-label">Nasdaq Score</div><div class="nd-summary-value">${esc(sig)} · ${esc(score)} / 100</div></div></div>`);
    return {available:true,title:'Pre-Market Analysis',meta:'Analysis updated: '+esc(a.updatedET||a.updated||'—'),body:bias+(metrics?`<div class="session-analysis-metrics">${metrics}</div>`:'')+paras+(catalysts?`<h3>Major events to watch today</h3><ol>${catalysts}</ol>`:'')+watch+keyTimes};
  }
  function checkpointView(key){
    const day=manualDate||etParts().date;
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
  function researchView(key){
    const day=manualDate||etParts().date, a=researchData?.sessions?.[day]?.[key];
    if(!a || a.publicationStatus!=='published')return null;
    const def=stages.find(s=>s.key===key);
    const snapshot=sessionData?.records?.[day]?.[key];
    const checkpoint=snapshot?'<div class="session-analysis-metrics">'+[metric('Nasdaq',snapshot.nasdaqChangePct,'%'),metric('QQQ',snapshot.qqqChangePct,'%'),metric('Score',snapshot.nasdaqScore,' / 100')].join('')+'</div>':'';
    const paragraphs=Array.isArray(a.paragraphs)?a.paragraphs:[];
    const filtered=[];let suppress=false;
    for(const p of paragraphs){
      const plain=String(p||'').trim();
      if(/^#{0,4}\s*publication status\s*$/i.test(plain)){suppress=true;continue}
      if(suppress){if(/^#{1,4}\s+/.test(plain)&&!/publication status/i.test(plain))suppress=false;else continue}
      if(/^#{0,4}\s*(nasdaq bias|confidence|event risk)\s*$/i.test(plain))continue;
      if(/^\*\*(neutral|moderate|high|low|cautious|bullish|bearish)/i.test(plain)&&filtered.length<4)continue;
      filtered.push(p);
    }
    const paras=filtered.map(researchMarkdown).join('');
    // Corrupted auxiliary extracts are intentionally omitted from public output.
    // The complete, better-preserved research narrative above contains the watch items.
    const cats='',changed='',watch='';
    const time=new Date(a.updatedET).toLocaleString('en-US',{timeZone:'America/New_York',month:'short',day:'numeric',hour:'numeric',minute:'2-digit',timeZoneName:'short'});
    return {available:true,title:def.label+' Analysis',meta:'Research updated '+esc(time),body:summaryCards(a)+checkpoint+paras+changed+(cats?'<h3>Major Catalysts</h3><ol>'+cats+'</ol>':'')+(watch?'<h3>What to Watch</h3>'+watch:'')};
  }
  function viewFor(key){const research=researchView(key);if(research)return research;if(key==='premarket')return premarketView();const def=stages.find(s=>s.key===key);const day=manualDate||etParts().date;const state=researchData?.sessions?.[day]?.[key]?.publicationStatus||'missing';return {available:false,title:def.label+' Analysis',meta:'Research '+state,body:'<div class="session-awaiting">Independent research '+(state==='failed'?'publication failed.':state==='pending'?'is pending.':'has not been published for this session.')+'</div>'}}
  function paint(){
    installStyle();
    const host=document.getElementById('premarket');if(!host)return;
    host.className='premarket session-tabs-shell';
    const auto=automaticTab(), selected=manualTab||auto, view=viewFor(selected);
    const dates=Object.keys(researchData?.sessions||{}).sort().reverse();
    const dateSelector=dates.length?'<label class="session-analysis-time">Research date <select id="session-research-date" aria-label="Research date"><option value="">Today</option>'+dates.filter(x=>x!==etParts().date).map(x=>'<option value="'+esc(x)+'" '+(manualDate===x?'selected':'')+'>'+esc(x)+'</option>').join('')+'</select></label>':'';
    const tabs=stages.map(s=>{
      const v=viewFor(s.key), cls=['session-tab',s.key===selected?'active':'',v.available?'has-data':'awaiting'].filter(Boolean).join(' ');
      const current=s.key===auto?'<span class="session-current-note">Current window</span>':'';
      return `<button type="button" class="${cls}" data-session-tab="${s.key}" aria-selected="${s.key===selected?'true':'false'}"><b>${esc(s.label)}</b><span>${esc(s.time)}</span>${current}</button>`;
    }).join('');
    host.innerHTML=`<div class="session-tabs-head"><div><div class="section-kicker">Session analysis</div><h2>NasDecode Analysis</h2></div><div class="muted">Automatically follows New York market time · click any tab to review</div>${dateSelector}</div><div class="session-tabbar" role="tablist">${tabs}</div><div class="session-tab-panel" role="tabpanel"><div class="session-analysis-title"><h3>${esc(view.title)}</h3><div class="session-analysis-time">${view.meta}</div></div>${view.body}</div>`;
    host.querySelectorAll('[data-session-tab]').forEach(btn=>btn.addEventListener('click',()=>{manualTab=btn.dataset.sessionTab;paint()}));
    host.querySelector('#session-research-date')?.addEventListener('change',e=>{manualDate=e.target.value||null;paint()});
    const old=document.getElementById('session-analysis');if(old)old.remove();
  }
  async function refreshData(d){
    if(d)dashboard=d;
    const t=Date.now();
    const [p,s,r]=await Promise.all([
      fetch('data/premarket.json?t='+t,{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
      fetch('data/session-analyses.json?t='+t,{cache:'no-store'}).then(r=>r.ok?r.json():{records:{}}).catch(()=>({records:{}})),
      fetch('data/session-research.json?t='+t,{cache:'no-store'}).then(r=>r.ok?r.json():{sessions:{}}).catch(()=>({sessions:{}}))
    ]);
    premarketData=p;sessionData=s||{records:{}};researchData=r||{sessions:{}};paint();
  }
  window.NasDecodeSessionTabs={render:refreshData,select:key=>{manualTab=key;paint()},followTime:()=>{manualTab=null;paint()}};
  const boot=()=>refreshData(window.currentDashboard||null);
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot);else boot();
  setInterval(()=>{if(!manualTab)paint()},60000);
})();
