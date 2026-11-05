'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const id='nd-qqq-wave-trend',nodes={},listeners={};
const buttons=['4h','8h'].map(tf=>({dataset:{ndWtTf:tf},setAttribute(){},classList:{toggle(){}},closest:s=>s==='#'+id?root:null}));
const root={querySelector:s=>nodes[s]||(nodes[s]={innerHTML:'',textContent:''}),querySelectorAll:()=>buttons};
const bars=Array.from({length:48},(_,i)=>({startET:'2026-11-04T04:00:00-05:00',endET:'2026-11-04T08:00:00-05:00',wt1:i-20,wt2:i-21,close:600}));
const series={latest:bars[47],candles:bars,lastCross:null};
const data={symbol:'QQQ',timeframes:{'4h':series,'8h':series},movingAverages:{timeframe:'1D',price:600,sma50:580,sma200:550,distanceSMA50Pct:3.4483,distanceSMA200Pct:9.0909,throughDate:'2026-11-04'}};
const context={window:{},console,Date,Intl,Number,String,Math,setInterval(){},
 document:{hidden:false,getElementById:s=>s===id?root:null,addEventListener:(n,f)=>(listeners[n]||(listeners[n]=[])).push(f)},
 fetch:async url=>{assert(url.includes('qqq-wavetrend.json'));return {ok:true,json:async()=>data}}};
vm.runInNewContext(fs.readFileSync('public/nvda-wavetrend.js','utf8'),context);
(async()=>{
 await context.window.NDWaveTrend.load();
 assert(nodes['.nd-wt-chart'].innerHTML.includes('QQQ WaveTrend 4H'));
 assert(nodes['.nd-wt-moving-averages'].innerHTML.includes('DAILY SMA200'));
 assert(nodes['.nd-wt-moving-averages'].innerHTML.includes('$550.00'));
 assert(nodes['.nd-wt-moving-averages'].innerHTML.includes('2026-11-04'));
 for(const fn of listeners.click)fn({target:{closest:()=>buttons[1]}});
 assert(nodes['.nd-wt-chart'].innerHTML.includes('QQQ WaveTrend 8H'));
 data.movingAverages=null;await context.window.NDWaveTrend.load();
 assert(nodes['.nd-wt-moving-averages'].innerHTML.includes('unavailable'));
 const html=fs.readFileSync('index.html','utf8');
 assert(html.includes("rowCards.slice(5).join('')+qqqWaveTrendCard+"));
 console.log('QQQ Overview placement, 4H/8H selector and daily SMA display passed');
})().catch(e=>{console.error(e);process.exitCode=1});
