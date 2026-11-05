const frame=document.getElementById('concept-atlas'),loading=document.getElementById('atlas-loading');
const modeButtons=[...document.querySelectorAll('[data-mode]')],guideToggle=document.getElementById('guide-toggle'),manualTools=document.getElementById('explore-tools');
const initialConcept=new URLSearchParams(location.search).get('concept');
let associationsReady=false,atlasReady=false,activeStory=0,lastAppliedStory=-1,guidedEnabled=!initialConcept,pendingOutcomeShortcut=null,overviewSettled=false,heldGraphScroll=null,gateAdjusting=false,storyCompleted=false;
let storyWheelLocked=!initialConcept;
const storySteps=[...document.querySelectorAll('.story-step')];
// Phones use one caption below the network; original steps remain scroll triggers.
const phoneStory=matchMedia('(max-width: 850px)'),mobileCaption=document.createElement('section');
mobileCaption.id='mobile-story-caption';mobileCaption.className='mobile-story-caption story-step-copy';mobileCaption.setAttribute('aria-label','Current story');
(document.querySelector('.network-controls')||frame).after(mobileCaption);
function syncMobileCaption(){
 mobileCaption.setAttribute('aria-hidden',String(!phoneStory.matches));
 if(!phoneStory.matches)return;
 const step=storySteps[activeStory];mobileCaption.innerHTML=step.querySelector('.story-step-copy').innerHTML;
 mobileCaption.style.setProperty('--story-accent',step.style.getPropertyValue('--story-accent'));mobileCaption.scrollTop=0;
}
phoneStory.addEventListener('change',syncMobileCaption);

