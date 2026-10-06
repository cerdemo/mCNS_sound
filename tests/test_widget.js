const assert = require('node:assert/strict');
const {NeuralReadout, FlyAgent, imageAnchors} = require('../mcns/widget-core.js');
const readout = new NeuralReadout([
  {input:true,hex:[0,0],population:'input'},
  {input:false,hex:[0,0],population:'left'},
  {input:false,hex:[2,2],population:'right'}
]);
assert.equal(readout.update([100,0,0]).activity,0);
assert.equal(readout.update([100,0,20]).x,1);
assert.equal(readout.update([100,20,0]).x,0);
const drive={x:.5,y:.5,activity:.3};
const anchors=[];
for(let x=.1;x<.95;x+=.07)for(let y=.1;y<.95;y+=.07)anchors.push({x,y,kind:'edge'});
const a=new FlyAgent(42), b=new FlyAgent(42), modes=new Set();
for(let i=0;i<3600;i++){
  const f=a.update(1/60,drive,null,anchors);
  assert.deepEqual(f,b.update(1/60,drive,null,anchors));
  assert.ok(f.x>=0&&f.x<=1&&f.y>=0&&f.y<=1);
  modes.add(f.mode);
  if(f.mode==='walking')assert.equal(f.gain,0);
}
assert.ok(modes.has('flying')&&modes.has('walking'));
for(const state of ['escaping','hidden']){
 const f=a.update(.05,drive,{tracking_valid:true,state,gain:state==='hidden'?0:1,x:.1,y:.1});
 assert.equal(f.mode,state);
 if(state==='hidden')assert.equal(f.wing_hz,0);
}
assert.equal(a.update(.05,drive,null,[],false).gain,0);
const low=new FlyAgent(42), high=new FlyAgent(42);
let lo,hi;
for(let i=0;i<5;i++){lo=low.update(.05,{...drive,activity:0},null);hi=high.update(.05,{...drive,activity:1},null);}
assert.ok(hi.speed>lo.speed&&hi.wing_hz>lo.wing_hz);
assert.deepEqual(imageAnchors(new Uint8Array(128*128),128,128),[]);
const pixels=new Uint8Array(128*128);pixels.fill(255,64*128);
assert.ok(imageAnchors(pixels,128,128).length>0);
console.log('Widget: neural causality, deterministic flight/walk, fear/mute and scene anchors passed.');
const {EmbodiedAgent}=require('../mcns/widget-core.js');
const embodiedA=new EmbodiedAgent(42),embodiedB=new EmbodiedAgent(42);
const motor={escape_drive:0,turn_drive:0,landing_drive:0,locomotion_drive:.3,probe_left:.3,probe_right:.3};
for(let i=0;i<100;i++){
 const one=embodiedA.update(.02,drive,motor,{objects:[]});
 const two=embodiedB.update(.02,drive,motor,{objects:[{id:1,label:'person',box:[.01,.01,.1,.1],velocity:[10,10]}]});
 assert.equal(one.x,two.x);assert.equal(one.y,two.y); // Remote human motion is not fear input.
}
const perched=new EmbodiedAgent();perched.contact=7;perched.lastBox=[.2,.3,.8,.8];perched.x=.4;perched.y=.312;
const carried=perched.update(.02,drive,motor,{objects:[{id:7,box:[.3,.4,.9,.9]}]});
assert.equal(carried.mode,'walking');assert.ok(carried.x>.5&&carried.y>.4);assert.equal(carried.gain,0);
const takeoff=perched.update(.02,drive,{...motor,escape_drive:.8},{objects:[{id:7,box:[.3,.4,.9,.9]}]});
assert.equal(takeoff.mode,'escaping');assert.equal(takeoff.contact_id,null);
console.log('Embodiment: unrelated movement ignored, moving support carried, DN-driven takeoff passed.');

