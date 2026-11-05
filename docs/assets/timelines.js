const timelinePoints=JSON.parse(document.getElementById('timeline-points').textContent);
const timelineDialog=document.getElementById('timeline-detail'),timelineBody=document.getElementById('timeline-detail-body'),timelineTip=document.getElementById('timeline-tooltip');
const timelineEscape=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const timelineNumber=value=>value==null?'—':Math.abs(value)>=1000||Math.abs(value)<.01?Number(value).toExponential(2):Number(value).toFixed(2);
function timelineSummary(d){return `Adjusted OR ${timelineNumber(d.or_sd)} (95% CI ${timelineNumber(d.lo)}–${timelineNumber(d.hi)})`}
function showTimelineTip(event,datum){
 timelineTip.replaceChildren();const name=document.createElement('strong'),stats=document.createElement('span');name.textContent=datum.label;stats.textContent=timelineSummary(datum);timelineTip.append(name,stats);timelineTip.hidden=false;
 const box=event.currentTarget.getBoundingClientRect(),x=event.clientX||box.left,y=event.clientY||box.top;
 timelineTip.style.left=Math.max(10,Math.min(innerWidth-timelineTip.offsetWidth-10,x+15))+'px';timelineTip.style.top=Math.max(10,Math.min(innerHeight-timelineTip.offsetHeight-10,y+15))+'px';
}
function openTimelineDetail(datum){
 timelineTip.hidden=true;
 const p=datum.p==null?'—':datum.p===0?'0 (reported)':Number(datum.p).toExponential(2);
 const kind=datum.kind==='literature'?'Literature marker':datum.kind==='glyph'?'Glyph concept':'Phecode comparator';
 timelineBody.innerHTML=`<p class="timeline-detail-kind">${kind}</p><h2 id="timeline-detail-title">${timelineEscape(datum.label)}</h2><p class="timeline-detail-stats">${timelineEscape(timelineSummary(datum))}</p><p class="timeline-detail-p">p = ${p}</p>`;
 if(datum.kind==='glyph'&&datum.interpretation){const description=document.createElement('p');description.className='timeline-glyph-interpretation';description.textContent=datum.interpretation;timelineBody.appendChild(description)}
 if(datum.kind==='literature'&&datum.rule){
  const section=document.createElement('section');section.className='timeline-rule';
  const heading=document.createElement('h3');heading.textContent='Rule used in this cohort';
  const summary=document.createElement('p');summary.className='timeline-rule-summary';summary.textContent=datum.rule.summary;
  const adaptation=document.createElement('p');adaptation.className='timeline-rule-note';adaptation.textContent=datum.note||datum.rule.source_note||'';
  const details=document.createElement('details'),label=document.createElement('summary'),code=document.createElement('pre');label.textContent='Exact encoding';code.textContent=datum.rule.encoding;details.append(label,code);
  const units=document.createElement('p');units.className='timeline-rule-units';units.textContent='Encoding before Discovery-training standardization. The plotted association was estimated in this study.';
  section.append(heading,summary,adaptation,details,units);timelineBody.appendChild(section);
 }
 if(datum.url){
  const title=document.createElement('p');title.className='timeline-paper-title';title.textContent=datum.title;
  const link=document.createElement('a');link.className='timeline-paper-link';link.href=datum.url;link.target='_blank';link.rel='noopener noreferrer';link.innerHTML='<svg viewBox="0 0 18 18" aria-hidden="true" focusable="false"><path d="M4 2h7l3 3v11H4zM11 2v4h3M6.5 9h5M6.5 12h5"/></svg><span>Read paper ↗</span>';timelineBody.append(title,link);
 }
 if(datum.kind==='glyph'){
  const button=document.createElement('button');button.type='button';button.className='timeline-concept-link';button.textContent='Find concept in graph ↑';
  button.onclick=()=>{timelineDialog.close();document.getElementById('concept-atlas').contentWindow.postMessage({type:'glyph:concept',concept:datum.marker},'*');document.getElementById('atlas').scrollIntoView({behavior:'smooth'})};timelineBody.appendChild(button);
 }
 timelineDialog.showModal();
}
document.querySelectorAll('[data-timeline-point]').forEach(target=>{
 const datum=timelinePoints[target.dataset.timelinePoint];
 target.addEventListener('pointermove',event=>showTimelineTip(event,datum));target.addEventListener('pointerleave',()=>timelineTip.hidden=true);
 target.addEventListener('focus',event=>showTimelineTip(event,datum));target.addEventListener('blur',()=>timelineTip.hidden=true);
 target.addEventListener('click',()=>openTimelineDetail(datum));target.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openTimelineDetail(datum)}});
});
document.getElementById('timeline-close').onclick=()=>timelineDialog.close();
timelineDialog.addEventListener('click',event=>{if(event.target===timelineDialog){const r=timelineDialog.getBoundingClientRect();if(event.clientX<r.left||event.clientX>r.right||event.clientY<r.top||event.clientY>r.bottom)timelineDialog.close()}});

