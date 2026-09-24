// ACT selects complete SPR drawings. This module never invents joints or in-between poses.
export function nativeFrameAt(time, count, delayMs) {
  if (!Number.isFinite(time) || count < 1 || !(delayMs > 0)) throw new RangeError('Invalid native timeline.');
  return Math.min(count - 1, Math.max(0, Math.floor(time / delayMs)));
}

export function nativePartFrame(template, part, frameIndex, action='attack') {
  const frames=template.parts[part].actions[action].frames;
  return frames[frameIndex % frames.length];
}

export function headAttachment(body, head) {
  return body.anchors.length && head.anchors.length
    ? [body.anchors[0][0]-head.anchors[0][0],body.anchors[0][1]-head.anchors[0][1]] : [0,0];
}

export function composeNative(template, textures, frameIndex, options={}) {
  const [width,height]=template.canvas, out=new Uint8ClampedArray(width*height*4);
  const action=options.action || 'attack';
  const body=nativePartFrame(template,'body',frameIndex,action);
  // This facing draws the equipped headgear after the head. Its own ACT anchor
  // attaches to the body's anchor, exactly like the native head part.
  for(const part of ['body','head','headgear','weapon','trail']) {
    if(!template.parts[part])continue;
    if(options[part]===false)continue;
    const frame=nativePartFrame(template,part,frameIndex,action);
    const attachment=(part==='head'||part==='headgear') ? headAttachment(body,frame) : [0,0];
    for(const layer of frame.layers) {
      if(layer.index<0)continue;
      const image=textures[part]?.[layer.index];
      if(!image)throw new Error(`Missing ${part} SPR image ${layer.index}`);
      const [sxScale,syScale]=layer.scale;
      if(Math.abs(sxScale)<.001 || Math.abs(syScale)<.001)continue;
      const cx=template.origin[0]+layer.x+attachment[0], cy=template.origin[1]+layer.y+attachment[1];
      const radius=Math.hypot(image.width*sxScale,image.height*syScale)/2+2;
      const cos=Math.cos(-layer.rotation),sin=Math.sin(-layer.rotation);
      for(let y=Math.max(0,Math.floor(cy-radius));y<Math.min(height,Math.ceil(cy+radius));y++) {
        for(let x=Math.max(0,Math.floor(cx-radius));x<Math.min(width,Math.ceil(cx+radius));x++) {
          const dx=x+.5-cx,dy=y+.5-cy;
          let u=(dx*cos-dy*sin)/sxScale;
          const v=(dx*sin+dy*cos)/syScale;
          if(layer.mirror)u=-u;
          const sourceX=Math.floor(u+image.width/2),sourceY=Math.floor(v+image.height/2);
          if(sourceX<0||sourceY<0||sourceX>=image.width||sourceY>=image.height)continue;
          const source=(sourceY*image.width+sourceX)*4, dest=(y*width+x)*4;
          const alpha=image.data[source+3]/255*layer.color[3];
          if(alpha<=0)continue;
          const prior=out[dest+3]/255,combined=alpha+prior*(1-alpha);
          for(let c=0;c<3;c++)out[dest+c]=(image.data[source+c]*layer.color[c]*alpha+out[dest+c]*prior*(1-alpha))/combined;
          out[dest+3]=combined*255;
        }
      }
    }
  }
  return {width,height,data:out};
}

export function pixelDifference(actual, expected) {
  if(actual.width!==expected.width || actual.height!==expected.height)return {pixels:Infinity,maxChannelDelta:255};
  let pixels=0,maxChannelDelta=0;
  for(let i=0;i<actual.data.length;i+=4) {
    let changed=false;
    for(let c=0;c<4;c++){const delta=Math.abs(actual.data[i+c]-expected.data[i+c]);if(delta){changed=true;maxChannelDelta=Math.max(maxChannelDelta,delta);}}
    if(changed)pixels++;
  }
  return {pixels,maxChannelDelta};
}
