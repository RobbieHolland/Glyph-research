// Research-site adapter around Glyph's reusable standalone explorer.
// Coordinates and edges are immutable exports; all interactions are display-only.
let sidebarOpened=false;
document.body.classList.toggle('standalone-atlas',window.parent===window);
const outcomeFamily=new Map();Object.entries(DATA.outcome_groups).forEach(([g,names])=>names.forEach(n=>outcomeFamily.set(n,g)));
const familyColor=g=>{const name=DATA.outcome_groups[g]?.[0];return name?outcomeColor(name):'#8a8a85'};
const originalLegend=updateLegend;
updateLegend=function(){
 if(colorMode==='modality'){
  document.getElementById('legend').innerHTML='<b>Data modalities</b><br>'+DATA.modalities.map(m=>`<span class="legend-item"><span class="dot" style="background:${modalityColor(m)}"></span>${escapeHTML(m)}</span>`).join('')+'<span class="legend-sub">Original paper layout · node size reflects activation frequency</span>';
 }else{
  const families=[...new Set([...selected].map(o=>outcomeFamily.get(o)))].filter(Boolean);
  document.getElementById('legend').innerHTML=`<b>${selected.size===1?escapeHTML([...selected][0].replace(/\s*\([^)]*\)$/,'')):'Disease associations'}</b><br>`+families.map(g=>`<span class="legend-item"><span class="dot" style="background:${familyColor(g)}"></span>${escapeHTML(g)}</span>`).join('')+'<span class="legend-sub">Disease family sets the hue · darker = higher OR · gray = no significant higher-risk association</span>';
  const outcome=selected.size===1?[...selected][0]:null;
  const limit=outcome?associationStrengthLimit(outcome):0;
  const sign=1;
  const hue=outcome&&limit?associationStrengthColor({outcome,odds_ratio:Math.exp(sign*limit)}):'#404040';
  const scale=document.createElement('div');scale.className='strength-key';
  const labels=outcome&&limit?[0,1/3,2/3,1].map((t,i)=>(i===0?'OR ':'')+formatOR(Math.exp(sign*limit*t))):['OR 1','Strongest per outcome'];
  scale.innerHTML=`<div class="strength-gradient" style="background:linear-gradient(to right,#fff,${hue})"></div><div class="strength-ticks">${labels.map(t=>`<span>${t}</span>`).join('')}</div><div class="legend-sub">Scaled separately for each outcome</div>`;
  document.getElementById('legend').appendChild(scale);

 }
};
const originalDrawNode=drawNode;
drawNode=function(n){
 originalDrawNode(n);
 const style=n.paper_style;
 if(!style)return;
 // Render the original SVG markers, including dashed undocumented concepts.
 n.outline.style.stroke=colorMode==='modality'?style.stroke:'#1f1f1f';
 n.outline.style.strokeWidth=style.stroke_width;
 n.outline.style.strokeOpacity=style.stroke_opacity;
 n.outline.style.strokeDasharray=style.dasharray;
 n.outline.style.vectorEffect='none';
 if(colorMode==='modality') [...n.el.children].forEach(c=>{
  if(c!==n.outline)c.setAttribute('fill-opacity',style.fill_opacity);
 });
};
const paperEdges=new Map((DATA.paper_edges||[]).map(e=>[[e.a,e.b].sort((a,b)=>a-b).join(':'),e]));
edgeLayer.querySelectorAll('.edge').forEach(el=>{
 const style=paperEdges.get([+el.dataset.a,+el.dataset.b].sort((a,b)=>a-b).join(':'));
 if(!style)return;
 // Keep paper edge weights, with a screen-space minimum for readability.
 el.style.stroke='#808080';el.setAttribute('stroke-width',Math.max(.65,style.width*.75));
 el.setAttribute('stroke-opacity',.38);el.style.vectorEffect='non-scaling-stroke';
});
if(DATA.paper_node_order)nodeLayer.replaceChildren(
 ...DATA.paper_node_order.map(i=>DATA.nodes[i].el),...DATA.nodes.map(n=>n.hit));