function send(message){frame.contentWindow?.postMessage(message,'*')}
function syncMode(mode){modeButtons.forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.mode===mode)))}
function resumeStoryScroll(){
 if(!storyWheelLocked||storyCompleted||guidedEnabled)return;
 const url=new URL(location.href);url.searchParams.delete('concept');history.replaceState(null,'',url);
 setGuided(true);
}
function setGuided(enabled,revealTools=false){
 if(enabled)storyWheelLocked=true;else if(storyCompleted)storyWheelLocked=false;
 const replay=enabled&&storyCompleted;
 if(replay){storyCompleted=false;delete storyShell.dataset.completed;activeStory=0;lastAppliedStory=-1;markStory(0)}
 guidedEnabled=enabled;if(!enabled)heldGraphScroll=null;guideToggle.textContent=enabled?'Explore freely':storyCompleted?'Replay story':'Resume scroll guide';guideToggle.setAttribute('aria-pressed',String(!enabled));
 document.getElementById('atlas').dataset.manual=String(!enabled);send({type:'glyph:guided-mode',enabled,storyScroll:storyWheelLocked});
 if(!enabled&&revealTools)manualTools.open=true;
 if(enabled){manualTools.open=false;lastAppliedStory=-1;applyStory()}
 if(replay)window.scrollTo({top:scrollY+storyShell.getBoundingClientRect().top-94,behavior:'instant'});
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
function needsGraphHold(target){return !storyCompleted&&guidedEnabled&&atlasReady&&associationsReady&&!overviewSettled&&target>graphReleaseY()}
function finishStory(){
 if(storyCompleted)return;
 // Anchor the following content while removing the finished tour's scroll space.
 const anchor=document.getElementById('timelines'),before=anchor.getBoundingClientRect().top;
 storyCompleted=true;heldGraphScroll=null;setGuided(false);
 storyShell.dataset.completed='true';guideToggle.textContent='Replay story';
 window.scrollBy({top:anchor.getBoundingClientRect().top-before,behavior:'instant'});
 updateStoryProgress();
}
function storyFocusPositions(){
 const positions=storySteps.map(step=>{const box=step.getBoundingClientRect();return scrollY+box.top+box.height/2-innerHeight/2});
 positions[positions.length-1]=Math.min(positions[positions.length-1],graphReleaseY()-Math.min(220,innerHeight*.2));
 return positions;
}
function scrollWithGraphGate(delta){
 if(delta<0){heldGraphScroll=null;window.scrollBy({top:delta,behavior:'instant'});return false}
 const target=(heldGraphScroll??scrollY)+delta;
 if(needsGraphHold(target)){
  heldGraphScroll=Math.min(target,document.documentElement.scrollHeight-innerHeight);
  window.scrollTo({top:graphReleaseY(),behavior:'instant'});updateStoryProgress();return true;
 }
 window.scrollBy({top:delta,behavior:'instant'});return false;
}
addEventListener('wheel',event=>{
 if(event.deltaY<0)heldGraphScroll=null;
 if(event.ctrlKey||event.metaKey||event.deltaY===0)return;
 const unit=event.deltaMode===1?16:event.deltaMode===2?innerHeight:1;
 const delta=event.deltaY*unit;
 if(event.target.closest?.('dialog,input,textarea,select,.manual-options,#atlas-search-results'))return;
 resumeStoryScroll();
 if(needsGraphHold((heldGraphScroll??scrollY)+delta)){
  // Nested controls and dialogs retain their native scrolling.
  if(event.target.closest?.('dialog,input,textarea,select,.manual-options,#atlas-search-results'))return;
  event.preventDefault();scrollWithGraphGate(delta);
 }
},{passive:false});
addEventListener('touchmove',event=>{if(!event.target.closest?.('dialog,input,textarea,select,.manual-options,#mobile-story-caption'))resumeStoryScroll()},{passive:true});
addEventListener('keydown',event=>{
 if(['ArrowUp','PageUp','Home'].includes(event.key))heldGraphScroll=null;
 if(['ArrowUp','ArrowDown','PageUp','PageDown','Home','End',' '].includes(event.key)&&!event.target.closest?.('input,textarea,select,[contenteditable=true],dialog'))resumeStoryScroll();
});
// Also cover keyboard, touch momentum and scrollbar overshoots.
let lastPageScrollY=scrollY;
addEventListener('scroll',()=>{
 const movingUp=scrollY<lastPageScrollY;lastPageScrollY=scrollY;
 if(movingUp){heldGraphScroll=null;return;}
 if(!storyCompleted&&atlasReady&&associationsReady&&scrollY>graphReleaseY()+2&&(!guidedEnabled||(overviewSettled&&activeStory===storySteps.length-1))){finishStory();return}
 if(gateAdjusting||!needsGraphHold(scrollY))return;
 heldGraphScroll=Math.max(heldGraphScroll??0,scrollY);gateAdjusting=true;
 window.scrollTo({top:graphReleaseY(),behavior:'instant'});updateStoryProgress();
 requestAnimationFrame(()=>gateAdjusting=false);
},{passive:true});
// Integrated smooth resistance: linear through the focus, gently released at its edges.
function focusResistance(distance,span,strength){
 if(span<=0)return 0;
 const sign=Math.sign(distance),d=Math.abs(distance),core=span*.75,shoulder=span-core;
 const t=Math.max(0,Math.min(1,(d-core)/shoulder));
 const resisted=d<=core?d:core+shoulder*(t-t*t*t+.5*t*t*t*t);
 return sign*strength*resisted;
}
function updateStoryProgress(){
 if(storyProgressFrame!==null)cancelAnimationFrame(storyProgressFrame);
 storyProgressFrame=null;const bounds=storyShell.getBoundingClientRect();
 const progress=storyCompleted?1:Math.max(0,Math.min(1,(innerHeight*.4-bounds.top)/Math.max(1,bounds.height-innerHeight*.6)));
 document.getElementById('story-progress-fill').style.transform=`scaleX(${progress})`;
 if(guidedEnabled&&atlasReady&&associationsReady){
  const anchor=innerHeight*.5,centers=storySteps.map(step=>{const box=step.getBoundingClientRect();return box.top+box.height*.5});
  // Each desktop focus occupies nearly a viewport of real scroll distance.
  // Let the text and camera keep moving, at a slower rate near the center.
  const halfHold=phoneStory.matches?0:innerHeight*.45;
  storySteps.forEach((step,index)=>{
   const offset=index===storySteps.length-1?0:focusResistance(anchor-centers[index],halfHold,.7);
   step.style.setProperty('--story-focus-offset',offset+'px');
  });
  // Finish the pullback before the sticky map reaches its release edge.
  const visual=document.querySelector('.story-visual'),stickyTop=parseFloat(getComputedStyle(visual).top)||0;
  const finishBeforeRelease=Math.min(220,innerHeight*.2);
  centers[centers.length-1]=Math.min(centers[centers.length-1],bounds.bottom-visual.getBoundingClientRect().height-stickyTop-finishBeforeRelease+anchor);

  let segment=0;while(segment<centers.length-2&&anchor>centers[segment+1])segment++;
  const distance=Math.max(1,centers[segment+1]-centers[segment]);
  const traveled=Math.max(0,Math.min(distance,anchor-centers[segment]));
  const slowStart=Math.min(halfHold,distance*.4),slowEnd=segment+1===storySteps.length-1?0:slowStart;
  const startLoss=focusResistance(traveled,slowStart,.82);
  const endLoss=focusResistance(distance,slowEnd,.82)-focusResistance(distance-traveled,slowEnd,.82);
  const fullTravel=distance-focusResistance(distance,slowStart,.82)-focusResistance(distance,slowEnd,.82);
  const phase=Math.max(0,Math.min(1,(traveled-startLoss-endLoss)/Math.max(1,fullTravel)));
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
 // Use fresh geometry rather than stale ratios from different observer updates.
 const stops=storyFocusPositions();
 const candidates=storySteps.map((step,index)=>{const box=step.getBoundingClientRect();return {index,visible:box.bottom>innerHeight*.12&&box.top<innerHeight*.82,distance:Math.abs(stops[index]-scrollY)}}).filter(item=>item.visible).sort((a,b)=>a.distance-b.distance);
 if(candidates.length)markStory(candidates[0].index);
},{rootMargin:'-12% 0px -18% 0px',threshold:[0,.15,.3,.5,.7,.9,1]});
storySteps.forEach(step=>storyObserver.observe(step));markStory(0);
guideToggle.addEventListener('click',()=>setGuided(!guidedEnabled));
modeButtons.forEach(button=>button.addEventListener('click',()=>{setGuided(false);syncMode(button.dataset.mode);send({type:'glyph:color',mode:button.dataset.mode});manualTools.open=false}));
document.getElementById('choose-diseases').addEventListener('click',()=>{setGuided(false);syncMode('outcome');send({type:'glyph:outcomes'})});
document.getElementById('toggle-regions').addEventListener('click',event=>{const visible=event.currentTarget.getAttribute('aria-pressed')!=='true';event.currentTarget.setAttribute('aria-pressed',String(visible));send({type:'glyph:regions',visible});manualTools.open=false});
frame.addEventListener('load',()=>{loading.hidden=true;atlasReady=true;send({type:'glyph:guided-mode',enabled:guidedEnabled,storyScroll:storyWheelLocked});if(initialConcept)send({type:'glyph:concept',concept:initialConcept});applyStory()});
window.addEventListener('message',event=>{
 if(event.source!==frame.contentWindow)return;const message=event.data;if(!message||typeof message!=='object')return;
 if(message.type==='glyph:scroll'&&(guidedEnabled||storyWheelLocked)){resumeStoryScroll();const unit=message.deltaMode===1?16:message.deltaMode===2?innerHeight:1;scrollWithGraphGate(message.deltaY*unit);return}
 if(message.type==='glyph:resume-story'){resumeStoryScroll();return}
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
  atlasReady=true;loading.hidden=true;send({type:'glyph:guided-mode',enabled:guidedEnabled,storyScroll:storyWheelLocked});if(initialConcept)send({type:'glyph:concept',concept:initialConcept});applyOutcomeShortcut();applyStory();
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
 for(const match of matches){const button=document.createElement('button');button.type='button';button.textContent=match.code+(match.text?' · '+match.text:'');button.onclick=()=>{atlasSearch.value='';atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false');send({type:'glyph:search',query:''});send({type:'glyph:concept',concept:match.code})};atlasResults.appendChild(button)}
 if(!matches.length&&atlasSearch.value.trim())atlasResults.textContent='No matching concepts';
 atlasResults.hidden=!atlasSearch.value.trim();atlasSearch.setAttribute('aria-expanded',String(!atlasResults.hidden));
});
document.addEventListener('click',event=>{if(!event.target.closest('.atlas-search-wrap')){atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false')}});
atlasSearch.addEventListener('keydown',event=>{if(event.key==='Escape'){atlasResults.hidden=true;atlasSearch.setAttribute('aria-expanded','false')}if(event.key==='ArrowDown'){event.preventDefault();atlasResults.querySelector('button')?.focus()}});
