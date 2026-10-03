(()=>{
  const stages=[
    ['early_market','Early Market','10:30 ET'],
    ['mid_market','Mid-Market','13:00 ET'],
    ['near_close','Near-Close','15:30 ET']
  ];
  const etDate=()=>{
    const parts=new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());
    const get=t=>parts.find(x=>x.type===t)?.value;
    return `${get('year')}-${get('month')}-${get('day')}`;
  };
  const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const metricRe=/\b(NasDecode Score|Consolidation Risk|Opportunity Score|Macro Data Impulse|Semiconductor Leadership|Mega-cap Leadership|Earnings AVWAP Leadership|S&P 500 50D Breadth|Nasdaq(?:-100| 100)?|SOXX|SOX|SMH|Semiconductor(?:s)?|Mega-cap(?:s)?|Market breadth|Breadth|VIX volatility|VIX|VXN|10Y Treasury(?: Yield)?|2Y Treasury(?: Yield)?|Treasury yields?|Treasuries|Fed(?: expectations)?|Federal Reserve|Options positioning|WTI|Brent|Oil|Core CPI|CPI|Core PCE|PCE|Payrolls?|Nonfarm payrolls?|Unemployment|Wages?|Average Hourly Earnings|ISM(?: Manufacturing| Services)?|PMI|Retail Sales|GDP)\b/gi;
  const analysisText=s=>esc(s).replace(metricRe,'<span class="analysis-metric">$1</span>');
  function installStyle(){
    if(document.getElementById('session-analysis-style'))return;
    const s=document.createElement('style');s.id='session-analysis-style';s.textContent=`
      .session-analysis{margin:14px 0 24px;background:var(--card);border:1px solid var(--line);padding:20px;border-radius:12px}
      .session-analysis-head{display:flex;justify-content:space-between;gap:14px;align-items:end;margin-bottom:14px;flex-wrap:wrap}
      .session-analysis-head h2{margin:0}.session-analysis-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}
      .session-analysis-card{border:1px solid var(--line);background:#091626;border-radius:11px;padding:14px;min-width:0}
      .session-analysis-card h3{margin:0 0 4px;font-size:15px}.session-analysis-time{font-size:11px;color:var(--muted);margin-bottom:10px}
      .session-analysis-metrics{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:9px}.session-pill{border:1px solid #29415e;background:#10233a;border-radius:999px;padding:5px 8px;font-size:11px;font-weight:750}
      .session-analysis-card p{color:#e5edf7;line-height:1.52;margin:8px 0;font-size:13px}.session-analysis-card .analysis-metric{color:#65b9ff;font-weight:750}.session-analysis-empty{color:var(--muted);line-height:1.45}
      @media(max-width:900px){.session-analysis-grid{grid-template-columns:1fr}}`;
    document.head.appendChild(s);
  }
  function metric(label,v,suffix=''){
    return v===null||v===undefined?'':`<span class="session-pill">${esc(label)} ${esc(v)}${suffix}</span>`;
  }
  function render(data){
    installStyle();
    const day=etDate();
    const rec=(data?.records||{})[day]||{};
    let host=document.getElementById('session-analysis');
    if(!host){
      host=document.createElement('section');host.id='session-analysis';host.className='session-analysis';
      const pre=document.querySelector('.premarket');
      if(pre&&pre.parentNode)pre.insertAdjacentElement('afterend',host);
      else (document.querySelector('.wrap')||document.body).appendChild(host);
    }
    const cards=stages.map(([key,label,time])=>{
      const a=rec[key];
      if(!a)return `<article class="session-analysis-card"><h3>${label}</h3><div class="session-analysis-time">${time}</div><div class="session-analysis-empty">Scheduled analysis will appear here after the checkpoint is captured.</div></article>`;
      const metrics=[metric('Score',a.nasdaqScore),metric('Nasdaq',a.nasdaqChangePct,'%'),metric('Risk',a.consolidationRisk),metric('Opportunity',a.opportunityScore)].join('');
      const ps=(a.paragraphs||[]).map(p=>`<p>${analysisText(p)}</p>`).join('');
      return `<article class="session-analysis-card"><h3>${esc(a.label||label)}</h3><div class="session-analysis-time">${esc(a.scheduledET||time)} · captured ${esc((a.capturedET||'').replace('T',' ').slice(0,16))} ET</div><div class="session-analysis-metrics">${metrics}</div>${ps}</article>`;
    }).join('');
    host.innerHTML=`<div class="session-analysis-head"><div><div class="section-kicker">Session evolution</div><h2>Intraday Analysis</h2></div><div class="muted">Early → Mid-Market → Near-Close</div></div><div class="session-analysis-grid">${cards}</div>`;
  }
  async function load(){
    try{const r=await fetch(`data/session-analyses.json?t=${Date.now()}`,{cache:'no-store'});if(r.ok)render(await r.json());else render({});}
    catch(e){render({});}
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',load);else load();
})();
