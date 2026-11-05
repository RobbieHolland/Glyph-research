// Draw the small graph shell first, then progressively load aggregate association chunks.
const associationProgress=document.createElement('div');associationProgress.id='associationProgress';associationProgress.setAttribute('role','status');associationProgress.textContent='Loading association data…';document.getElementById('stage').appendChild(associationProgress);
let completedAssociationChunks=0;const associationChunkPromises=new Map();
const decodeAssociation=a=>({outcome:DATA.outcomes[a[0]],odds_ratio:a[1],p_value:a[2],ci_lower:a[3],ci_upper:a[4],corrected_p_value:a[5],significant:a[6],count:a[7],modality_corrected_p_value:null});
function loadAssociationChunk(chunk){
 if(associationChunkPromises.has(chunk.url))return associationChunkPromises.get(chunk.url);
 const promise=(async()=>{
  const response=await fetch(chunk.url);if(!response.ok)throw new Error('Association download failed');
  const records=await response.json();
  Object.entries(records).forEach(([key,packed])=>{
   A[key]=packed.map(decodeAssociation);DATA.nodes[Number(key)].associations_ready=true;
   const significant=significantByNode[Number(key)];Object.keys(significant).forEach(k=>delete significant[k]);
   A[key].filter(a=>a.significant).forEach(a=>significant[a.outcome]=a);
  });
  completedAssociationChunks++;
  associationProgress.textContent=`Loading association data ${completedAssociationChunks}/${DATA.association_chunks.length}…`;
  notifyParent('glyph:data-progress',{associationsReady:false,loaded:completedAssociationChunks,total:DATA.association_chunks.length});
  if(selectedNode&&Object.hasOwn(records,String(selectedNode.i)))show(selectedNode);
  if(completedAssociationChunks===DATA.association_chunks.length){
   DATA.associations_ready=true;associationProgress.hidden=true;
   updateAssociationMode();if(selectedNode)show(selectedNode);
   notifyParent('glyph:data-ready',{associationsReady:true});
  }
 })().catch(error=>{
  associationChunkPromises.delete(chunk.url);associationProgress.textContent='Association data could not load. Retry';associationProgress.classList.add('can-retry');associationProgress.onclick=()=>loadAssociationChunk(chunk);throw error;
 });
 associationChunkPromises.set(chunk.url,promise);return promise;
}
window.loadAssociationForNode=index=>{
 const chunk=DATA.association_chunks.find(c=>c.nodes.includes(index));if(chunk)loadAssociationChunk(chunk).catch(()=>{});
};
async function startAssociationDownloads(){
 let next=0;
 async function worker(){while(next<DATA.association_chunks.length){const chunk=DATA.association_chunks[next++];try{await loadAssociationChunk(chunk)}catch{break}await new Promise(resolve=>setTimeout(resolve,0))}}
 await Promise.all([worker(),worker()]);
}
// Two frames ensure the graph can paint before downloads and decoding start.
requestAnimationFrame(()=>requestAnimationFrame(startAssociationDownloads));
