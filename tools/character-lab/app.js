(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const STORAGE_KEY = 'ro-character-atelier-v1';
  const DIRECTIONS = [['south','South'],['west','West'],['north','North'],['east','East']];
  const DEFAULTS = {design:null,direction:'south',cloth:'original',hair:'original',zoom:2,background:'field',baseline:true};
  const TONES = {
    cloth:[['original','Original palette',null],['teal','River teal','#45877e'],['red','Madder red','#a84b48'],['navy','Midnight navy','#414f78'],['gold','Harvest gold','#bc9444']],
    hair:[['original','Original palette',null],['copper','Copper','#a8673b'],['dark','Charcoal','#393a39'],['brown','Walnut','#695039'],['blonde','Wheat','#baa063']]
  };
  let manifest, assetsReady=false, renderQueued=false, lastSprite=null, lastReference=null;
  let renderVersion=0;
  let state={...DEFAULTS};
  const images=new Map(), normalized=new Map();
  const stats={original:null,reference:null};
  try { const restored=JSON.parse(localStorage.getItem(STORAGE_KEY)||'null'); if(restored&&typeof restored==='object') state={...state,...restored}; } catch(_){ /* A fresh study works when browser storage is unavailable. */ }
  function status(message,error=false){$('status').textContent=message;$('status').classList.toggle('error',error);}
  function save(){try{localStorage.setItem(STORAGE_KEY,JSON.stringify(state));}catch(_){status('Preview ready. Browser storage is unavailable; export a recipe to keep your choices.');}}
  function sourceURL(file){if(!file||typeof file!=='string')throw new Error('An artwork filename is missing.');const url=new URL(file,/^(\.?\/?assets\/|\/)/.test(file)?location.href:new URL('assets/',location.href));if(url.origin!==location.origin)throw new Error('Only local artwork is supported.');return url.href;}
  function loadImage(file){const url=sourceURL(file);if(images.has(url))return images.get(url);const promise=new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error('Could not load '+file));image.src=url;});images.set(url,promise);return promise;}
  function chosenDesign(selection=state){return manifest.designs.find(d=>d.id===selection.design)||manifest.designs[0];}
  function frameFor(descriptor,selection=state){const frames=descriptor.frames||[];const lookup=selection.direction.toLowerCase();return frames.find(f=>String(f.name||f.label||'').toLowerCase()===lookup)||frames[DIRECTIONS.findIndex(d=>d[0]===lookup)]||frames[0];}
  function canvas(width,height){const result=document.createElement('canvas');result.width=width;result.height=height;return result;}
  function hexToHsl(hex){const h=hex.replace('#','');return rgbToHsl(parseInt(h.slice(0,2),16),parseInt(h.slice(2,4),16),parseInt(h.slice(4,6),16));}
  function rgbToHsl(r,g,b){r/=255;g/=255;b/=255;const hi=Math.max(r,g,b),lo=Math.min(r,g,b),delta=hi-lo;let h=0;const l=(hi+lo)/2,s=delta===0?0:delta/(1-Math.abs(2*l-1));if(delta){if(hi===r)h=((g-b)/delta)%6;else if(hi===g)h=(b-r)/delta+2;else h=(r-g)/delta+4;h=(h*60+360)%360;}return[h,s,l];}
  function hslToRgb(h,s,l){const c=(1-Math.abs(2*l-1))*s,x=c*(1-Math.abs((h/60)%2-1)),m=l-c/2;let rgb=h<60?[c,x,0]:h<120?[x,c,0]:h<180?[0,c,x]:h<240?[0,x,c]:h<300?[x,0,c]:[c,0,x];return rgb.map(v=>Math.round((v+m)*255));}
  const clamp=(v,min,max)=>Math.max(min,Math.min(max,v));
  function toneHex(kind,id,design){const built=TONES[kind].find(t=>t[0]===id);if(!built)return null;const override=design.palettes?.[kind];if(Array.isArray(override)){const i=TONES[kind].findIndex(t=>t[0]===id)-1;if(i>=0&&/^#[\da-f]{6}$/i.test(override[i]||''))return override[i];}return built[2];}
  function insideMask(hsl,x,y,mask){const[h,s,l]=hsl;const hue=mask.hue||[0,360];return (hue[0]<=hue[1]?h>=hue[0]&&h<=hue[1]:h>=hue[0]||h<=hue[1])&&s>=(mask.satMin??.22)&&s<=(mask.satMax??1)&&l>=(mask.lightMin??.06)&&l<=(mask.lightMax??.94)&&x>=(mask.xMin??0)&&x<=(mask.xMax??1)&&y>=(mask.yMin??0)&&y<=(mask.yMax??1);}
  function insideRect(x,y,rect){return x>=rect.x&&y>=rect.y&&x<rect.x+rect.w&&y<rect.y+rect.h;}
  function recolor(data,bounds,design,frame,selection){
    if(selection.cloth==='original'&&selection.hair==='original')return;
    const cloth=toneHex('cloth',selection.cloth,design),hair=toneHex('hair',selection.hair,design);
    const masks=design.colorMasks||{},frameMasks=frame.colorMasks||{};
    const clothMask={hue:[145,215],satMin:.22,lightMin:.07,lightMax:.93,...masks.cloth,...frameMasks.cloth};
    const hairMask={hue:[12,48],satMin:.3,lightMin:.10,lightMax:.62,yMax:.40,...masks.hair,...frameMasks.hair};
    const hairRegions=frame.hairRegions||frame.hairIncludeRects||hairMask.regions||[];
    const hairExclusions=frame.hairExcludeRects||hairMask.excludeRegions||[];
    const cp=cloth&&hexToHsl(cloth),hp=hair&&hexToHsl(hair);
    for(let i=0;i<data.data.length;i+=4){
      if(data.data[i+3]<96)continue;
      const x=((i/4)%data.width-bounds.x)/Math.max(1,bounds.w);
      const y=(Math.floor(i/4/data.width)-bounds.y)/Math.max(1,bounds.h);
      const hsl=rgbToHsl(data.data[i],data.data[i+1],data.data[i+2]);
      let target=null,base=.5;
      if(cp&&insideMask(hsl,x,y,clothMask)){target=cp;base=clothMask.baseLight??.5;}
      else if(hp&&insideMask(hsl,x,y,hairMask)&&(!hairRegions.length||hairRegions.some(rect=>insideRect(x,y,rect)))&&!hairExclusions.some(rect=>insideRect(x,y,rect))){target=hp;base=hairMask.baseLight??.46;}
      if(!target)continue;
      const light=clamp(hsl[2]+(target[2]-base)*.65,.04,.97);
      const saturation=clamp(target[1]*(.6+hsl[1]*.6),0,1);
      const rgb=hslToRgb(target[0],saturation,light);
      data.data[i]=rgb[0];data.data[i+1]=rgb[1];data.data[i+2]=rgb[2];
    }
  }
  async function makeSprite(descriptor,isReference=false,selection={...state}){
    const snapshot={...selection};
    const frame=frameFor(descriptor,snapshot);
    if(!frame)throw new Error('This design has no direction frames.');
    const file=frame.file||descriptor.file;
    const key=JSON.stringify([descriptor.id,file,frame,isReference?'reference':snapshot.cloth,isReference?'reference':snapshot.hair,descriptor.displayHeight,descriptor.normalizationHeight,descriptor.frames.map(f=>f.contentBounds),descriptor.colorMasks,descriptor.palettes]);
    if(normalized.has(key))return normalized.get(key);
    const image=await loadImage(file);
    const x=Math.round(frame.x||0),y=Math.round(frame.y||0),w=Math.round(frame.w||image.naturalWidth),h=Math.round(frame.h||image.naturalHeight);
    if(w<1||h<1||x<0||y<0||x+w>image.naturalWidth||y+h>image.naturalHeight)throw new Error('A sprite frame extends outside its source artwork.');
    const crop=canvas(w,h),ctx=crop.getContext('2d',{willReadFrequently:true});
    ctx.drawImage(image,x,y,w,h,0,0,w,h);
    const pixels=ctx.getImageData(0,0,w,h);
    let left=w,top=h,right=-1,bottom=-1;
    for(let py=0;py<h;py++)for(let px=0;px<w;px++)if(pixels.data[(py*w+px)*4+3]>=96){left=Math.min(left,px);top=Math.min(top,py);right=Math.max(right,px);bottom=Math.max(bottom,py);}
    if(right<left)throw new Error('The selected sprite frame is empty.');
    const bounds={x:left,y:top,w:right-left+1,h:bottom-top+1};
    for(let i=3;i<pixels.data.length;i+=4)if(pixels.data[i]<96){pixels.data[i-3]=0;pixels.data[i-2]=0;pixels.data[i-1]=0;pixels.data[i]=0;}
    if(!isReference)recolor(pixels,bounds,descriptor,frame,snapshot);
    ctx.putImageData(pixels,0,0);
    const targetHeight=Number(frame.displayHeight||descriptor.displayHeight||94);
    const commonHeight=Number(descriptor.normalizationHeight)||Math.max(bounds.h,...descriptor.frames.map(f=>Number(f.contentBounds?.h)||0));
    const scale=targetHeight/commonHeight;
    const anchorX=Number.isFinite(frame.anchorX)?frame.anchorX:(left+right+1)/2;
    const anchorY=Number.isFinite(frame.anchorY)?frame.anchorY:bottom+1;
    const result=canvas(128,128),out=result.getContext('2d');
    out.imageSmoothingEnabled=false;
    const dx=Math.round(64+(left-anchorX)*scale),dy=Math.round(112+(top-anchorY)*scale),dw=Math.round(bounds.w*scale),dh=Math.round(bounds.h*scale);
    out.drawImage(crop,left,top,bounds.w,bounds.h,dx,dy,dw,dh);
    const sprite={canvas:result,frame,file,bounds,width:dw,height:dh,clipped:dx<0||dx+dw>128||dy<0||dy+dh>128};
    normalized.set(key,sprite);
    return sprite;
  }
  function drawPreview(element,sprite,selection,backgroundImage){
    const rect=element.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
    const width=Math.max(1,Math.round(rect.width*dpr)),height=Math.max(1,Math.round(rect.height*dpr));
    if(element.width!==width)element.width=width;
    if(element.height!==height)element.height=height;
    const ctx=element.getContext('2d');
    ctx.imageSmoothingEnabled=false;ctx.fillStyle='#e6e9db';ctx.fillRect(0,0,width,height);
    if(selection.background==='checker'){
      const grid=12*dpr;
      for(let y=0;y<height;y+=grid)for(let x=0;x<width;x+=grid){ctx.fillStyle=(Math.floor(x/grid)+Math.floor(y/grid))%2?'#e5e5dc':'#f2f1e8';ctx.fillRect(x,y,grid,grid);}
    }else if(selection.background==='field'&&backgroundImage){
      const bg=backgroundImage;
      ctx.imageSmoothingEnabled=true;
      const scale=Math.max(width/bg.width,height/bg.height);
      ctx.drawImage(bg,(width-bg.width*scale)/2,(height-bg.height*scale)/2,bg.width*scale,bg.height*scale);
      ctx.fillStyle='#edf0d91c';ctx.fillRect(0,0,width,height);
    }else{ctx.fillStyle='#ecebdc';ctx.fillRect(0,0,width,height);}
    const baseline=Math.round(height*.79),scale=selection.zoom*dpr;
    if(selection.baseline){ctx.strokeStyle='#43593b66';ctx.setLineDash([4*dpr,5*dpr]);ctx.lineWidth=dpr;ctx.beginPath();ctx.moveTo(12*dpr,baseline+.5);ctx.lineTo(width-12*dpr,baseline+.5);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#3d563eb3';ctx.font=`${8*dpr}px system-ui`;ctx.fillText('FEET',12*dpr,baseline+13*dpr);}
    ctx.imageSmoothingEnabled=false;
    ctx.drawImage(sprite.canvas,Math.round(width/2-64*scale),Math.round(baseline-112*scale),128*scale,128*scale);
  }
  async function render(){
    if(!assetsReady)return;
    const version=++renderVersion,snapshot={...state};
    const isCurrent=()=>version===renderVersion&&JSON.stringify(snapshot)===JSON.stringify(state);
    try{
      const design=chosenDesign(snapshot);
      const[original,reference]=await Promise.all([makeSprite(design,false,snapshot),makeSprite(manifest.reference,true,snapshot)]);
      if(!isCurrent())return;
      const backgroundImage=snapshot.background==='field'&&manifest.background?.file?await loadImage(manifest.background.file):null;
      if(!isCurrent())return;
      const originalElement=$('original-canvas'),referenceElement=$('reference-canvas');
      const minHeight=Math.ceil((Math.max(original.height,reference.height)*snapshot.zoom+24)/.79)+'px';
      originalElement.style.minHeight=minHeight;
      referenceElement.style.minHeight=minHeight;
      // All asynchronous work has finished. The two previews and their metadata
      // commit together, so an older render cannot overwrite a newer selection.
      if(!isCurrent())return;
      drawPreview(originalElement,original,snapshot,backgroundImage);
      drawPreview(referenceElement,reference,snapshot,backgroundImage);
      lastSprite=original;lastReference=reference;
      stats.original={width:original.width,height:original.height};
      stats.reference={width:reference.width,height:reference.height};
      commitMetadata(originalElement,original,snapshot,version);
      commitMetadata(referenceElement,reference,{...snapshot,design:manifest.reference.id||'ro-reference',cloth:'original',hair:'original'},version);
      $('original-size').textContent=`${original.width} × ${original.height} px`;
      $('reference-size').textContent=`${reference.width} × ${reference.height} px`;
      $('active-design-name').textContent=design.name;
      $('design-caption').textContent=snapshot.direction.toUpperCase()+' VIEW';
      if(original.clipped)status('This pose extends past the export canvas. Try another view before exporting.',true);
      else status(`${DIRECTIONS.find(d=>d[0]===snapshot.direction)?.[1]||snapshot.direction} view · ${snapshot.zoom}× preview · PNG exports at native study size.`);
      updateControls();
      return{original,reference};
    }catch(error){if(isCurrent()){status(error.message+' Open this workshop through its local web server.',true);console.error(error);}}
  }
  function commitMetadata(element,sprite,selection,version){
    const digest=digestSprite(sprite);
    element.dataset.spriteHash=digest.hash;
    element.dataset.opaquePixels=String(digest.opaque);
    for(const key of ['design','direction','cloth','hair','zoom'])element.dataset[key]=String(selection[key]);
    element.dataset.renderId=String(version);
  }
  function queueRender(){renderVersion++;if(renderQueued)return;renderQueued=true;requestAnimationFrame(()=>{renderQueued=false;render();});}
  function change(key,value){state[key]=value;save();updateControls();queueRender();}
  function updateControls(){document.querySelectorAll('[data-design]').forEach(button=>{const on=button.dataset.design===state.design;button.classList.toggle('active',on);button.setAttribute('aria-pressed',on);const chosen=button.querySelector('.chosen');if(chosen)chosen.hidden=!on;});document.querySelectorAll('[data-direction]').forEach(button=>button.setAttribute('aria-pressed',button.dataset.direction===state.direction));document.querySelectorAll('[data-tone]').forEach(button=>button.setAttribute('aria-pressed',button.dataset.tone===state[button.dataset.kind]));document.querySelectorAll('[data-zoom]').forEach(button=>button.setAttribute('aria-pressed',Number(button.dataset.zoom)===state.zoom));$('background-select').value=state.background;$('baseline-toggle').checked=state.baseline;$('export-png').disabled=!assetsReady||!lastSprite;$('export-json').disabled=!assetsReady;}
  function buildControls(){for(const[id,label]of DIRECTIONS){const button=document.createElement('button');button.className='direction-button';button.dataset.direction=id;button.textContent=label;button.onclick=()=>change('direction',id);$('direction-controls').append(button);}for(const kind of ['cloth','hair'])for(const[id,label,color]of TONES[kind]){const button=document.createElement('button');button.className='swatch'+(id==='original'?' original':'');button.dataset.kind=kind;button.dataset.tone=id;button.title=label;button.setAttribute('aria-label',label+' '+kind);if(color)button.style.background=color;button.onclick=()=>change(kind,id);$(kind+'-palette').append(button);}for(let zoom=1;zoom<=4;zoom++){const button=document.createElement('button');button.className='segment';button.dataset.zoom=zoom;button.textContent=zoom+'×';button.onclick=()=>change('zoom',zoom);$('zoom-controls').append(button);}$('background-select').onchange=event=>change('background',event.target.value);$('baseline-toggle').onchange=event=>change('baseline',event.target.checked);$('reset-button').onclick=()=>{state={...DEFAULTS,design:manifest?.designs[0]?.id||null};normalized.clear();save();updateControls();queueRender();status('Study reset to its original colors.');};$('export-png').onclick=exportPNG;$('export-json').onclick=exportRecipe;}
  async function buildDesigns(){for(const design of manifest.designs){const button=document.createElement('button');button.className='design-card';button.dataset.design=design.id;button.setAttribute('aria-label',design.name);const thumb=canvas(180,120);thumb.className='thumb';const name=document.createElement('strong');name.textContent=design.name;const note=document.createElement('small');note.textContent=design.subtitle||'Original character study';const chosen=document.createElement('span');chosen.className='chosen';chosen.textContent='✓';chosen.setAttribute('aria-hidden','true');button.append(thumb,name,note,chosen);button.onclick=()=>{state.design=design.id;state.cloth='original';state.hair='original';normalized.clear();save();updateControls();queueRender();};$('design-list').append(button);try{const sprite=await makeSprite(design,true);const ctx=thumb.getContext('2d');ctx.imageSmoothingEnabled=false;ctx.drawImage(sprite.canvas,30,0,120,120);}catch(error){status(error.message,true);}}}
  function showExportResult(url,name,preview=false){
    let wrapper=$('export-result-container');
    if(!wrapper){
      wrapper=document.createElement('div');wrapper.id='export-result-container';
      Object.assign(wrapper.style,{marginTop:'12px',padding:'10px',border:'1px solid #cbd3c0',borderRadius:'4px',background:'#f1f4e8',gridColumn:'1 / -1'});
      $('export-json').insertAdjacentElement('afterend',wrapper);
    }
    wrapper.replaceChildren();
    const link=document.createElement('a');link.id='export-result';link.href=url;link.download=name;
    link.textContent='Download '+name;
    Object.assign(link.style,{display:'block',fontSize:'10px',color:'#3f6250',overflowWrap:'anywhere'});
    wrapper.append(link);
    if(preview){const image=document.createElement('img');image.src=url;image.alt='Exported sprite preview';image.width=64;image.height=64;Object.assign(image.style,{display:'block',imageRendering:'pixelated',margin:'8px auto 0',background:'#e6ebdc'});wrapper.append(image);}
    // Browsers that permit automatic downloads may save immediately. The link
    // remains available when an embedded browser requires an explicit click.
    link.click();
    return link;
  }
  async function exportPNG(){
    const snapshot={...state},filename=`${state.design}-${state.direction}.png`;
    try{
      const sprite=await makeSprite(chosenDesign(snapshot),false,snapshot);
      const url=sprite.canvas.toDataURL('image/png');
      showExportResult(url,filename,true);
      status('PNG ready · use the download link to save.');
    }catch(error){status('PNG export failed: '+error.message,true);}
  }
  function exportRecipe(){
    const snapshot={...state},design=chosenDesign(snapshot),frame=frameFor(design,snapshot);
    const recipe={schema:'character-atelier/1',study:'static-four-view',...snapshot,source:{file:frame.file||design.file,frame},export:{width:128,height:128,baseline:112,displayHeight:frame.displayHeight||design.displayHeight||94}};
    const filename=`${snapshot.design}-recipe.json`;
    showExportResult('data:application/json;charset=utf-8,'+encodeURIComponent(JSON.stringify(recipe,null,2)+'\n'),filename);
    status('Recipe ready · use the download link to save.');
  }
  function digestSprite(sprite){
    const data=sprite.canvas.getContext('2d').getImageData(0,0,128,128).data;
    let hash=2166136261,opaque=0;
    for(let i=0;i<data.length;i++){hash=Math.imul(hash^data[i],16777619);if(i%4===3&&data[i]>0)opaque++;}
    return{hash:(hash>>>0).toString(16).padStart(8,'0'),opaque,width:128,height:128};
  }
  function getPixelDigest(target='original'){const sprite=target==='reference'?lastReference:lastSprite;return sprite?digestSprite(sprite):null;}
  window.characterLab={get state(){return{...state};},get manifest(){return manifest;},get stats(){return structuredClone(stats);},render,getPixelDigest,setState(values){for(const key of Object.keys(DEFAULTS))if(key in values)state[key]=values[key];save();updateControls();return render();},exportPNG,exportRecipe};
  async function initialize(){buildControls();try{const response=await fetch('assets/manifest.json',{cache:'no-store'});if(!response.ok)throw new Error('The local asset manifest is not ready ('+response.status+').');manifest=await response.json();if(!Array.isArray(manifest.designs)||!manifest.designs.length||!manifest.reference)throw new Error('The local manifest needs original designs and an RO reference.');if(!manifest.designs.some(d=>d.id===state.design))state.design=manifest.designs[0].id;if(!DIRECTIONS.some(d=>d[0]===state.direction))state.direction='south';if(![1,2,3,4].includes(state.zoom))state.zoom=2;for(const kind of ['cloth','hair'])if(!TONES[kind].some(t=>t[0]===state[kind]))state[kind]='original';if(!['field','checker','plain'].includes(state.background))state.background='field';state.baseline=Boolean(state.baseline);await buildDesigns();assetsReady=true;save();await render();}catch(error){status(error.message+' Start the local web server and check the assets folder.',true);console.error(error);}new ResizeObserver(queueRender).observe($('original-canvas'));new ResizeObserver(queueRender).observe($('reference-canvas'));}
  initialize();
})();
