import { POSES, DEFAULT_TIMING, timeline, samplePose, crossedContact, validateTiming } from './modular-motion.mjs';

const ASSET_ROOT = './assets/modular-v1/';
const VERSION = 1;
const clone = value => JSON.parse(JSON.stringify(value));
const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const offset = () => ({weaponX: 0, weaponY: 0, weaponAngle: 0, hatX: 0, hatY: 0});
const defaults = () => ({hat: 'scout', weapon: 'arming', mode: 'weighted', anchors: false,
  trails: false, feedback: false, targetInRange: true, visible: {body: true, head: true, hat: true, weapon: true},
  timing: {...DEFAULT_TIMING}, attachments: POSES.map(offset)});

function finite(value, name, min, max) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max)
    throw new Error(`${name} must be a number between ${min} and ${max}.`);
  return value;
}

export function validateProject(data) {
  if (!data || data.version !== VERSION || data.type !== 'wayfarer-modular-attack')
    throw new Error('Choose a Wayfarer modular attack JSON exported by this workshop.');
  const v = data.config;
  if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error('Missing character settings.');
  const result = defaults();
  for (const [key, options] of Object.entries({hat: ['none','scout','cap'], weapon: ['arming','falchion'], mode: ['weighted','armOnly']})) {
    if (!options.includes(v[key])) throw new Error(`Unknown ${key}.`);
    result[key] = v[key];
  }
  for (const key of ['anchors','trails','feedback','targetInRange']) {
    if (typeof v[key] !== 'boolean') throw new Error(`Invalid ${key}.`);
    result[key] = v[key];
  }
  for (const key of ['body','head','hat','weapon']) {
    if (typeof v.visible?.[key] !== 'boolean') throw new Error(`Invalid ${key} visibility.`);
    result.visible[key] = v.visible[key];
  }
  if (!v.timing || typeof v.timing !== 'object' || ['windup','strike','recovery'].some(key => !Object.hasOwn(v.timing,key)))
    throw new Error('Timing must include windup, strike and recovery.');
  result.timing = validateTiming(v.timing);
  if (!Array.isArray(v.attachments) || v.attachments.length !== POSES.length) throw new Error('Expected six pose attachment records.');
  result.attachments = v.attachments.map((a, i) => {
    const o = {};
    for (const key of Object.keys(offset())) o[key] = finite(a?.[key], `Pose ${i + 1} ${key}`, key === 'weaponAngle' ? -90 : -30, key === 'weaponAngle' ? 90 : 30);
    return o;
  });
  return result;
}

export function segmentDistance(point, a, b) {
  const dx = b[0] - a[0], dy = b[1] - a[1];
  const t = clamp(((point[0]-a[0])*dx+(point[1]-a[1])*dy)/(dx*dx+dy*dy || 1), 0, 1);
  return Math.hypot(point[0] - a[0] - t*dx, point[1] - a[1] - t*dy);
}

async function loadParts() {
  const response = await fetch(ASSET_ROOT + 'atlas.json');
  if (!response.ok) throw new Error('The character atlas could not be loaded.');
  const manifest = await response.json();
  const image = new Image();
  image.src = ASSET_ROOT + manifest.image;
  await image.decode();
  const parts = {};
  for (const [name, rect] of Object.entries(manifest.parts)) {
    const [sx,sy,w,h] = rect;
    const canvas = document.createElement('canvas'); canvas.width=w; canvas.height=h;
    const c=canvas.getContext('2d',{willReadFrequently:true});
    c.drawImage(image,sx,sy,w,h,0,0,w,h);
    const pixels=c.getImageData(0,0,w,h), d=pixels.data;
    let left=w,top=h,right=0,bottom=0;
    for(let y=0;y<h;y++) for(let x=0;x<w;x++) {
      const i=(y*w+x)*4;
      // A texture transparency key, applied once on load. Source art stays untouched.
      if(d[i]>170 && d[i+2]>150 && d[i+1]<115 && d[i]+d[i+2]-2*d[i+1]>210) d[i+3]=0;
      if(d[i+3]>128){left=Math.min(left,x);right=Math.max(right,x);top=Math.min(top,y);bottom=Math.max(bottom,y);}
    }
    c.putImageData(pixels,0,0);
    if(left>right) throw new Error(`Missing atlas part: ${name}`);
    const cropped=document.createElement('canvas');cropped.width=right-left+1;cropped.height=bottom-top+1;
    cropped.getContext('2d').drawImage(canvas,left,top,cropped.width,cropped.height,0,0,cropped.width,cropped.height);
    parts[name]=cropped;
  }
  return parts;
}