// Collapsible outcome families retain the existing checkbox behavior.
const outcomeRows=new Map([...choices.querySelectorAll('label')].map(row=>[row.querySelector('input').value,row]));
choices.replaceChildren();
const outcomeGroups=[];
function makeOutcomeGroup(name,outcomes){
 const group=document.createElement('details');group.className='outcome-group';
 const heading=document.createElement('summary'),dot=document.createElement('i'),title=document.createElement('span'),count=document.createElement('span');
 dot.className='dot';dot.style.background=familyColor(name);title.textContent=name;
 count.className='outcome-group-count';heading.append(dot,title,count);
 const rows=document.createElement('div');rows.className='outcome-group-rows';
 outcomes.forEach(outcome=>{const row=outcomeRows.get(outcome);if(row)rows.appendChild(row)});
 group.append(heading,rows);choices.appendChild(group);
 outcomeGroups.push({group,name,count,rows,outcomes});
}
Object.entries(DATA.outcome_groups).forEach(([name,outcomes])=>makeOutcomeGroup(name,outcomes));
const other=DATA.outcomes.filter(o=>!outcomeGroups.some(g=>g.outcomes.includes(o)));
if(other.length)makeOutcomeGroup('Other outcomes',other);
function updateGroupCounts(){outcomeGroups.forEach(({group,name,count,outcomes})=>{
 const number=outcomes.filter(o=>selected.has(o)).length;
 count.textContent=`${number}/${outcomes.length}`;
 group.querySelector('summary').setAttribute('aria-label',`${name}: ${number} of ${outcomes.length} selected`);
})}
const sourceUpdateSummary=updateSummary;
updateSummary=function(){sourceUpdateSummary();updateGroupCounts()};
updateGroupCounts();
const groupActions=document.createElement('div');groupActions.className='group-actions';
[['Expand groups',true],['Collapse groups',false]].forEach(([text,open])=>{
 const button=document.createElement('button');button.type='button';button.textContent=text;
 button.onclick=()=>outcomeGroups.forEach(({group})=>{group.open=open});groupActions.appendChild(button);
});
choices.before(groupActions);
const noOutcomes=document.createElement('p');noOutcomes.className='outcome-empty';noOutcomes.textContent='No matching outcomes.';noOutcomes.hidden=true;choices.after(noOutcomes);
let groupSearchActive=false;const groupOpenBeforeSearch=new Map();
document.getElementById('outcomeSearch').oninput=e=>{
 const query=e.target.value.trim().toLowerCase();
 if(query&&!groupSearchActive)outcomeGroups.forEach(({group})=>groupOpenBeforeSearch.set(group,group.open));
 let visible=0;
 outcomeGroups.forEach(({group,name,rows})=>{
  const familyMatches=name.toLowerCase().includes(query);let matches=0;
  [...rows.children].forEach(row=>{row.hidden=!!query&&!familyMatches&&!row.textContent.toLowerCase().includes(query);if(!row.hidden)matches++});
  group.hidden=!matches;visible+=matches;
  if(query)group.open=!!matches;
  else if(groupSearchActive)group.open=groupOpenBeforeSearch.get(group)||false;
 });
 groupSearchActive=!!query;noOutcomes.hidden=visible>0;
};

