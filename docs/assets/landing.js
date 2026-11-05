const frame=document.getElementById('concept-atlas'),loading=document.getElementById('atlas-loading');
const modeButtons=[...document.querySelectorAll('[data-mode]')],guideToggle=document.getElementById('guide-toggle'),manualTools=document.getElementById('explore-tools');
const initialConcept=new URLSearchParams(location.search).get('concept');
let associationsReady=false,atlasReady=false,activeStory=0,lastAppliedStory=-1,guidedEnabled=!initialConcept,pendingOutcomeShortcut=null,overviewSettled=false,heldGraphScroll=null,gateAdjusting=false;
const storySteps=[...document.querySelectorAll('.story-step')];
// Phones use one caption below the network; original steps remain scroll triggers.
const phoneStory=matchMedia('(max-width: 850px)'),mobileCaption=document.createElement('section');
mobileCaption.id='mobile-story-caption';mobileCaption.className='mobile-story-caption story-step-copy';mobileCaption.setAttribute('aria-label','Current story');
frame.after(mobileCaption);
function syncMobileCaption(){
 mobileCaption.setAttribute('aria-hidden',String(!phoneStory.matches));
 if(!phoneStory.matches)return;
 const step=storySteps[activeStory];mobileCaption.innerHTML=step.querySelector('.story-step-copy').innerHTML;
 mobileCaption.style.setProperty('--story-accent',step.style.getPropertyValue('--story-accent'));mobileCaption.scrollTop=0;
}
phoneStory.addEventListener('change',syncMobileCaption);