export async function createWorkshop(canvas, {onUpdate = () => {}} = {}) {
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Canvas rendering is unavailable.');
  const parts = await loadParts();
  let config = defaults();
  let time = 0, playing = false, paused = false, speed = 1, loop = false, selected = 0;
  let hitCount = 0, contact = false, eventMessage = 'Ready. Try an attack, then change the equipment.';
  let last = performance.now(), lastNotify = 0, hitAt = -Infinity, contactConsumed = false, restartAt = 0;
  let stopped = false, animationId, hitPauseUntil = 0;
  const SCALE = 2.8, ROOT = [325,394];
  const getTimeline = () => timeline(config.timing);
  const getPose = t => {
    const track=getTimeline();
    // Include the contact cel in the display cadence, even between 24 fps samples.
    if (t>=track.contactTime && t<Math.min(track.followStart,track.contactTime+34))
      return samplePose(track.contactTime,config.timing,config.mode,{interpolate:true});
    return samplePose(t, config.timing, config.mode, {interpolate:true, fps:24});
  };
  const getOffset = pose => {
    const track=getTimeline(), t=pose.sampledTime ?? pose.timeMs;
    const knots=[track.windupStart,...track.poseTimes.slice(1),track.settledStart];
    const indexes=[0,1,2,3,4,5,0];
    if(t<=knots[0] || t>=knots.at(-1)) return config.attachments[0];
    let i=0;while(i<knots.length-2 && t>knots[i+1])i++;
    let ratio=(t-knots[i])/(knots[i+1]-knots[i]);
    if(i===4 && t<track.recoveryStart) ratio=0;
    else if(i===4) ratio=(t-track.recoveryStart)/(knots[i+1]-track.recoveryStart);
    if(i===0 || i>=4)ratio=ratio*ratio*(3-2*ratio);
    const from=config.attachments[indexes[i]],to=config.attachments[indexes[i+1]];
    return Object.fromEntries(Object.keys(offset()).map(key=>[key,from[key]+(to[key]-from[key])*ratio]));
  };
  const target = () => [config.targetInRange ? 58 : 105, -43];

  function state() {
    const pose=getPose(time), tl=getTimeline();
    return {ready:true,playing,paused,time,duration:tl.duration,poseIndex:pose.poseIndex,phase:pose.phase,
      hitCount,contact,contactTime:tl.contactTime,poseTimes:tl.poseTimes,speed,loop,
      config:{...clone(config), attachment:{...config.attachments[selected],pose:selected}},message:eventMessage};
  }
  function notify() { onUpdate(state()); }
  function transformSprite(name,x,y,w,h,angle=0,anchorX=.5,anchorY=.5,alpha=1) {
    ctx.save();ctx.translate(x,y);ctx.rotate(angle*Math.PI/180);ctx.globalAlpha=alpha;
    ctx.imageSmoothingEnabled=false;
    ctx.drawImage(parts[name],-w*anchorX,-h*anchorY,w,h);ctx.restore();
  }
  function segment(name,a,b,width,overlap=2,alpha=1) {
    const length=Math.hypot(b[0]-a[0],b[1]-a[1]);
    const angle=Math.atan2(b[1]-a[1],b[0]-a[0])*180/Math.PI-90;
    transformSprite(name,(a[0]+b[0])/2,(a[1]+b[1])/2,width,length+overlap*2,angle,.5,.5,alpha);
  }
  function swordGeometry(pose, attached=getOffset(pose)) {
    const angle=(pose.swordAngle+attached.weaponAngle)*Math.PI/180;
    const hand=[pose.wrist[0]+attached.weaponX,pose.wrist[1]+attached.weaponY];
    return {hand,angle,base:[hand[0]+Math.cos(angle)*8,hand[1]+Math.sin(angle)*8],
      tip:[hand[0]+Math.cos(angle)*43,hand[1]+Math.sin(angle)*43]};
  }
  function eventAtContact() {
    if(contactConsumed) return;
    contactConsumed=true;
    const p=samplePose(getTimeline().contactTime,config.timing,config.mode,{interpolate:true});
    const sword=swordGeometry(p);
    contact=config.visible.weapon && segmentDistance(target(),sword.base,sword.tip)<=13;
    if(contact) {hitCount++;hitAt=performance.now();eventMessage=`Hit ${hitCount} · contact at ${Math.round(getTimeline().contactTime)} ms.`;
      if(config.feedback){time=getTimeline().contactTime;hitPauseUntil=hitAt+65;}
    }
    else eventMessage='Miss · the blade did not reach the target at the contact pose.';
  }
  function render(now) {
    const W=canvas.width,H=canvas.height,p=getPose(time),a=getOffset(p),tl=getTimeline();
    ctx.clearRect(0,0,W,H);
    const gradient=ctx.createLinearGradient(0,0,0,H);gradient.addColorStop(0,'#eeeee2');gradient.addColorStop(.65,'#e4e8d7');gradient.addColorStop(1,'#d8dfc7');
    ctx.fillStyle=gradient;ctx.fillRect(0,0,W,H);
    // Quiet ground marks establish distance without obscuring silhouettes.
    ctx.strokeStyle='#c4cfb7';ctx.lineWidth=1;
    for(let i=-4;i<=6;i++){ctx.beginPath();ctx.moveTo(W*.5+i*95,330);ctx.lineTo(W*.5+i*145,H);ctx.stroke();}
    for(const y of [357,389,435]) {ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(W,y);ctx.stroke();}
    ctx.fillStyle='#738063';ctx.font='11px system-ui';ctx.fillText('ONE DIRECTION  /  ORIGINAL PARTS  /  SHARED TIMELINE',27,30);
    ctx.textAlign='right';ctx.fillText(config.mode==='weighted'?'FULL BODY MOTION':'ARM-ONLY COMPARISON',W-27,30);ctx.textAlign='left';
    ctx.save();ctx.translate(...ROOT);ctx.scale(SCALE,SCALE);
    const t=target();
    ctx.fillStyle='#56644324';ctx.beginPath();ctx.ellipse(0,1,23,5,0,0,Math.PI*2);ctx.fill();
    ctx.beginPath();ctx.ellipse(t[0],1,18,5,0,0,Math.PI*2);ctx.fill();
    let shake=0;
    const impactAge=now-hitAt;
    if(config.feedback && impactAge<240) shake=Math.sin(impactAge*.07)*3*(1-impactAge/240);
    transformSprite('dummy',t[0]+shake,-30,39,60,config.feedback&&impactAge<150 ? Math.sin(impactAge*.06)*3 : 0);
    if(config.anchors) {
      ctx.strokeStyle='#bf7d3b';ctx.lineWidth=.5;ctx.setLineDash([2,2]);ctx.beginPath();ctx.arc(...t,13,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
    }
    if(config.visible.body) {
      segment('upperArm',p.rearShoulder,p.rearElbow,10,2,.87);
      segment('forearm',p.rearElbow,p.rearWrist,7,1.5,.87);
      transformSprite('freeHand',...p.rearWrist,7,8,0,.5,.3,.88);
      segment('thigh',[p.hips[0]-7,p.hips[1]+3],p.rearKnee,12,3,.93);
      segment('boot',p.rearKnee,p.rearAnkle,14,2,.93);
      segment('thigh',[p.hips[0]+6,p.hips[1]+4],p.knee,13,3);
      segment('boot',p.knee,p.ankle,15,2);
      transformSprite('pelvis',p.hips[0],p.hips[1]+6,27,21);
      const torso={ready:'torsoReady',coil:'torsoCoil',follow:'torsoFollow'}[p.torsoVariant] || 'torsoReady';
      const center=[(p.neck[0]+p.hips[0])/2,(p.neck[1]+p.hips[1])/2];
      transformSprite(torso,...center,29,Math.hypot(p.hips[0]-p.neck[0],p.hips[1]-p.neck[1])+4,p.torsoAngle || 0);
    }
    const behindHead=p.wrist[1]<p.neck[1]-4;
    const arm=()=>{
      if(config.visible.body){segment('upperArm',p.shoulder,p.elbow,10.5,2);segment('forearm',p.elbow,p.wrist,7.7,1.8);}
      if(config.trails && config.visible.weapon && time>tl.contactTime-45 && time<tl.contactTime+105) {
        ctx.strokeStyle='#fffbdbbb';ctx.lineWidth=2.2;
        ctx.beginPath();
        for(let dt=-50;dt<=0;dt+=10){const q=swordGeometry(getPose(Math.max(0,time+dt)));dt===-50?ctx.moveTo(...q.tip):ctx.lineTo(...q.tip);}ctx.stroke();
      }
      if(config.visible.weapon) {
        const geometry=swordGeometry(p,a);
        transformSprite(config.weapon,...geometry.hand,55,config.weapon==='arming'?17.4:17.8,p.swordAngle+a.weaponAngle,.2,.5);
      }
      if(config.visible.body) transformSprite('grip',...p.wrist,8.5,8,p.swordAngle+35);
    };
    if(behindHead) arm();
    const head=[p.head[0],p.head[1]+6];
    if(config.visible.head) transformSprite('head',...head,28.5,28.5,0,.5,.5);
    if(config.hat!=='none' && config.visible.hat) {
      if(config.hat==='scout') transformSprite('scout',head[0]+a.hatX+1,head[1]+a.hatY-10,28,23);
      else transformSprite('cap',head[0]+a.hatX,head[1]+a.hatY-11,31,18);
    }
    if(!behindHead) arm();
    if(config.anchors) {
      const chain=[p.shoulder,p.elbow,p.wrist];ctx.strokeStyle='#9e5236';ctx.lineWidth=.55;
      ctx.beginPath();chain.forEach((v,i)=>i?ctx.lineTo(...v):ctx.moveTo(...v));ctx.stroke();
      for(const [label,pos,color] of [['hand',p.wrist,'#ae5239'],['head',head,'#3c716e'],['root',[0,0],'#59673d']]){
        ctx.strokeStyle=color;ctx.beginPath();ctx.arc(...pos,1.8,0,Math.PI*2);ctx.stroke();
        ctx.fillStyle=color;ctx.font='3.8px system-ui';ctx.fillText(label,pos[0]+3,pos[1]-3);
      }
      const s=swordGeometry(p);ctx.strokeStyle='#ae5239';ctx.beginPath();ctx.moveTo(...s.base);ctx.lineTo(...s.tip);ctx.stroke();
    }
    if(config.feedback && impactAge<300) {
      ctx.globalAlpha=1-impactAge/300;ctx.fillStyle='#8a502e';ctx.font='bold 8px Georgia';ctx.textAlign='center';ctx.fillText('HIT',t[0],-73-impactAge/35);ctx.textAlign='left';ctx.globalAlpha=1;
    }
    ctx.restore();
    ctx.fillStyle='#61704e';ctx.font='12px system-ui';ctx.fillText('WAYFARER',ROOT[0]-34,ROOT[1]+37);
    ctx.textAlign='center';ctx.fillText(config.targetInRange?'TRAINING DUMMY':'DUMMY · OUT OF RANGE',ROOT[0]+t[0]*SCALE,ROOT[1]+37);ctx.textAlign='left';
  }
  function frame(now) {
    if(stopped)return;
    const dt=Math.min(Math.max(now-last,0),100);last=now;
    if(playing && !paused) {
      const duration=getTimeline().duration;
      if(restartAt && now>=restartAt) {time=0;contactConsumed=false;contact=false;restartAt=0;}
      if(!restartAt && now>=hitPauseUntil) {
        const previous=time;time=Math.min(duration,time+dt*speed);
        if(crossedContact(previous,time,config.timing)) eventAtContact();
        if(time>=duration) {
          if(loop) restartAt=now+450;
          else {playing=false;paused=false;}
        }
      }
      selected=getPose(time).poseIndex;
    }
    render(now);
    if(now-lastNotify>45) {notify();lastNotify=now;}
    animationId=requestAnimationFrame(frame);
  }
  const app = {
    attack(){time=0;selected=0;playing=true;paused=false;contact=false;contactConsumed=false;restartAt=0;hitPauseUntil=0;eventMessage='Attack started.';last=performance.now();notify();},
    togglePause(){if(!playing){if(time>=getTimeline().duration)time=0;playing=true;paused=false;contactConsumed=time>=getTimeline().contactTime;restartAt=0;}else paused=!paused;last=performance.now();notify();},
    setLoop(value){loop=Boolean(value);if(!loop)restartAt=0;notify();},
    setSpeed(value){speed=finite(value,'Playback speed',.1,3);notify();},
    seek(value){time=clamp(finite(value,'Time',0,10000),0,getTimeline().duration);playing=false;paused=false;selected=getPose(time).poseIndex;contact=false;contactConsumed=time>=getTimeline().contactTime;restartAt=0;hitPauseUntil=0;eventMessage='Pose preview · scrubbing does not deal damage.';render(performance.now());notify();},
    selectPose(index){selected=clamp(Math.round(index),0,POSES.length-1);app.seek(getTimeline().poseTimes[selected]);},
    configure(patch){
      const next=clone(config);
      for(const key of ['hat','weapon','mode','anchors','trails','feedback','targetInRange']) if(key in patch) next[key]=patch[key];
      if(patch.visible) next.visible={...next.visible,...patch.visible};
      if(patch.timing) next.timing={...next.timing,...patch.timing};
      if(patch.attachment){const {pose=selected,index,...values}=patch.attachment;const n=clamp(Math.round(index??pose),0,POSES.length-1);next.attachments[n]={...next.attachments[n],...values};}
      config=validateProject({version:VERSION,type:'wayfarer-modular-attack',config:next});
      // Timing edits are an authoring operation; stop, retain the selected pose, and re-arm only on play.
      if(patch.timing){time=getTimeline().poseTimes[selected];playing=false;paused=false;contactConsumed=time>=getTimeline().contactTime;restartAt=0;contact=false;}
      render(performance.now());notify();
    },
    reset(){config=defaults();time=0;selected=0;playing=false;paused=false;loop=false;speed=1;hitCount=0;contact=false;contactConsumed=false;restartAt=0;hitPauseUntil=0;hitAt=-Infinity;eventMessage='Default poses and equipment restored.';notify();},
    exportData(){return {type:'wayfarer-modular-attack',version:VERSION,config:clone(config),poseIds:POSES.map(p=>p.id),source:'Original parts atlas + authored joints. One direction. No video frames.'};},
    importData(data){const validated=validateProject(data);config=validated;time=0;selected=0;playing=false;paused=false;contact=false;contactConsumed=false;restartAt=0;hitPauseUntil=0;eventMessage='Character settings imported.';notify();},
    getState:state,
    dispose(){stopped=true;cancelAnimationFrame(animationId);}
  };
  // Exposed intentionally for reproducible workshop QA and debugging this local PoC.
  window.modularWorkshop=app;
  render(performance.now());notify();animationId=requestAnimationFrame(frame);
  return app;
}