function notifyParent(type='glyph:state',extra={}){if(window.parent!==window)window.parent.postMessage({type,colorMode,selectedOutcomes:selected.size,sidebarOpen:sidebarOpened,guided:!!DATA.guided_mode,outcomeLabel:selected.size===1?[...selected][0].replace(/\s*\([^)]*\)$/, ''):selected.size?'Selected diseases':'Choose a disease',...extra},'*')}
function chooseColor(mode){
 const radio=document.querySelector(`input[name="colorMode"][value="${mode}"]`);
 if(!radio)return;radio.checked=true;radio.onchange();notifyParent();
}
const selectedConceptMarker=document.createElementNS(NS,'g');selectedConceptMarker.id='selectedConceptMarker';selectedConceptMarker.setAttribute('pointer-events','none');camera.appendChild(selectedConceptMarker);
const storyContextMarkers=document.createElementNS(NS,'g');storyContextMarkers.id='storyContextMarkers';storyContextMarkers.setAttribute('pointer-events','none');camera.appendChild(storyContextMarkers);
function updateStoryContext(n){
 storyContextMarkers.replaceChildren();if(!n||!DATA.guided_mode)return;
 for(const name of DATA.story_related||[]){
  const related=DATA.nodes.find(node=>node.name===name);if(!related||related===n)continue;
  related.el.style.opacity='1';
  const x=related.x*S,y=related.y*S,r=radius(related)+6/scale;
  const ring=circle(x,y,r,'none');ring.setAttribute('stroke',modalityColor(related.modality));ring.setAttribute('stroke-width','2');ring.setAttribute('vector-effect','non-scaling-stroke');
  const labelY=y-r-8/scale,width=52/scale,height=24/scale;
  const background=document.createElementNS(NS,'rect');background.setAttribute('x',x-width/2);background.setAttribute('y',labelY-18/scale);background.setAttribute('width',width);background.setAttribute('height',height);background.setAttribute('rx',3/scale);background.setAttribute('fill','#fff');background.setAttribute('fill-opacity','.93');
  const label=document.createElementNS(NS,'text');label.setAttribute('x',x);label.setAttribute('y',labelY);label.setAttribute('text-anchor','middle');label.setAttribute('font-size',20/scale);label.setAttribute('font-weight','650');label.setAttribute('fill',related.modality==='Radiology reports'?'#b85c00':modalityColor(related.modality));label.textContent=related.name;
  const group=document.createElementNS(NS,'g');group.dataset.relatedConcept=name;group.append(ring,background,label);storyContextMarkers.appendChild(group);
 }
}
function updateConceptMarker(n){
 updateStoryContext(n);selectedConceptMarker.replaceChildren();selectedConceptMarker.style.display=n?'':'none';if(!n)return;
 const x=n.x*S,y=n.y*S,r=radius(n)+8/scale;
 for(const [stroke,width] of [['#fff',6],['#171717',2.5]]){
  const ring=circle(x,y,r,'none');ring.setAttribute('stroke',stroke);ring.setAttribute('stroke-width',width);ring.setAttribute('vector-effect','non-scaling-stroke');selectedConceptMarker.appendChild(ring);
 }
 const yLabel=y-r-12/scale,width=(n.name.length*11+14)/scale,height=25/scale;
 const background=document.createElementNS(NS,'rect');background.setAttribute('x',x-width/2);background.setAttribute('y',yLabel-18/scale);background.setAttribute('width',width);background.setAttribute('height',height);background.setAttribute('rx',4/scale);background.setAttribute('fill','#fff');
 const text=document.createElementNS(NS,'text');text.setAttribute('x',x);text.setAttribute('y',yLabel);text.setAttribute('text-anchor','middle');text.setAttribute('font-size',18/scale);text.setAttribute('font-weight','700');text.setAttribute('fill',modalityColor(n.modality));text.textContent=n.name;
 selectedConceptMarker.append(background,text);selectedConceptMarker.dataset.concept=n.name;
}
let associationListConcept=null,associationListExpanded=false;
function compactOutcomeAssociations(){
 const identifier=selectedNode?.concept_id??selectedNode?.name??null;
 if(identifier!==associationListConcept){associationListConcept=identifier;associationListExpanded=false}
 const detail=document.getElementById('detail'),table=detail.querySelector('table.assoc');if(!table)return;
 const allowed=new Set((A[selectedNode.i]||[]).filter(a=>a.odds_ratio>1).map(a=>a.outcome));
 [...table.querySelectorAll('tbody tr')].forEach(row=>{if(!allowed.has(row.querySelector('[data-outcome]')?.dataset.outcome))row.remove()});
 const noteText='Higher-risk associations (OR > 1), ordered by OR. P-values are Bonferroni-adjusted; intervals are 95% CIs. Click an outcome to highlight it.';
 if(table.previousElementSibling?.classList.contains('assoc-note'))table.previousElementSibling.textContent=noteText;
 const rows=[...table.querySelectorAll('tbody tr')];if(rows.length<=3)return;
 const body=table.querySelector('tbody');body.id='outcome-association-rows';
 const button=document.createElement('button');button.type='button';button.id='association-more';button.className='association-more';button.setAttribute('aria-controls',body.id);
 const note=table.previousElementSibling;
 function update(){
  rows.forEach((row,index)=>row.hidden=!associationListExpanded&&index>=3);
  button.textContent=associationListExpanded?'Show less':`Show more (${rows.length-3})`;
  button.setAttribute('aria-expanded',String(associationListExpanded));
  if(note?.classList.contains('assoc-note'))note.textContent=`${associationListExpanded?'All higher-risk outcomes':'Top three higher-risk outcomes'} by OR. P-values are Bonferroni-adjusted; intervals are 95% CIs. Click an outcome to highlight it.`;
 }
 button.onclick=()=>{associationListExpanded=!associationListExpanded;update()};
 table.after(button);update();
}
const sourceRenderSelected=renderSelected;
renderSelected=function(){sourceRenderSelected();compactOutcomeAssociations();updateConceptMarker(selectedNode);sidebarOpened=sidebarOpened||!!selectedNode;document.getElementById('app').classList.toggle('has-selection',sidebarOpened);const exportButton=document.getElementById('exportConcept');if(exportButton)exportButton.disabled=!!(DATA.progressive_associations&&!selectedNode?.associations_ready)};
let cameraTravelFrame=null,scrollCameraFrame=null,scrollCameraTarget=null,scrollCameraLastTime=0;
function cancelGuidedCamera(){if(cameraTravelFrame!==null)cancelAnimationFrame(cameraTravelFrame);if(scrollCameraFrame!==null)cancelAnimationFrame(scrollCameraFrame);cameraTravelFrame=null;scrollCameraFrame=null;scrollCameraTarget=null}
function travelCamera(target,duration=1050){
 cancelGuidedCamera();
 if(matchMedia('(prefers-reduced-motion: reduce)').matches){scale=target.scale;tx=target.tx;ty=target.ty;apply();updateConceptMarker(selectedNode);return}
 const initial={scale,tx,ty};
 const center=view=>({x:(S/2-view.tx)/view.scale,y:(S/2-view.ty)/view.scale});
 const firstCenter=center(initial),targetCenter=center(target);
 const changingFocus=Math.hypot(firstCenter.x-targetCenter.x,firstCenter.y-targetCenter.y)>25;
 // Between close-ups, visibly pull back to the whole map, then push into the
 // new concept. A single linear pan between equal zoom levels felt like a cut.
 const legs=initial.scale>1.15&&target.scale>1.15&&changingFocus?
  [{target:{scale:1,tx:0,ty:0},duration:650},{target:{scale:1,tx:0,ty:0},duration:100},{target,duration:950}]:
  [{target,duration}];
 let index=0,from=initial,legStart=performance.now();
 function step(now){
  const leg=legs[index],progress=Math.min(1,(now-legStart)/leg.duration);
  const ease=progress<.5?4*progress**3:1-(-2*progress+2)**3/2;
  const a=center(from),b=center(leg.target);
  scale=Math.exp(Math.log(from.scale)+(Math.log(leg.target.scale)-Math.log(from.scale))*ease);
  tx=S/2-(a.x+(b.x-a.x)*ease)*scale;ty=S/2-(a.y+(b.y-a.y)*ease)*scale;
  apply();updateConceptMarker(selectedNode);
  if(progress===1){
   scale=leg.target.scale;tx=leg.target.tx;ty=leg.target.ty;apply();
   if(++index===legs.length){cameraTravelFrame=null;return}
   from={scale,tx,ty};legStart=now;
  }
  cameraTravelFrame=requestAnimationFrame(step);
 }
 cameraTravelFrame=requestAnimationFrame(step);
}
// Scrolling defines one continuous route: overview -> close-up -> pan -> overview.
// A short follower also smooths large wheel/page-scroll jumps instead of cutting.
let lastReportedOverview=null;
function reportCameraOverview(settled){
 if(lastReportedOverview!==settled){lastReportedOverview=settled;notifyParent('glyph:camera-state',{overviewSettled:settled})}
}
let guidedPanelFraction=0,guidedPanelTarget=0,guidedPanelOwned=false;
function applyGuidedPanel(fraction){
 const app=document.getElementById('app');guidedPanelFraction=fraction;guidedPanelOwned=true;
 sidebarOpened=true;app.classList.add('has-selection');app.style.transition='none';
 if(innerWidth<=580){app.style.gridTemplateColumns='1fr';app.style.gridTemplateRows=`${100-56*fraction}% ${56*fraction}%`}
 else{const width=innerWidth>1100?420:innerWidth>850?350:270;app.style.gridTemplateColumns=`minmax(0,1fr) ${width*fraction}px`;app.style.gridTemplateRows='1fr'}
 document.getElementById('side').style.opacity=String(Math.max(0,Math.min(1,(fraction-.15)/.65)));
}
function releaseGuidedPanel(){
 if(!guidedPanelOwned)return;const app=document.getElementById('app');
 app.style.removeProperty('transition');app.style.removeProperty('grid-template-columns');app.style.removeProperty('grid-template-rows');document.getElementById('side').style.removeProperty('opacity');
 guidedPanelOwned=false;guidedPanelFraction=sidebarOpened?1:0;guidedPanelTarget=guidedPanelFraction;
}
function setScrollCamera(fromConcept,toConcept,progress){
 if(!DATA.guided_mode)return;
 if(cameraTravelFrame!==null){cancelAnimationFrame(cameraTravelFrame);cameraTravelFrame=null}
 const pose=name=>{const n=name?DATA.nodes.find(n=>n.name===name):null;return n?{scale:2.2,x:n.x*S,y:n.y*S}:{scale:1,x:S/2,y:S/2}};
 const from=pose(fromConcept),to=pose(toConcept),t=Math.max(0,Math.min(1,progress)),ease=t*t*(3-2*t);
 if(fromConcept||toConcept&&t>0){guidedPanelTarget=Math.max(guidedPanelTarget,fromConcept?1:ease);if(!guidedPanelOwned)applyGuidedPanel(guidedPanelFraction)}

 scrollCameraTarget={scale:Math.exp(Math.log(from.scale)+(Math.log(to.scale)-Math.log(from.scale))*ease),x:from.x+(to.x-from.x)*ease,y:from.y+(to.y-from.y)*ease};
 reportCameraOverview(scrollCameraTarget.scale===1&&Math.abs(scale-1)<.00015&&Math.hypot((S/2-tx)/scale-S/2,(S/2-ty)/scale-S/2)<.04);
 if(scrollCameraFrame!==null)return;
 scrollCameraLastTime=performance.now();
 function follow(now){
  if(!scrollCameraTarget||!DATA.guided_mode){scrollCameraFrame=null;return}
  const goal=scrollCameraTarget,dt=Math.max(1,Math.min(64,now-scrollCameraLastTime));scrollCameraLastTime=now;
  const blend=1-Math.exp(-dt/110),x=(S/2-tx)/scale,y=(S/2-ty)/scale;
  const nextX=x+(goal.x-x)*blend,nextY=y+(goal.y-y)*blend;
  scale=Math.exp(Math.log(scale)+(Math.log(goal.scale)-Math.log(scale))*blend);
  tx=S/2-nextX*scale;ty=S/2-nextY*scale;
  if(guidedPanelOwned&&Math.abs(guidedPanelFraction-guidedPanelTarget)>.0001)applyGuidedPanel(guidedPanelFraction+(guidedPanelTarget-guidedPanelFraction)*blend);
  apply();updateConceptMarker(selectedNode);
  if(Math.abs(Math.log(scale/goal.scale))<.00015&&Math.hypot(nextX-goal.x,nextY-goal.y)<.04&&Math.abs(guidedPanelFraction-guidedPanelTarget)<.001){
   scale=goal.scale;tx=S/2-goal.x*scale;ty=S/2-goal.y*scale;if(guidedPanelOwned)applyGuidedPanel(guidedPanelTarget);apply();updateConceptMarker(selectedNode);scrollCameraFrame=null;reportCameraOverview(goal.scale===1&&goal.x===S/2&&goal.y===S/2);
  }else scrollCameraFrame=requestAnimationFrame(follow);
 }
 scrollCameraFrame=requestAnimationFrame(follow);
}
function focusConcept(n){
 document.getElementById('search').value='';hideConceptResults();
 // Restore a visible starting point even if display filters excluded this node.
 selectedModalities.add(n.modality);selectedFamilies.add(n.embedding_family);onlySignificant=false;document.getElementById('onlySignificant').checked=false;
 facetChoices.querySelectorAll('label').forEach(row=>{if(row.textContent.trim()===n.modality||row.textContent.trim()===n.embedding_family)row.querySelector('input').checked=true});
 const target={scale:2.2,tx:S/2-n.x*S*2.2,ty:S/2-n.y*S*2.2};
 if(DATA.guided_mode){show(n);travelCamera(target)}else{cancelGuidedCamera();scale=target.scale;tx=target.tx;ty=target.ty;apply();show(n)}
}

