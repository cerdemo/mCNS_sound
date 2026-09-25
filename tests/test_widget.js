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
const motor={escape_drive:0,turn_drive:0,landing_drive:0};
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
