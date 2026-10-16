#!/usr/bin/env node
/* Run WaveTrend browser module against actual published data with minimal DOM.
   This catches runtime failures that node --check alone cannot detect. */
'use strict';
const fs=require('fs');
const vm=require('vm');
const assert=require('assert');

const fixture=JSON.parse(fs.readFileSync('public/data/nvda-wavetrend.json','utf8'));
const nodes={};
function node(name) { if(!nodes[name])nodes[name]={innerHTML:'',textContent:'',dataset:{},classList:{toggle(){}},setAttribute(){}};return nodes[name] }
const buttons=['4h','8h'].map(x=>({dataset:{ndWtTf:x},classList:{toggle(){}},setAttribute(){}}));
const root={querySelector:n=>node(n),querySelectorAll:n=>n==='[data-nd-wt-tf]'?buttons:[]};
const doc={getElementById:id=>id==='nd-wave-trend'?root:null,
  addEventListener(){},hidden:false};
let fetched=false;
const context={document:doc,window:{},console,Date,Intl,Number,String,Math,
  setInterval(){},fetch:async()=>{fetched=true;return {ok:true,json:async()=>fixture}}};
vm.runInNewContext(fs.readFileSync('public/nvda-wavetrend.js','utf8'),context);
(async()=>{
    await context.window.NDWaveTrend.load();
    assert(fetched,'data not fetched');
    assert(node('.nd-wt-panels').innerHTML.includes('4H Momentum'),'momentum panels missing');
    assert(node('.nd-wt-chart').innerHTML.includes('<svg'),'oscillator SVG missing');
    assert(!node('.nd-wt-alignment').textContent.includes('Loading'),'alignment stuck loading');
    assert(node('.nd-wt-interpretation').textContent.length>20,'interpretation missing');
    assert(node('.nd-wt-freshness').textContent.includes('ET'),'freshness missing');
    console.log('NVDA WT end-to-end browser initialization passed');
})().catch(e=>{console.error('NVDA WT initialization failed:',e.stack||e);process.exitCode=1});