const sourceShow=show;
show=function(n){
 if(DATA.progressive_associations&&!n.associations_ready)window.loadAssociationForNode?.(n.i);
 sourceShow(n);
 const report=document.getElementById('detail');
 const badge=document.createElement('span');badge.className='interpretation-note';badge.textContent=n.interpretation_source||'Concept interpretation';
 const heading=report.querySelector('.concept-heading');if(heading)heading.after(badge);else report.prepend(badge);
 notifyParent('glyph:selection',{concept:n.name});
};
const sourceClear=clearSelection;
clearSelection=function(){sourceClear();notifyParent('glyph:selection',{concept:null})};
document.querySelector('input[name="colorMode"][value="modality"]').checked=true;
document.querySelector('input[name="associationDirection"][value="risk"]').checked=true;
document.getElementById('colorSummary').textContent='Color: modalities';
document.getElementById('outcomeSearch').placeholder='Search diseases';
updateSummary();
document.getElementById('mapTitle').textContent='Concept details';
document.getElementById('mapMeta').textContent='';
document.getElementById('intro').innerHTML='Click a dot to view its interpretation and association wheel. Drag to pan; use + and − to zoom.<div class="try-concepts"><span class="try-label">Try a concept</span><button data-concept="I87">I87 · Hepatobiliary</button><button data-concept="I76">I76 · Bowel</button><button data-concept="L84">L84 · Renal</button></div>';
document.querySelectorAll('[data-concept]').forEach(b=>b.onclick=()=>{const n=DATA.nodes.find(n=>n.name===b.dataset.concept);if(n)show(n)});
document.getElementById('outcomeChoices').addEventListener('change',()=>chooseColor('outcome'));
['selectAllOutcomes','clearOutcomes'].forEach(id=>document.getElementById(id).addEventListener('click',()=>chooseColor('outcome')));
document.querySelectorAll('input[name="colorMode"]').forEach(r=>r.addEventListener('change',()=>notifyParent()));
document.querySelectorAll('.node-group').forEach(g=>g.style.willChange='auto');
window.addEventListener('message',event=>{
 if(event.source!==window.parent)return;
 const m=event.data;if(!m||typeof m!=='object')return;
 if(m.type==='glyph:color'&&['modality','outcome'].includes(m.mode))chooseColor(m.mode);
 if(m.type==='glyph:outcomes'){
  chooseColor('outcome');const picker=document.getElementById('outcomePicker');picker.open=!picker.open;
  if(picker.open)document.getElementById('outcomeSearch').focus();
 }
 if(m.type==='glyph:concept'&&typeof m.concept==='string'){
  const n=DATA.nodes.find(n=>n.name===m.concept);if(n){setGuidedMode(false);notifyParent('glyph:manual');focusConcept(n)}
 }
});
let applyingGuidedScene=false;
function setGuidedMode(enabled){DATA.guided_mode=enabled;if(!enabled)releaseGuidedPanel();if(!enabled&&DATA.story_related?.length){DATA.story_related=[];applyFilters()}document.body.classList.toggle('guided-view',enabled);svg.style.touchAction=enabled?'pan-y':'none'}
function beginManualExploration(){cancelGuidedCamera();if(DATA.guided_mode&&!applyingGuidedScene){setGuidedMode(false);notifyParent('glyph:manual')}}
document.addEventListener('pointerdown',event=>{if(event.pointerType!=='touch'&&event.target.closest('button,input,summary,.hit')&&!event.target.closest('#association-more'))beginManualExploration()},true);
document.addEventListener('click',event=>{if(event.target.closest('button,input,summary,.hit')&&!event.target.closest('#association-more'))beginManualExploration()},true);
document.getElementById('search').addEventListener('input',beginManualExploration);
// Reading a scrolling details panel takes manual control without moving the page.
document.getElementById('side').addEventListener('wheel',beginManualExploration,{capture:true,passive:true});
window.addEventListener('message',event=>{
 if(event.source!==window.parent)return;const m=event.data;
 if(m?.type==='glyph:guided-mode'){setGuidedMode(!!m.enabled);if(!m.enabled)cancelGuidedCamera()}
 if(m?.type==='glyph:select-outcome'){
  setGuidedMode(false);const outcome=DATA.outcomes.find(o=>o===m.outcome||o.endsWith('('+m.outcome+')'));
  if(outcome){selected.clear();selected.add(outcome);colorMode='outcome';document.querySelector('input[name="colorMode"][value="outcome"]').checked=true;syncOutcomeBoxes();clearSelection();travelCamera({scale:1,tx:0,ty:0});notifyParent()}
 }
 if(m?.type==='glyph:scroll-camera')setScrollCamera(m.from,m.to,m.progress);
 if(m?.type==='glyph:story'){
  applyingGuidedScene=true;DATA.story_related=Array.isArray(m.related)?m.related:[];setGuidedMode(true);
  const requested=Array.isArray(m.outcomes)?m.outcomes:[m.outcome];
  const outcomes=requested.map(value=>DATA.outcomes.find(o=>o===value||o.endsWith('('+value+')'))).filter(Boolean);
  if(outcomes.length){selected.clear();outcomes.forEach(outcome=>selected.add(outcome));colorMode='outcome';document.querySelector('input[name="colorMode"][value="outcome"]').checked=true;syncOutcomeBoxes();document.getElementById('colorSummary').textContent='Color: outcomes'}
  if(m.concept){const n=DATA.nodes.find(n=>n.name===m.concept);if(n){if(m.scrollDriven)show(n);else focusConcept(n)}}
  else{clearSelection();if(!m.scrollDriven)travelCamera({scale:1,tx:0,ty:0})}
  notifyParent();applyingGuidedScene=false;
 }
});
setGuidedMode(!!DATA.progressive_associations);

