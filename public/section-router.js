(()=>{'use strict';
const pages={overview:'Overview',macro:'Macro / Rates',internals:'Market Internals',assessment:'Assessment',analysis:'Analysis',watch:'Open Watch'};
const requested=new URLSearchParams(location.search).get('view')||'overview';
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
     group=t.includes('macro')?'macro':t.includes('internals')?'internals':t.includes('assessment')?'assessment':'';
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
html[data-nd-page="overview"] #factorCards,
html[data-nd-page="overview"] #premarket,
html[data-nd-page="overview"] .signal-details,
html[data-nd-page="overview"] #marketMovingDevelopments{display:none!important}
html[data-nd-page="macro"] #factorCards > :not([data-nd-section="macro"]),
html[data-nd-page="internals"] #factorCards > :not([data-nd-section="internals"]),
html[data-nd-page="assessment"] #factorCards > :not([data-nd-section="assessment"]){display:none!important}
html[data-nd-page="macro"] #premarket,html[data-nd-page="macro"] .signal-details,html[data-nd-page="macro"] #marketSetup,html[data-nd-page="macro"] .lower-intel,html[data-nd-page="macro"] #marketMovingDevelopments,
html[data-nd-page="internals"] #premarket,html[data-nd-page="internals"] .signal-details,html[data-nd-page="internals"] #marketSetup,html[data-nd-page="internals"] .lower-intel,html[data-nd-page="internals"] #marketMovingDevelopments,
html[data-nd-page="assessment"] #premarket,html[data-nd-page="assessment"] .lower-intel,html[data-nd-page="assessment"] #marketMovingDevelopments,
html[data-nd-page="analysis"] #factorCards,html[data-nd-page="analysis"] .signal-details,html[data-nd-page="analysis"] #marketSetup,html[data-nd-page="analysis"] .lower-intel,html[data-nd-page="analysis"] #marketMovingDevelopments,
html[data-nd-page="watch"] #factorCards,html[data-nd-page="watch"] #premarket,html[data-nd-page="watch"] .signal-details,html[data-nd-page="watch"] #marketSetup{display:none!important}
html[data-nd-page="overview"] .lower-intel{margin-top:18px}
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
})();