const {crawlerRig}=require('../mcns/widget-core.js');
const silent=new EmbodiedAgent(), moving=new EmbodiedAgent();
for(let i=0;i<300;i++){
  const f=silent.update(1/60,{...drive,activity:1},{},{});
  assert.equal(f.x,.5);assert.equal(f.y,.4);assert.equal(f.angle,0);assert.equal(f.phase,0);assert.equal(f.gain,0);
}
let active;
for(let i=0;i<30;i++)active=moving.update(1/60,drive,{...motor,turn_drive:.4},{});
assert.ok(Math.hypot(active.x-.5,active.y-.4)>.02&&active.angle>0&&active.phase>0);
const rig=crawlerRig(active,2,1.4);
assert.equal(rig.probes.length,8);assert.equal(new Set(rig.probes.map(p=>p.id)).size,8);
rig.limbs.forEach((limb,i)=>assert.deepEqual(rig.probes[i],{id:limb.id,...limb.points.at(-1)}));
const stoppedRig=crawlerRig(silent.update(.01,drive,{},{}));
assert.deepEqual(stoppedRig,crawlerRig(silent.update(.05,drive,{},{})));
const straight={...active,angle:0};
const wide=crawlerRig(straight,2),square=crawlerRig(straight,1);
wide.probes.forEach((p,i)=>assert.ok(Math.abs((p.x-active.x)*2-(square.probes[i].x-active.x))<1e-10));
const noLanding=new EmbodiedAgent();noLanding.x=.4;noLanding.y=.3;
assert.equal(noLanding.update(.02,drive,motor,{objects:[{id:8,box:[.2,.3,.8,.8]}]}).contact_id,null);
assert.equal(noLanding.update(.02,drive,{...motor,landing_drive:.5},{objects:[{id:8,box:[.2,.3,.8,.8]}]}).contact_id,8);
console.log('Crawler: zero neural drive stops body and limbs; turn, gait, shared probes and neural landing passed.');

const headingRig=crawlerRig({...active,angle:.7},16/9);
assert.ok(Math.abs((headingRig.head.y-active.y)/(headingRig.head.x-active.x)-Math.tan(.7))<1e-10);
const edge=new EmbodiedAgent();edge.x=.03;edge.angle=Math.PI;
for(let i=0;i<100;i++)assert.equal(edge.update(.02,drive,{},{}).angle,Math.PI);

// Measured neural onsets produce brief, directed bursts; a held signal does not retrigger.
const {NeuralMotion}=require('../mcns/widget-core.js');
const express=new NeuralMotion();
const quiet={locomotion_drive:.015,escape_drive:0,turn_drive:0,probe_left:.015,probe_right:.015};
let calm;
for(let i=0;i<120;i++)calm=express.update(1/60,quiet);
assert.equal(calm.burst,0);assert.equal(calm.turnRate,0);
assert.ok(calm.speed>.09&&calm.speed<.2);
const alarm={...quiet,escape_drive:.15,turn_drive:.18,probe_right:.08};
let peak=express.update(1/60,alarm);
assert.ok(peak.speed>5*calm.speed);assert.ok(peak.turnRate>6);
assert.ok(peak.phaseRate>3*calm.phaseRate);assert.ok(peak.probe_left>.6);
for(let i=0;i<120;i++)peak=express.update(1/60,alarm);
assert.ok(peak.burst<1e-5); // No repeated timer bursts on an unchanging observation.
for(let i=0;i<120;i++)peak=express.update(1/60,{});
assert.equal(peak.speed,0);assert.equal(peak.turnRate,0);assert.equal(peak.phaseRate,0);
const restrained=new NeuralMotion(),dramatic=new NeuralMotion();
restrained.update(.02,quiet,.5);dramatic.update(.02,quiet,2.5);
assert.ok(dramatic.update(.02,alarm,2.5).speed>restrained.update(.02,alarm,.5).speed);
// A symmetric neural response cannot invent a turn direction.
const symmetrical=new NeuralMotion();symmetrical.update(.02,quiet);
assert.equal(symmetrical.update(.02,{...quiet,escape_drive:.2}).turnRate,0);
// Mid-flight braking, endpoint motion, and offline/reconnect must remain finite and bounded.
const fast=new EmbodiedAgent();
for(let i=0;i<30;i++)fast.update(1/60,drive,quiet,{});
let fastest=0;
for(let i=0;i<30;i++){
  const f=fast.update(1/60,drive,alarm,{});fastest=Math.max(fastest,f.speed);
  assert.ok(f.x>=.03&&f.x<=.97&&f.y>=.03&&f.y<=.96);
  assert.ok(crawlerRig(f).probes.every(p=>Number.isFinite(p.x)&&Number.isFinite(p.y)));
}
assert.ok(fastest>.7);
for(let i=0;i<180;i++)fast.update(1/60,drive,{},{});
assert.equal(fast.flightSpeed,0);
assert.equal(fast.update(.02,drive,alarm,{},false).gain,0);
const resumed=fast.update(.02,drive,quiet,{});
assert.equal(resumed.burst,0);
console.log('Agility: neural onset boosts speed/gait, directed saccade, no timer retrigger, gain control and quiet braking passed.');