const queryConcept=new URLSearchParams(location.search).get('concept');
if(queryConcept){const n=DATA.nodes.find(n=>n.name===queryConcept);if(n)show(n)}
// Show explicit text-search matches as well as highlighting them on the graph.
const conceptSearch=document.getElementById('search'),conceptResults=document.createElement('div');
conceptResults.id='conceptSearchResults';conceptResults.hidden=true;conceptResults.setAttribute('role','region');conceptResults.setAttribute('aria-label','Matching concepts');
document.getElementById('stage').appendChild(conceptResults);
conceptSearch.setAttribute('aria-controls',conceptResults.id);conceptSearch.setAttribute('aria-expanded','false');
function hideConceptResults(){conceptResults.hidden=true;conceptSearch.setAttribute('aria-expanded','false')}
// Match clinical names and common aliases, and rank names ahead of incidental text matches.
const clinicalSearchAliases={patient_age:['age','patient age'],patient_sex:['sex','male','female'],current_smoker:['smoking','smoker','current smoker','current smoking'],heavy_alcohol_use:['alcohol','heavy alcohol','heavy alcohol use'],recent_bmi:['bmi','body mass index']};
const normalizeConceptQuery=value=>String(value||'').toLowerCase().replace(/[_-]+/g,' ').replace(/\s+/g,' ').trim();
function conceptSearchTerms(n){return [n.name,n.concept_id,n.wheel_label,...(clinicalSearchAliases[n.concept_id]||[])].filter(Boolean).map(normalizeConceptQuery)}
const originalNodePassesFilter=nodePassesFilter;
nodePassesFilter=function(n,q=conceptSearch.value){
 if(!originalNodePassesFilter(n,''))return false;
 q=normalizeConceptQuery(q);if(!q)return true;
 return [...conceptSearchTerms(n),normalizeConceptQuery(n.interpretation),String(n.feature_idx)].some(text=>text.includes(q));
};
function rankedConceptMatches(){
 const q=normalizeConceptQuery(conceptSearch.value);
 const rank=n=>{const terms=conceptSearchTerms(n);if(terms.includes(q))return 0;if(terms.some(term=>term.startsWith(q)))return 1;if(terms.some(term=>term.split(' ').includes(q)))return 2;return 3};
 return DATA.nodes.filter(n=>nodePassesFilter(n)).sort((a,b)=>rank(a)-rank(b));
}
function renderConceptResults(){
 const query=conceptSearch.value.trim();conceptResults.replaceChildren();if(!query){hideConceptResults();return}
 const matches=rankedConceptMatches();
 const count=document.createElement('div');count.className='concept-results-count';count.textContent=matches.length?'Matching concepts':'No matching concepts';conceptResults.appendChild(count);
 matches.slice(0,12).forEach(n=>{
  const button=document.createElement('button');button.type='button';button.className='concept-result';
  const id=document.createElement('strong'),interpretation=document.createElement('span');id.textContent=n.name;id.style.color=modalityColor(n.modality);interpretation.textContent=n.interpretation||'No interpretation available';button.append(id,interpretation);
  button.onclick=()=>{conceptSearch.value='';applyFilters();show(n);hideConceptResults()};conceptResults.appendChild(button);
 });
 if(matches.length>12){const note=document.createElement('div');note.className='concept-results-count';note.textContent='Type more to narrow the results.';conceptResults.appendChild(note)}
 const stage=document.getElementById('stage').getBoundingClientRect(),input=conceptSearch.getBoundingClientRect(),width=Math.min(390,stage.width-24);
 conceptResults.style.width=width+'px';conceptResults.style.left=Math.max(12,Math.min(stage.width-width-12,input.left-stage.left))+'px';conceptResults.style.top=(input.bottom-stage.top+6)+'px';
 conceptResults.hidden=false;conceptSearch.setAttribute('aria-expanded','true');
}
conceptSearch.oninput=()=>{applyFilters();renderConceptResults()};
conceptSearch.addEventListener('focus',()=>{if(conceptSearch.value.trim())renderConceptResults()});
conceptSearch.addEventListener('keydown',e=>{if(e.key==='ArrowDown'){e.preventDefault();conceptResults.querySelector('button')?.focus()}if(e.key==='Escape')hideConceptResults()});
document.addEventListener('click',e=>{if(!conceptResults.contains(e.target)&&e.target!==conceptSearch)hideConceptResults()});

