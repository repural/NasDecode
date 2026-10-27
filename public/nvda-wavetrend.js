/* NasDecode research-only NVDA and SOXL WaveTrend display. Never modifies score calculations. */
(function(){
  'use strict';
  function createWidget(symbol, rootId){
  const state={data:null,timeframe:'4h',loading:null};
  const safe=(value)=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fixed=(n,d=1)=>Number.isFinite(Number(n))?Number(n).toFixed(d):'—';
  const date=(s,withTime=false)=>{
    const d=new Date(s);
    return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',
      month:'short',day:'numeric',...(withTime?{hour:'numeric',minute:'2-digit',hour12:true}:{})}).format(d):'—';
  };
  const condition=(x)=>!x?'Unavailable':Number(x.wt1)>Number(x.wt2)?'Bullish':'Bearish';
  const tone=(x)=>condition(x)==='Bullish'?'positive':'negative';
  function developing(tf){
    const p=state.data?.timeframes?.[tf]?.developing, now=Date.now();
    if(!p||p.isConfirmed!==false||!Number.isFinite(p.wt1)||!Number.isFinite(p.wt2))return null;
    const start=Date.parse(p.startET),end=Date.parse(p.endET),asOf=Date.parse(p.asOfET);
    return start<=asOf&&asOf<=now&&start<=now&&now<end&&now-asOf<=30*60*1000?p:null;
  }
  function panel(tf){
    const d=state.data?.timeframes?.[tf];
    if(!d||!d.latest)return '<div class="nd-wt-panel"><b>'+tf.toUpperCase()+' Momentum</b><span class="nd-wt-wait">Historical data unavailable</span></div>';
    const preview=developing(tf),p=preview||d.latest, c=d.lastCross, direction=condition(p),positive=direction==='Bullish';
    return '<div class="nd-wt-panel"><div class="nd-wt-panel-head"><b>'+tf.toUpperCase()+' Momentum</b><span class="'+(positive?'nd-wt-up':'nd-wt-down')+'">'+(positive?'↗':'↘')+'</span></div>'+
      '<strong class="'+(positive?'nd-wt-up':'nd-wt-down')+'">'+direction+(preview?' <small class="nd-wt-developing-label">Developing</small>':'')+'</strong>'+
      '<div class="nd-wt-pair"><span>WT1 / WT2'+(preview?' · Developing':' · Confirmed')+'</span><b>'+fixed(p.wt1)+' / '+fixed(p.wt2)+'</b></div>'+
      (preview?'<div class="nd-wt-development">As of '+date(p.asOfET,true)+' ET · '+(p.potentialCross?'Potential '+(p.potentialCross==='bullish'?'green':'red')+' crossover':'No potential crossover')+'<br>Last confirmed: '+condition(d.latest)+' · WT1 / WT2 '+fixed(d.latest.wt1)+' / '+fixed(d.latest.wt2)+'</div>':'')+
      '<div class="nd-wt-cross"><small>LAST CONFIRMED CROSS</small><b class="'+(c?.direction==='bullish'?'nd-wt-up':'nd-wt-down')+'">'+
      (c?.direction==='bullish'?'↗ Green':c?.direction==='bearish'?'↘ Red':'None')+' · '+date(c?.confirmedAtET||c?.endET,true)+' ET'+'</b>'+
      '<span>'+symbol+' close: '+(c?.close!=null?'$'+fixed(c.close,2):'—')+'</span></div></div>';
  }
  function path(candles,key,xMin,yTop,width,height){
    return candles.map((c,i)=>{const v=Number(c[key]);return (i?'L':'M')+(xMin+i*width/(candles.length-1)).toFixed(2)+','+(yTop+(100-v)/200*height).toFixed(2)}).join(' ');
  }
  function graph(){
    // One replaceable developing point; confirmed history never changes in-browser.
    const data=state.data?.timeframes?.[state.timeframe],preview=developing(state.timeframe);
    const confirmed=data?.candles?.slice(preview?-31:-32);
    const candles=confirmed?.concat(preview?[preview]:[]);
    if(!candles?.length)return '<p class="nd-wt-wait">No historical oscillator candles available.</p>';
    const x0=44,y0=15,w=695,h=180,y=(v)=>y0+(100-v)/200*h;
    const x=(i)=>x0+i*w/(candles.length-1);
    const levels=[60,53,0,-53,-60].map(v=>'<line x1="'+x0+'" x2="'+(x0+w)+'" y1="'+y(v)+'" y2="'+y(v)+'" stroke="'+(v===0?'#586069':'#343940')+'" stroke-dasharray="'+(v===0?'none':'4 5')+'" opacity=".8"/>'+
       ([60,0,-60].includes(v)?'<text x="37" y="'+(y(v)+4)+'" fill="#929aa4" font-size="11" text-anchor="end">'+(v>0?'+':'')+v+'</text>':'')).join('');
    const tickIndices=[...new Set([0,8,16,24,candles.length-1].filter(i=>i<candles.length))];
    const ticks=tickIndices.map((i,n)=>{
      const candle=candles[i],label=date(candle.isConfirmed===false?candle.asOfET:candle.endET,candle.isConfirmed===false||state.timeframe==='4h');
      return '<text x="'+x(i)+'" y="225" text-anchor="'+(n===0?'start':n===tickIndices.length-1?'end':'middle')+'" fill="#a0a8b1" font-size="11">'+safe(label)+'</text>';
    }).join('');
    const dividers=candles.map((v,i)=>i>0&&v.startET.slice(0,10)!==candles[i-1].startET.slice(0,10)?
      '<line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+y0+'" y2="'+(y0+h)+'" stroke="#41464c" stroke-dasharray="2 5" opacity=".52"/>':'').join('');
    const marks=candles.map((c,i)=>{
      if(c.isConfirmed===false||!c.cross)return '';
      const positive=c.cross==='bullish',v=Number(c.wt1);
      return '<circle cx="'+x(i)+'" cy="'+y(v)+'" r="4.5" fill="#121518" stroke="'+(positive?'#34d399':'#fb7185')+'" stroke-width="2"/>';
    }).join('');
    const touch=candles.map((c,i)=>'<rect x="'+(x(i)-w/(candles.length-1)/2)+'" y="'+y0+'" width="'+(w/(candles.length-1))+'" height="'+h+'" fill="transparent"><title>'+
      safe('Candle '+date(c.startET,true)+' to '+date(c.endET,true)+' ET | '+(c.provider||'Massive')+(c.isConfirmed===false?' | Developing, as of '+date(c.asOfET,true)+' ET; may change':' | Confirmed on close')+' | WT1 '+fixed(c.wt1,2)+' | WT2 '+fixed(c.wt2,2)+(c.isConfirmed===false&&c.potentialCross?' | Potential '+c.potentialCross+' crossover':c.cross?' | '+c.cross+' crossover':''))+'</title></rect>').join('');
    const solidWidth=w*(confirmed.length-1)/(candles.length-1);
    const pending=preview?['wt1','wt2'].map((key,i)=>'<path class="nd-wt-developing-path" d="M'+x(confirmed.length-1).toFixed(2)+','+y(confirmed[confirmed.length-1][key]).toFixed(2)+' L'+x(candles.length-1).toFixed(2)+','+y(preview[key]).toFixed(2)+'" stroke="'+(i?'#fb7185':'#34d399')+'" fill="none" stroke-width="2.5" stroke-dasharray="5 4"/>').join('')+
      '<circle class="nd-wt-developing-point" cx="'+x(candles.length-1)+'" cy="'+y(preview.wt1)+'" r="5" fill="none" stroke="#fbbf24" stroke-width="2" stroke-dasharray="2 2"/>':'';
    return '<svg class="nd-wt-plot" role="img" aria-label="'+symbol+' WaveTrend '+state.timeframe.toUpperCase()+' oscillator; green WT1, red WT2, confirmed bullish and bearish crossovers'+(preview?'; dashed unconfirmed developing preview':'')+'" viewBox="0 0 760 239" preserveAspectRatio="xMidYMid meet">'+
      levels+dividers+'<path d="'+path(confirmed,'wt1',x0,y0,solidWidth,h)+'" stroke="#34d399" fill="none" stroke-width="2.5" stroke-linejoin="round"/>'+
      '<path d="'+path(confirmed,'wt2',x0,y0,solidWidth,h)+'" stroke="#fb7185" fill="none" stroke-width="2.5" stroke-linejoin="round"/>'+
      marks+pending+ticks+touch+'</svg>'+(preview?'<p class="nd-wt-development">Dashed: developing '+state.timeframe.toUpperCase()+' candle · As of '+date(preview.asOfET,true)+' ET · '+(preview.potentialCross?'Potential '+(preview.potentialCross==='bullish'?'green':'red')+' crossover':'Unconfirmed WT values')+' · May change before close.</p>':'');
  }
  function interpretation(){
    const a=state.data?.timeframes?.['4h']?.latest,b=state.data?.timeframes?.['8h']?.latest;
    if(!a||!b)return 'Waiting for independently published WaveTrend research.';
    if(state.data.interpretation)return state.data.interpretation;
    const four=condition(a),eight=condition(b);
    if(four===eight)return 'Both timeframes are '+four.toLowerCase()+' (WT1 '+(four==='Bullish'?'above':'below')+' WT2). '+
      (four==='Bearish'?'A confirmed green crossover would be needed before 4H turns bullish.':'A confirmed red crossover would signal 4H momentum weakening.');
    return four==='Bullish'?'4H momentum has turned bullish while the 8H trend remains bearish — a recovery attempt, not full alignment.':
      '4H momentum has turned bearish while the 8H trend remains bullish — near-term momentum weakening.';
  }
  function backtest(){
    const report=state.data?.backtest;
    if(!report)return '<p class="nd-wt-wait">Historical simulation unavailable.</p>';
    const money=n=>'$'+new Intl.NumberFormat('en-US',{maximumFractionDigits:0}).format(n);
    const pct=n=>(n>0?'+':'')+fixed(n,2)+'%';
    const metrics=(n,value)=>'<td class="'+(n>=0?'nd-wt-up':'nd-wt-down')+'"><b>'+pct(n)+'</b><small>'+money(value)+'</small></td>';
    const rows=['4h','8h'].map(tf=>{
      const r=report.timeframes[tf];
      return '<tr><th scope="row">'+tf.toUpperCase()+' WT<small>'+r.zeroCosts.numberOfExecutions+' executions</small></th>'+['zeroCosts','cost10bps','cost25bps'].map(k=>metrics(r[k].returnPct,r[k].finalValue)).join('')+'</tr>';
    }).join('');
    const hold=report.timeframes['4h'].zeroCosts;
    return '<div class="nd-wt-history-head"><b>Historical strategy comparison</b><span>2026 YTD · $10,000 initial</span></div>'+
      '<p class="nd-wt-history-note">Through '+date(hold.lastCandleCloseET,true)+' ET. Buy-and-hold: <b>'+pct(hold.buyAndHoldReturnPct)+' · '+money(hold.buyAndHoldValue)+'</b>.</p>'+
      '<div class="nd-wt-table-wrap"><table class="nd-wt-table"><thead><tr><th>Strategy</th><th>No costs</th><th>0.10% / trade</th><th>0.25% / trade</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
      '<p class="nd-wt-history-note">Return and ending value. Green cross → buy; red cross → cash, at the next candle open. Current simulation positions: 4H '+safe(hold.finalPosition)+'; 8H '+safe(report.timeframes['8h'].zeroCosts.finalPosition)+'.</p>'+
      '<details class="nd-wt-method"><summary>Method and limitations</summary><p>'+safe(report.assumptions)+' '+safe(report.limitations)+'</p></details>';
  }
  function update(){
    const root=document.getElementById(rootId);
    if(!root)return;
    const existing=root.querySelector('.nd-wt-panels');
    if(existing)existing.innerHTML=panel('4h')+panel('8h');
    const graphNode=root.querySelector('.nd-wt-chart');
    if(graphNode)graphNode.innerHTML=graph();
    const status=root.querySelector('.nd-wt-alignment'),a=state.data?.timeframes?.['4h']?.latest,b=state.data?.timeframes?.['8h']?.latest;
    if(status)status.textContent=a&&b?'Confirmed: '+(condition(a)===condition(b)?condition(a)+' alignment':'Mixed momentum'):'Research unavailable';
    const analysis=root.querySelector('.nd-wt-interpretation');
    if(analysis)analysis.textContent=(developing('4h')||developing('8h')?'Confirmed candles: ':'')+interpretation();
    const history=root.querySelector('.nd-wt-backtest');
    if(history)history.innerHTML=backtest();
    const freshness=root.querySelector('.nd-wt-freshness');
    if(freshness){
      const end=state.data?.timeframes?.['4h']?.latest?.endET;
      const end8=state.data?.timeframes?.['8h']?.latest?.endET;
      const last=end&&end8&&new Date(end)<new Date(end8)?end:end8||end;
      const ageHours=last?(Date.now()-new Date(last).getTime())/3600000:Infinity;
      const status=Number.isFinite(ageHours)&&ageHours>=0?(ageHours>36?'Older completed candles':'Completed candles'):'Historical data';
      const source=state.data?.displaySource||'Massive';
      const checked=state.data?.collectionCheckedAtET;
      const health=state.data?.collectionStatus==='yahoo_fetch_failed'?' · Yahoo fetch failed; retaining last complete candles':'';
      freshness.textContent=last?source+' · '+status+' · Last confirmed 4H '+date(end,true)+' ET · 8H '+date(end8,true)+' ET'+(checked?' · Checked '+date(checked,true)+' ET':'')+health:'Research feed unavailable';
    }
    root.querySelectorAll('[data-nd-wt-tf]').forEach(btn=>{
      btn.setAttribute('aria-pressed',String(btn.dataset.ndWtTf===state.timeframe));
      btn.classList.toggle('active',btn.dataset.ndWtTf===state.timeframe);
    });
  }
  async function load(){
    if(!document.getElementById(rootId))return;
    if(state.loading)return state.loading;
    state.loading=(async()=>{
      try{
        const response=await fetch('data/'+symbol.toLowerCase()+'-wavetrend.json?t='+Date.now(),{cache:'no-store'});
        if(!response.ok)throw Error('HTTP '+response.status);
        const data=await response.json();
        if(data.symbol!==symbol||!data.timeframes?.['4h']?.candles?.length||!data.timeframes?.['8h']?.candles?.length)throw Error('Unexpected WaveTrend schema');
        state.data=data;
      }catch(error){console.warn(symbol+' WaveTrend research unavailable:',error)}
      update();
    })();
    try{await state.loading}finally{state.loading=null}
  }
  document.addEventListener('click',e=>{
    const btn=e.target.closest('[data-nd-wt-tf]');
    if(!btn||!btn.closest('#'+rootId))return;
    state.timeframe=btn.dataset.ndWtTf;
    // The selector affects only the oscillator and selected button.
    const root=document.getElementById(rootId);
    root.querySelector('.nd-wt-chart').innerHTML=graph();
    root.querySelectorAll('[data-nd-wt-tf]').forEach(b=>{b.classList.toggle('active',b===btn);b.setAttribute('aria-pressed',String(b===btn))});
  });
  // Re-fetch on an independent cadence even when the main dashboard snapshot does not change.
  // Developing points expire at their scheduled close and are never confirmed signals.
  setInterval(()=>{if(!document.hidden && document.getElementById(rootId))load()},5*60*1000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden && document.getElementById(rootId))load()});
  return {load,update};
  }
  const widgets=[createWidget('NVDA','nd-wave-trend'),createWidget('SOXL','nd-soxl-wave-trend')];
  window.NDWaveTrend={load:()=>Promise.all(widgets.map(w=>w.load())),update:()=>widgets.forEach(w=>w.update())};
})();