function send(message){frame.contentWindow?.postMessage(message,'*')}
function syncMode(mode){modeButtons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)))}
function setGuided(enabled,revealTools=false){
 guidedEnabled=enabled;if(!enabled)heldGraphScroll=null;guideToggle.textContent=enabled?'Explore freely':'Resume scroll guide';guideToggle.setAttribute('aria-pressed',String(!enabled));
 document.getElementById('atlas').dataset.manual=String(!enabled);send({type:'glyph:guided-mode',enabled});
 if(!enabled&&revealTools)manualTools.open=true;
 if(enabled){manualTools.open=false;lastAppliedStory=-1;applyStory()}
}
function updateDiseaseHeading(label){
 const lower=label.toLowerCase();
 const pretty=label==='Cancer Liver Primary'?'Primary liver cancer':label.endsWith('(428.4)')||lower.includes('heart failure with preserved ef')?'Heart failure (HFpEF)':label.endsWith('(585.33)')||lower.includes('chronic kidney disease, stage iii')?'Kidney disease':label;
 document.getElementById('active-disease').textContent=pretty;document.getElementById('manual-disease').textContent=pretty;
 document.getElementById('show-liver-cancer').setAttribute('aria-pressed',String(pretty==='Primary liver cancer'));
 document.getElementById('show-cardiac').setAttribute('aria-pressed',String(pretty==='Heart failure (HFpEF)'));
 document.getElementById('show-renal').setAttribute('aria-pressed',String(pretty==='Kidney disease'));
}
function applyOutcomeShortcut(){
 if(!pendingOutcomeShortcut||!atlasReady||!associationsReady)return;
 const action=pendingOutcomeShortcut;pendingOutcomeShortcut=null;
 const presets={liver:['Cancer Liver Primary','Primary liver cancer'],cardiac:['428.4','Heart failure (HFpEF)'],renal:['585.33','Kidney disease']};
 if(presets[action]){const [outcome,label]=presets[action];send({type:'glyph:select-outcome',outcome});updateDiseaseHeading(label)}
 else send({type:'glyph:outcomes'});
}
function openOutcomeShortcut(action){
 setGuided(false);manualTools.open=false;pendingOutcomeShortcut=action;
 applyOutcomeShortcut();
}
document.getElementById('show-liver-cancer').addEventListener('click',()=>openOutcomeShortcut('liver'));
document.getElementById('show-cardiac').addEventListener('click',()=>openOutcomeShortcut('cardiac'));
document.getElementById('show-renal').addEventListener('click',()=>openOutcomeShortcut('renal'));
document.getElementById('show-all-outcomes').addEventListener('click',()=>openOutcomeShortcut('all'));
const storyShell=document.querySelector('.story-shell');let storyProgressFrame=null;
function graphReleaseY(){
 const visual=document.querySelector('.story-visual'),bounds=storyShell.getBoundingClientRect();
 const stickyTop=parseFloat(getComputedStyle(visual).top)||0;
 return Math.floor(Math.max(0,scrollY+bounds.bottom-visual.getBoundingClientRect().height-stickyTop));
}
function needsGraphHold(target){return guidedEnabled&&atlasReady&&associationsReady&&!overviewSettled&&target>graphReleaseY()}
function scrollWithGraphGate(delta){
 if(delta<0)heldGraphScroll=null;
 const target=(heldGraphScroll??scrollY)+delta;
 if(needsGraphHold(target)){
  heldGraphScroll=Math.min(target,document.documentElement.scrollHeight-innerHeight);
  window.scrollTo({top:graphReleaseY(),behavior:'instant'});updateStoryProgress();return true;
 }
 window.scrollBy({top:delta,behavior:'instant'});return false;
}
addEventListener('wheel',event=>{
 if(event.deltaY<0){heldGraphScroll=null;return}
 if(event.ctrlKey||event.metaKey||event.deltaY===0)return;
 const unit=event.deltaMode===1?16:event.deltaMode===2?innerHeight:1;
 if(needsGraphHold((heldGraphScroll??scrollY)+event.deltaY*unit)){event.preventDefault();scrollWithGraphGate(event.deltaY*unit)}
},{passive:false});
addEventListener('keydown',event=>{if(['ArrowUp','PageUp','Home'].includes(event.key))heldGraphScroll=null});
// Also cover keyboard, touch momentum and scrollbar overshoots.
addEventListener('scroll',()=>{
 if(gateAdjusting||!needsGraphHold(scrollY))return;
 heldGraphScroll=Math.max(heldGraphScroll??0,scrollY);gateAdjusting=true;
 window.scrollTo({top:graphReleaseY(),behavior:'instant'});updateStoryProgress();
 requestAnimationFrame(()=>gateAdjusting=false);
},{passive:true});
function updateStoryProgress(){
 storyProgressFrame=null;const bounds=storyShell.getBoundingClientRect();
 const progress=Math.max(0,Math.min(1,(innerHeight*.4-bounds.top)/Math.max(1,bounds.height-innerHeight*.6)));
 document.getElementById('story-progress-fill').style.transform=`scaleX(${progress})`;
 if(guidedEnabled&&atlasReady&&associationsReady){
  const anchor=innerHeight*.5,centers=storySteps.map(step=>{const box=step.getBoundingClientRect();return box.top+box.height*.5});
  // Finish the pullback before the sticky map reaches its release edge.
  const visual=document.querySelector('.story-visual'),stickyTop=parseFloat(getComputedStyle(visual).top)||0;
  const finishBeforeRelease=Math.min(220,innerHeight*.2);
  centers[centers.length-1]=Math.min(centers[centers.length-1],bounds.bottom-visual.getBoundingClientRect().height-stickyTop-finishBeforeRelease+anchor);

  let segment=0;while(segment<centers.length-2&&anchor>centers[segment+1])segment++;
  const phase=Math.max(0,Math.min(1,(anchor-centers[segment])/(centers[segment+1]-centers[segment])));
  send({type:'glyph:scroll-camera',from:storySteps[segment].dataset.concept||null,to:storySteps[segment+1].dataset.concept||null,progress:phase});
 }

}
addEventListener('scroll',()=>{if(storyProgressFrame===null)storyProgressFrame=requestAnimationFrame(updateStoryProgress)},{passive:true});
addEventListener('resize',updateStoryProgress);updateStoryProgress();
function applyStory(){
 if(!atlasReady||!associationsReady||!guidedEnabled||lastAppliedStory===activeStory)return;
 const step=storySteps[activeStory];lastAppliedStory=activeStory;
 send({type:'glyph:story',outcome:step.dataset.outcome,outcomes:step.dataset.outcomes?step.dataset.outcomes.split('|'):null,concept:step.dataset.concept||null,related:step.dataset.related?step.dataset.related.split(','):[],scrollDriven:true});
 updateDiseaseHeading(step.dataset.disease);updateStoryProgress();
}
function markStory(index){
 const changed=activeStory!==index;activeStory=index;storySteps.forEach((step,i)=>step.classList.toggle('is-active',i===index));if(changed||!mobileCaption.childElementCount)syncMobileCaption();applyStory();
}
const storyObserver=new IntersectionObserver(entries=>{
 for(const entry of entries)entry.target.dataset.visibility=String(entry.isIntersecting?entry.intersectionRatio:0);
 const visible=storySteps.map((step,index)=>({index,ratio:Number(step.dataset.visibility||0)})).filter(item=>item.ratio>0).sort((a,b)=>b.ratio-a.ratio);
 if(visible.length)markStory(visible[0].index);
},{rootMargin:'-12% 0px -18% 0px',threshold:[0,.15,.3,.5,.7,.9,1]});
storySteps.forEach(step=>storyObserver.observe(step));markStory(0);
guideToggle.addEventListener('click',()=>setGuided(!guidedEnabled));
modeButtons.forEach(button=>button.addEventListener('click',()=>{setGuided(false);syncMode(button.dataset.mode);send({type:'glyph:color',mode:button.dataset.mode});manualTools.open=false}));
document.getElementById('choose-diseases').addEventListener('click',()=>{setGuided(false);syncMode('outcome');send({type:'glyph:outcomes'})});
document.getElementById('toggle-regions').addEventListener('click',event=>{const visible=event.currentTarget.getAttribute('aria-pressed')!=='true';event.currentTarget.setAttribute('aria-pressed',String(visible));send({type:'glyph:regions',visible});manualTools.open=false});
frame.addEventListener('load',()=>{loading.hidden=true;atlasReady=true;send({type:'glyph:guided-mode',enabled:guidedEnabled});if(initialConcept)send({type:'glyph:concept',concept:initialConcept});applyStory()});
window.addEventListener('message',event=>{
 if(event.source!==frame.contentWindow)return;const message=event.data;if(!message||typeof message!=='object')return;
 if(message.type==='glyph:scroll'&&guidedEnabled){const unit=message.deltaMode===1?16:message.deltaMode===2?innerHeight:1;scrollWithGraphGate(message.deltaY*unit);return}
 if(message.type==='glyph:manual'){setGuided(false);return}
 if(message.type==='glyph:camera-state'){
  overviewSettled=!!message.overviewSettled;
  if(overviewSettled&&heldGraphScroll!==null){const destination=heldGraphScroll;heldGraphScroll=null;window.scrollTo({top:destination,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'})}
 }

 if(typeof message.associationsReady==='boolean'){
  associationsReady=message.associationsReady;document.getElementById('mode-outcome').disabled=!associationsReady;document.getElementById('choose-diseases').disabled=!associationsReady;
  if(associationsReady){applyOutcomeShortcut();applyStory()}
 }
 if(message.type==='glyph:ready'){
  atlasReady=true;loading.hidden=true;send({type:'glyph:guided-mode',enabled:guidedEnabled});if(initialConcept)send({type:'glyph:concept',concept:initialConcept});applyOutcomeShortcut();applyStory();
 }
 if(message.type==='glyph:regions-state')document.getElementById('toggle-regions').setAttribute('aria-pressed',String(message.regionsVisible));
 if(Number.isInteger(message.selectedOutcomes))document.querySelector('.count-chip').textContent=message.selectedOutcomes+'/141';
 if(message.type==='glyph:state'||message.type==='glyph:ready'||message.type==='glyph:selection')syncMode(message.colorMode);
 if(message.outcomeLabel&&!(guidedEnabled&&message.guided))updateDiseaseHeading(message.outcomeLabel);
 if(message.type==='glyph:selection'){
  frame.dataset.selected=String(message.sidebarOpen||!!message.concept);
  if(!message.guided){const url=new URL(location.href);if(typeof message.concept==='string'&&message.concept.length<100)url.searchParams.set('concept',message.concept);else url.searchParams.delete('concept');history.replaceState(null,'',url)}
 }
});
if(initialConcept)setGuided(false);

const atlasSearch=document.getElementById('atlas-search'),atlasResults=document.getElementById('atlas-search-results');
atlasSearch.addEventListener('input',()=>{setGuided(false);send({type:'glyph:search',query:atlasSearch.value})});
document.getElementById('atlas-reset').onclick=()=>{setGuided(false);atlasSearch.value='';atlasResults.hidden=true;send({type:'glyph:reset'})};
// Keep help available when the static timeline builder replaces the dialog block.
if(!document.getElementById('atlas-help-dialog')){
 const dialog=document.createElement('dialog');dialog.id='atlas-help-dialog';dialog.setAttribute('aria-labelledby','atlas-help-title');
 dialog.innerHTML='<button id="atlas-help-close" type="button" aria-label="Close help">×</button><h2 id="atlas-help-title">Explore the concept space</h2><p>Choose a disease to highlight concepts associated with higher risk (OR &gt; 1).</p><p>Search by concept code or description. Click any dot for its interpretation, association wheel, odds ratios, and p-values.</p><p>Drag to pan, and use + and − to zoom. Reset view returns to the full map. Resume scroll guide restarts the guided exploration.</p>';
 document.body.appendChild(dialog);
}
document.getElementById('atlas-help').onclick=()=>{document.getElementById('atlas-help-dialog').showModal()};
document.getElementById('atlas-help-close').onclick=()=>document.getElementById('atlas-help-dialog').close();
window.addEventListener('message',event=>{
 if(event.source!==frame.contentWindow||event.data?.type!=='glyph:search-results')return;
 atlasResults.replaceChildren();const matches=event.data.matches||[];
 for(const match of matches){const button=document.createElement('button');button.type='button';button.textContent=match.code+' · '+match.text;button.onclick=()=>{atlasSearch.value='';atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false');send({type:'glyph:search',query:''});send({type:'glyph:concept',concept:match.code})};atlasResults.appendChild(button)}
 if(!matches.length&&atlasSearch.value.trim())atlasResults.textContent='No matching concepts';
 atlasResults.hidden=!atlasSearch.value.trim();atlasSearch.setAttribute('aria-expanded',String(!atlasResults.hidden));
});
document.addEventListener('click',event=>{if(!event.target.closest('.atlas-search-wrap')){atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false')}});
atlasSearch.addEventListener('keydown',event=>{if(event.key==='Escape'){atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false')}if(event.key==='ArrowDown'){event.preventDefault();atlasResults.querySelector('button')?.focus()}});