// Approximate neighborhoods from the paper, fitted to curated semantic anchors.
const regionLayer=document.createElementNS(NS,'g'),regionLabelLayer=document.createElementNS(NS,'g');
regionLayer.id='conceptRegions';regionLabelLayer.id='conceptRegionLabels';
// Vector text backdrops avoid re-rasterizing a map-sized SVG filter on every zoom.
function labelBackdrop(text){
 const back=text.cloneNode(true);back.removeAttribute('id');back.removeAttribute('class');back.setAttribute('aria-hidden','true');back.classList.add('region-label-backdrop');
 back.style.fontSize=text.classList.contains('detail-region-label')||text.classList.contains('clinical-node-annotation')?'15px':'16px';
 back.style.fontWeight='500';if(text.classList.contains('clinical-node-annotation'))back.style.opacity='.88';back.style.letterSpacing=text.classList.contains('clinical-node-annotation')?'normal':'.1px';
 back.style.fill='#fff';back.style.stroke='#fff';back.style.strokeWidth='6px';back.style.strokeLinejoin='round';back.style.filter='none';return back;
}
regionLayer.setAttribute('pointer-events','none');regionLabelLayer.setAttribute('pointer-events','none');
camera.insertBefore(regionLayer,edgeLayer);camera.appendChild(regionLabelLayer);
function roundedRegionPath(points){
 const p=points.map(([x,y])=>[x*S,y*S]),mid=(a,b)=>[(a[0]+b[0])/2,(a[1]+b[1])/2];
 return 'M'+mid(p[p.length-1],p[0])+p.map((v,i)=>'Q'+v+' '+mid(v,p[(i+1)%p.length])).join('')+'Z';
}
(DATA.regions||[]).forEach(region=>{
 const path=document.createElementNS(NS,'path');path.classList.add('concept-region');if(region.detail)path.classList.add('detail-region');path.dataset.region=region.id;
 path.setAttribute('d',roundedRegionPath(region.polygon));regionLayer.appendChild(path);
 const text=document.createElementNS(NS,'text');text.classList.add('concept-region-label');if(region.detail)text.classList.add('detail-region-label');text.dataset.region=region.id;
 let [x,y]=region.label_position;
 const origin={x:x*S,y:y*S},length=path.getTotalLength();let closest=null,distance=Infinity;
 for(let i=0;i<=800;i++){const point=path.getPointAtLength(length*i/800),d=Math.hypot(origin.x-point.x,origin.y-point.y);if(d<distance){closest=point;distance=d}}
 const dx=origin.x-closest.x,dy=origin.y-closest.y,norm=Math.hypot(dx,dy)||1,ux=dx/norm,uy=dy/norm;
 const halfWidth=Math.max(...region.label.map(line=>line.length))*4.2,halfHeight=region.label.length*9;
 const offset=Math.min(halfWidth/Math.max(Math.abs(ux),1e-6),halfHeight/Math.max(Math.abs(uy),1e-6))+7;
 x=(closest.x+ux*offset)/S;y=(closest.y+uy*offset-halfHeight+12)/S;
 text.dataset.originalX=origin.x;text.dataset.originalY=origin.y;
 text.setAttribute('x',x*S);text.setAttribute('y',y*S);text.setAttribute('text-anchor','middle');
 region.label.forEach((line,i)=>{const span=document.createElementNS(NS,'tspan');span.setAttribute('x',x*S);span.setAttribute('dy',i?18:0);span.textContent=line;text.appendChild(span)});
 regionLabelLayer.appendChild(text);
});
const regionLabelBackdrops=document.createElementNS(NS,'g');regionLabelBackdrops.setAttribute('aria-hidden','true');
[...regionLabelLayer.children].forEach(text=>regionLabelBackdrops.appendChild(labelBackdrop(text)));regionLabelLayer.prepend(regionLabelBackdrops);
// Patient age is a clinical anchor, so label it separately from learned concepts.
const ageNode=DATA.nodes.find(n=>n.concept_id==='patient_age');
if(ageNode){
 const annotation=document.createElementNS(NS,'g');annotation.id='patientAgeAnnotation';annotation.setAttribute('pointer-events','none');
 const leader=document.createElementNS(NS,'path');leader.setAttribute('d',`M${ageNode.x*S+radius(ageNode)+3},${ageNode.y*S-2} L858,268`);leader.setAttribute('fill','none');leader.setAttribute('stroke','#858585');leader.setAttribute('stroke-width','.85');leader.setAttribute('vector-effect','non-scaling-stroke');
 const label=document.createElementNS(NS,'text');label.setAttribute('x','861');label.setAttribute('y','272');label.setAttribute('class','clinical-node-annotation');label.textContent='Patient age';annotation.append(leader,labelBackdrop(label),label);camera.appendChild(annotation);
}

