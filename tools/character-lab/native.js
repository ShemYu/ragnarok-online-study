import {nativeFrameAt,nativePartFrame,composeNative,pixelDifference} from './native-core.mjs';

const BASE='./assets/native-template-v1/', WAYFARER='./assets/native-wayfarer-v2/', EQUIPMENT='./assets/native-equipment-v1/', HEAD='./assets/native-head-v1/';
const $=id=>document.getElementById(id);
let template,equipment,originalTextures,frame=0,playing=false,time=0,last=0,completed=false,ready=false;
const outfits={},heads={},gearTextures={},cache=new Map(),MAX_CACHE=128;
let sceneFrames=[],sceneEpoch=0,measurement=null;
const controls=['play','restart','previous','next','scrub','loop','show-anchors','show-head','show-weapon','show-trail','costume-select','head-select','show-template-boundaries','headgear-select','weapon-select','benchmark','actor-count'];
controls.forEach(id=>$(id).disabled=true);
const status=message=>{$('status').textContent=message;};
const duration=()=>template.sequences.attack.durationMs;
const delay=()=>template.parts.body.actions.attack.delayMs;

async function json(path,base=BASE){const r=await fetch(base+path);if(!r.ok)throw new Error(`Cannot load ${path} (${r.status}).`);return r.json();}
async function pixels(path,base=BASE) {
  const image=new Image();image.src=base+path;await image.decode();
  const c=document.createElement('canvas');c.width=image.naturalWidth;c.height=image.naturalHeight;
  const ctx=c.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);
  return {width:c.width,height:c.height,data:ctx.getImageData(0,0,c.width,c.height).data,canvas:c};
}
function canvasOf(p){const c=document.createElement('canvas');c.width=p.width;c.height=p.height;c.getContext('2d').putImageData(new ImageData(p.data,p.width,p.height),0,0);return c;}
async function loadTextures(definitions,base) {
  const textures={};await Promise.all(Object.entries(definitions).map(async([index,meta])=>{textures[index]=await pixels(meta.file,base);}));return textures;
}
function configuration(original=false) {
  const outfit=original?'original':$('costume-select').value,gear=original?'none':$('headgear-select').value;
  const hasWeapon=original||$('weapon-select').value!=='none';
  return {outfit,gear,head:original?'original':$('head-select').value,options:{head:$('show-head').checked,headgear:true,weapon:$('show-weapon').checked&&hasWeapon,trail:$('show-trail').checked&&$('show-weapon').checked&&hasWeapon}};
}
function assembly(config) {
  const textures={...outfits[config.outfit],head:heads[config.head||'original']};
  if(config.gear!=='none')textures.headgear=gearTextures[config.gear];
  return {model:config.gear==='none'?template:{...template,parts:{...template.parts,headgear:equipment.parts[config.gear]}},textures};
}
function composed(config,index) {
  const key=JSON.stringify(['attack',config,index]);
  if(!cache.has(key)){
    const {model,textures}=assembly(config);cache.set(key,canvasOf(composeNative(model,textures,index,config.options)));
    if(cache.size>MAX_CACHE)cache.delete(cache.keys().next().value);
  }
  return cache.get(key);
}
function drawStage(canvas,config) {
  const ctx=canvas.getContext('2d'),scale=3,offsetX=(canvas.width-192*scale)/2,offsetY=-100;
  ctx.clearRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#e8ebdf';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=false;
  ctx.drawImage(composed(config,frame),offsetX,offsetY,192*scale,192*scale);
  if($('show-anchors').checked) {
    const anchor=nativePartFrame(template,'body',frame).anchors[0];
    if(anchor){const x=offsetX+(template.origin[0]+anchor[0])*scale,y=offsetY+(template.origin[1]+anchor[1])*scale;
      ctx.strokeStyle='#c06140';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(x-8,y);ctx.lineTo(x+8,y);ctx.moveTo(x,y-8);ctx.lineTo(x,y+8);ctx.stroke();
      ctx.fillStyle='#914d32';ctx.font='11px system-ui';ctx.fillText('head / hat anchor',x+10,y-5);
    }
  }
  if($('show-template-boundaries').checked) {
    const layer=nativePartFrame(template,'body',frame).layers.find(l=>l.index>=0),image=originalTextures.body[layer.index];
    ctx.strokeStyle='#697d96';ctx.setLineDash([4,4]);ctx.strokeRect(offsetX+(template.origin[0]+layer.x-image.width/2)*scale,offsetY+(template.origin[1]+layer.y-image.height/2)*scale,image.width*scale,image.height*scale);ctx.setLineDash([]);
  }
}
function facts() {
  const body=nativePartFrame(template,'body',frame),layer=body.layers.find(l=>l.index>=0),weapon=nativePartFrame(template,'weapon',frame),gear=$('headgear-select').value;
  const rows=[['Body action / frame',`${template.parts.body.actions.attack.sourceAction} / ${frame+1}`],['Body SPR slot',String(layer.index)],['Original frame duration',`${delay()} ms`],['Original body offset',`${layer.x}, ${layer.y}`],['Head module',`${$('head-select').selectedOptions[0].textContent} · SPR 1`],['Head / hat anchor',body.anchors[0].join(', ')],['Headgear module',gear==='none'?'None':`${equipment.parts[gear].label || gear} · source ACT ${equipment.parts[gear].actions.attack.sourceAction}`],['Dagger layer in source',weapon.layers.some(l=>l.index>=0)?'Visible':'Hidden'],['Source event',body.event<0?'None':template.parts.body.events[body.event]]];
  const container=document.createElement('tbody');$('source-facts').replaceChildren(container);
  for(const [label,value] of rows){const row=document.createElement('tr'),th=document.createElement('th'),td=document.createElement('td');th.scope='row';th.textContent=label;td.textContent=value;row.append(th,td);container.append(row);}
}
function render() {
  if(!ready)return;
  drawStage($('native-canvas'),configuration(true));drawStage($('custom-canvas'),configuration());
  $('frame-label').textContent=`Frame ${frame+1} / 9 · ${frame*delay()}–${(frame+1)*delay()} ms`;
  $('scrub').value=frame;$('play').textContent=playing?'Pause':completed?'Replay':'Play';
  document.querySelectorAll('[data-frame]').forEach(button=>button.setAttribute('aria-pressed',String(Number(button.dataset.frame)===frame)));facts();
}
function seek(index){frame=Math.min(8,Math.max(0,index));time=frame*delay();playing=false;completed=false;render();status('Paused on an original frame. Both views use the same body action data.');}
function drawScene(now,count) {
  const canvas=$('performance-canvas'),ctx=canvas.getContext('2d');ctx.fillStyle='#e8ebdf';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.imageSmoothingEnabled=false;
  const cols=count===1?1:count===32?8:16,rows=Math.ceil(count/cols),cellW=canvas.width/cols,cellH=canvas.height/rows;
  const scale=Math.min(2.3,cellW/130,cellH/140);
  for(let i=0;i<count;i++){
    const index=nativeFrameAt(((now-sceneEpoch+i*61)%duration()+duration())%duration(),9,delay());
    const x=(i%cols+.5)*cellW-96*scale,y=(Math.floor(i/cols)+1)*cellH-164*scale;
    ctx.drawImage(sceneFrames[index],x,y,192*scale,192*scale);
  }
}
function percentile(values,percent){const sorted=[...values].sort((a,b)=>a-b);return sorted[Math.min(sorted.length-1,Math.floor(sorted.length*percent))];}
function cancelMeasurement(message){if(measurement){measurement=null;$('benchmark').disabled=false;$('perf-results').textContent=message;}}
function prepareScene() {
  if(!ready)return;
  cancelMeasurement('Selection changed. Measure again for this configuration.');
  delete $('perf-results').dataset.measurement;
  $('perf-results').textContent='Measure this selection to compare fresh composition with cached playback.';
  const config=configuration();sceneFrames=Array.from({length:9},(_,i)=>composed(config,i));
  $('perf-status').textContent=`${$('actor-count').value} characters · ${$('costume-select').selectedOptions[0].textContent} · ${$('head-select').selectedOptions[0].textContent} · ${$('headgear-select').selectedOptions[0].textContent} · 9 cached poses`;
}
function finishMeasurement() {
  const m=measurement,elapsed=m.timestamps.at(-1)-m.timestamps[0],intervals=m.timestamps.slice(1).map((t,i)=>t-m.timestamps[i]);
  const result={actors:m.count,costume:m.config.outfit,head:m.config.head,headgear:m.config.gear,weapon:m.config.options.weapon,frames:m.costs.length,coldCompositionMs:m.coldMs,sceneCpuMedianMs:percentile(m.costs,.5),sceneCpuP95Ms:percentile(m.costs,.95),observedRafHz:(m.timestamps.length-1)*1000/elapsed,rafIntervalP95Ms:percentile(intervals,.95)};
  $('perf-results').textContent=`9-pose build: ${result.coldCompositionMs.toFixed(2)} ms · Cached scene CPU: ${result.sceneCpuMedianMs.toFixed(2)} ms median / ${result.sceneCpuP95Ms.toFixed(2)} ms p95 · Observed callbacks: ${result.observedRafHz.toFixed(1)} / sec (${result.frames} samples)`;
  $('perf-results').dataset.measurement=JSON.stringify(result);measurement=null;$('benchmark').disabled=false;
}
function tick(now) {
  if(playing){time+=Math.max(0,now-last);
    if(time>=duration()){if($('loop').checked){time%=duration();status('Loop restart jumps to the first source frame; no recovery frames were added.');}else{time=duration();playing=false;completed=true;status('Original action complete. The last frame is held; Replay returns to frame 1.');}}
    const next=nativeFrameAt(time,9,delay());if(next!==frame||!playing){frame=next;render();}
  }
  if(ready&&sceneFrames.length){const started=performance.now();drawScene(now,Number($('actor-count').value));const cost=performance.now()-started;
    if(measurement){measurement.costs.push(cost);measurement.timestamps.push(now);if(measurement.costs.length>=120)finishMeasurement();}
  }
  last=now;requestAnimationFrame(tick);
}
$('play').addEventListener('click',()=>{if(completed){time=0;frame=0;completed=false;}playing=!playing;last=performance.now();render();status(playing?'Playing the original nine frames at native 96 ms timing.':'Paused.');});
$('restart').addEventListener('click',()=>seek(0));$('previous').addEventListener('click',()=>seek(frame-1));$('next').addEventListener('click',()=>seek(frame+1));
$('scrub').addEventListener('input',event=>seek(Number(event.target.value)));
document.querySelectorAll('[data-frame]').forEach(button=>button.addEventListener('click',()=>{if(ready)seek(Number(button.dataset.frame));}));
for(const id of ['show-anchors','show-head','show-weapon','show-trail','costume-select','head-select','show-template-boundaries','headgear-select','weapon-select','actor-count'])$(id).addEventListener('change',()=>{render();prepareScene();if(id==='costume-select')gallery();});
$('benchmark').addEventListener('click',()=>{
  const config=configuration(),{model,textures}=assembly(config),start=performance.now();
  // Explicitly bypass the cache to measure a fresh nine-pose build.
  const coldFrames=Array.from({length:9},(_,i)=>canvasOf(composeNative(model,textures,i,config.options)));
  const coldMs=performance.now()-start;sceneFrames=coldFrames;
  measurement={config,count:Number($('actor-count').value),coldMs,costs:[],timestamps:[]};
  $('benchmark').disabled=true;$('perf-results').textContent='Measuring 120 animation callbacks…';delete $('perf-results').dataset.measurement;
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)cancelMeasurement('Measurement cancelled because the page was hidden. Measure again with this page visible.');});
function gallery() {
  const element=$('slot-gallery');element.replaceChildren();const selected=outfits[$('costume-select').value];
  for(const index of [82,83,84,85,86]){
    const card=document.createElement('figure'),pair=document.createElement('div');pair.className='slot-pair';
    for(const [name,texture] of [['Original',originalTextures.body[index]],['Selected costume',selected.body[index]]]){
      const img=document.createElement('img');img.src=texture.canvas.toDataURL('image/png');img.alt=`${name} body SPR slot ${index}`;pair.append(img);
    }
    const caption=document.createElement('figcaption');caption.textContent=`SPR ${index} · ${originalTextures.body[index].width} × ${originalTextures.body[index].height}`;card.append(pair,caption);element.append(card);
  }
}
try {
  const [source,oldCostume,wayfarer,gear,headDefinition]=await Promise.all([json('template.json'),json('costume.json'),json('costume.json',WAYFARER),json('equipment.json',EQUIPMENT),json('head.json',HEAD)]);template=source;equipment=gear;
  originalTextures={};await Promise.all(Object.entries(template.parts).map(async([part,definition])=>{originalTextures[part]=await loadTextures(definition.textures,BASE);}));
  outfits.original=originalTextures;
  heads.original=originalTextures.head;
  const replacementHead=await loadTextures(headDefinition.head,HEAD);
  for(const [index,image] of Object.entries(replacementHead)){const sourceHead=originalTextures.head[index];if(!sourceHead||image.width!==sourceHead.width||image.height!==sourceHead.height)throw new Error(`Head ${index} does not fit its native SPR slot.`);}
  heads.wayfarer={...originalTextures.head,...replacementHead};
  for(const [name,definition,base] of [['custom',oldCostume,BASE],['wayfarer',wayfarer,WAYFARER]]){
    const body=await loadTextures(definition.body,base);
    for(const [index,image] of Object.entries(body)){const original=originalTextures.body[index];if(!original||image.width!==original.width||image.height!==original.height)throw new Error(`Replacement ${index} does not fit its SPR slot.`);}
    outfits[name]={...originalTextures,body:{...originalTextures.body,...body}};
  }
  for(const [id,definition] of Object.entries(equipment.parts)){
    gearTextures[id]=await loadTextures(definition.textures,EQUIPMENT);
    const option=document.createElement('option');option.value=id;option.textContent=definition.label||definition.name||`RO ${id}`;$('headgear-select').append(option);
  }
  const checks=[];
  for(const [name,base,prefix] of [['original',BASE,'attack/'],['custom',BASE,'costume/attack/'],['wayfarer',WAYFARER,'costume/attack/']]){
    for(let i=0;i<9;i++)checks.push((async()=>pixelDifference(composeNative(template,outfits[name],i),await pixels(`${prefix}frame-${String(i).padStart(2,'0')}.png`,base)))());
  }
  for(const [id,definition] of Object.entries(equipment.parts)){
    const {model,textures}=assembly({outfit:'original',gear:id});
    for(let i=0;i<9;i++)checks.push((async()=>pixelDifference(composeNative(model,textures,i),await pixels(definition.sequences.attack.frames[i].file,EQUIPMENT)))());
  }
  for(const gear of ['none','cap','hat']){
    const {model,textures}=assembly({outfit:'wayfarer',head:'wayfarer',gear});
    for(let i=0;i<9;i++)checks.push((async()=>pixelDifference(composeNative(model,textures,i),await pixels(headDefinition.sequences[gear].frames[i].file,HEAD)))());
  }
  const results=await Promise.all(checks),exact=results.every(result=>result.pixels===0);
  $('regression-status').textContent=exact?`Verified: ${results.length} original, costume, head and equipment frames match the local native-data renderer pixel for pixel. Source ACT files are unchanged.`:'Renderer verification failed; inspect the native frame comparison before relying on this result.';
  $('regression-status').dataset.result=exact?'pass':'fail';
  if(!exact)throw new Error('Native pixel parity failed: '+JSON.stringify(results));
  controls.forEach(id=>$(id).disabled=false);ready=true;gallery();render();prepareScene();
  status('Ready. Wayfarer head and clothes are separate modules. Original RO actions and hat attachments are preserved.');
  sceneEpoch=last=performance.now();requestAnimationFrame(tick);
} catch(error){status(`Unable to start the template study: ${error.message}`);$('status').classList.add('error');console.error(error);}
