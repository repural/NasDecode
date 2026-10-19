'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const fixtures=Object.fromEntries(['NVDA','SOXL'].map(s=>[s,JSON.parse(fs.readFileSync('public/data/'+s.toLowerCase()+'-wavetrend.json'))]));
const listeners={},roots={};
for(const id of ['nd-wave-trend','nd-soxl-wave-trend']){
  const nodes={};
  const buttons=['4h','8h'].map(tf=>({dataset:{ndWtTf:tf},classList:{toggle(){}},setAttribute(){},closest:selector=>selector==='#'+id?roots[id]:null}));
  roots[id]={nodes,buttons,querySelector:n=>nodes[n]||(nodes[n]={innerHTML:'',textContent:''}),querySelectorAll:()=>buttons};
}
const context={window:{},console,Date,Intl,Number,String,Math,setInterval(){},
  document:{hidden:false,getElementById:id=>roots[id],addEventListener:(name,fn)=>(listeners[name]||(listeners[name]=[])).push(fn)},
  fetch:async url=>({ok:true,json:async()=>fixtures[url.includes('soxl')?'SOXL':'NVDA']})};
vm.runInNewContext(fs.readFileSync('public/nvda-wavetrend.js','utf8'),context);
(async()=>{
  await context.window.NDWaveTrend.load();
  const nvda=roots['nd-wave-trend'],soxl=roots['nd-soxl-wave-trend'];
  assert(nvda.nodes['.nd-wt-panels'].innerHTML.includes('NVDA close'));
  assert(soxl.nodes['.nd-wt-panels'].innerHTML.includes('SOXL close'));
  assert(soxl.nodes['.nd-wt-backtest'].innerHTML.includes('0.25% / trade'));
  assert(soxl.nodes['.nd-wt-interpretation'].textContent===fixtures.SOXL.interpretation);
  const previous=nvda.nodes['.nd-wt-chart'].innerHTML;
  for(const fn of listeners.click)fn({target:{closest:()=>soxl.buttons[1]}});
  assert(soxl.nodes['.nd-wt-chart'].innerHTML.includes('SOXL WaveTrend 8H'));
  assert.equal(nvda.nodes['.nd-wt-chart'].innerHTML,previous,'SOXL selector changed NVDA chart');
  console.log('Independent NVDA/SOXL widgets, analysis and backtest passed');
})().catch(e=>{console.error(e);process.exitCode=1});