const smokingNode=DATA.nodes.find(n=>n.concept_id==='current_smoker');
if(smokingNode){
 const annotation=document.createElementNS(NS,'g');annotation.id='smokingAnnotation';annotation.setAttribute('pointer-events','none');
 const leader=document.createElementNS(NS,'path');leader.setAttribute('d',`M${smokingNode.x*S+radius(smokingNode)+2},${smokingNode.y*S-2} L749,395`);leader.setAttribute('fill','none');leader.setAttribute('stroke','#858585');leader.setAttribute('stroke-width','.85');leader.setAttribute('vector-effect','non-scaling-stroke');
 const label=document.createElementNS(NS,'text');label.setAttribute('x','752');label.setAttribute('y','399');label.setAttribute('text-anchor','start');label.setAttribute('class','clinical-node-annotation');label.textContent='Smoking';annotation.append(leader,labelBackdrop(label),label);camera.appendChild(annotation);
}

let regionsVisible=true;
function setRegionsVisible(visible){regionsVisible=visible;regionLayer.style.display=visible?'':'none';regionLabelLayer.style.display=visible?'':'none';notifyParent('glyph:regions-state',{regionsVisible:visible})}
const regionOption=document.createElement('label'),regionCheckbox=document.createElement('input');regionCheckbox.type='checkbox';regionCheckbox.checked=true;
regionOption.append(regionCheckbox,document.createTextNode('Show neighborhood regions'));document.querySelector('#displaySettings>.outcomes').appendChild(regionOption);
regionCheckbox.onchange=()=>setRegionsVisible(regionCheckbox.checked);
window.addEventListener('message',event=>{if(event.source===window.parent&&event.data?.type==='glyph:regions'){regionCheckbox.checked=!!event.data.visible;setRegionsVisible(regionCheckbox.checked)}});

// Reset view restores the complete initial presentation, including disease selection.
function resetAtlasView(){
 cancelGuidedCamera();
 if(zoomFrame!==null)cancelAnimationFrame(zoomFrame);zoomFrame=null;pendingZoom=null;
 scale=1;tx=0;ty=0;drag=null;moved=0;apply();
 selected.clear();onlySignificant=false;activeContext=null;associationDirection='risk';extremeOnly=false;
 selectedModalities.clear();DATA.modalities.forEach(v=>selectedModalities.add(v));
 selectedFamilies.clear();DATA.embedding_families.forEach(v=>selectedFamilies.add(v));
 facetChoices.querySelectorAll('input').forEach(input=>input.checked=true);
 document.getElementById('onlySignificant').checked=false;document.getElementById('extremeOnly').checked=false;
 document.querySelector('input[name="associationDirection"][value="risk"]').checked=true;
 const allContext=contextChoices.querySelector('input');if(allContext)allContext.checked=true;
 conceptSearch.value='';hideConceptResults();
 const outcomeSearch=document.getElementById('outcomeSearch');outcomeSearch.value='';outcomeSearch.oninput({target:outcomeSearch});
 outcomeGroups.forEach(({group})=>group.open=false);groupOpenBeforeSearch.clear();groupSearchActive=false;
 colorMode='modality';document.querySelector('input[name="colorMode"][value="modality"]').checked=true;
 document.getElementById('colorSummary').textContent='Color: modalities';
 const showEdges=document.getElementById('showEdges');showEdges.checked=true;showEdges.onchange();
 regionCheckbox.checked=true;setRegionsVisible(true);
 document.querySelectorAll('#toolbar>details[open]').forEach(menu=>menu.open=false);
 selectedNode=null;syncOutcomeBoxes();updateAssociationMode();clearSelection();notifyParent();
}
document.getElementById('reset').onclick=resetAtlasView;

updateAssociationMode();recolor();notifyParent('glyph:ready',{associationsReady:!DATA.progressive_associations||!!DATA.associations_ready});

// This research atlas presents higher-risk concepts. Full estimates remain in exports.
const sourceAssociationMode=updateAssociationMode;
updateAssociationMode=function(){associationDirection='risk';sourceAssociationMode()};
const directionInputs=[...document.querySelectorAll('input[name="associationDirection"]')];
directionInputs.forEach(input=>{input.closest('label').hidden=true;input.disabled=input.value!=='risk'});
const options=document.querySelector('#displaySettings>.outcomes');
options.querySelector('b').textContent='Higher-risk associations (OR > 1)';
options.querySelector('p.meta').textContent='Highlight higher-risk concepts for the selected outcomes.';
document.querySelector('#extremeOnly').nextElementSibling.textContent='Highest 10% of odds ratios per outcome (minimum 5)';
// Parent controls keep the embedded graph free of floating toolbar buttons.
if(window.parent!==window)document.body.classList.add('parent-controls');
window.addEventListener('message',event=>{
 if(event.source!==window.parent)return;const m=event.data;
 if(m?.type==='glyph:search'){
  beginManualExploration();conceptSearch.value=String(m.query||'');applyFilters();
  const matches=conceptSearch.value.trim()?rankedConceptMatches().slice(0,12):[];
  notifyParent('glyph:search-results',{matches:matches.map(n=>({code:n.name,text:n.interpretation||''}))});
 }
 if(m?.type==='glyph:reset')resetAtlasView();
 if(m?.type==='glyph:help')document.getElementById('tourButton').click();
});
