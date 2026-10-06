const fs=require('fs'), vm=require('vm'), assert=require('assert');
const elements=new Map();
const element=id=>{if(!elements.has(id))elements.set(id,{textContent:'',disabled:false});return elements.get(id);};
class Player {
  constructor(){this.currentTime=0;this.duration=2;this.paused=true;}
  pause(){this.paused=true;}
  play(){this.paused=false;return Promise.resolve();}
  removeAttribute(){this.src='';}
}
let requests=0;
const sandbox={window:{addEventListener(){}},document:{getElementById:element,addEventListener(){},hidden:false},
  Audio:Player,setInterval(){},performance:{now:()=>100},fetch(){requests++;return Promise.resolve();},Float32Array,Math};
vm.runInNewContext(fs.readFileSync('mcns/source-audio.js','utf8'),sandbox);
(async()=>{
 const audio=new sandbox.window.MCNSSourceAudio();
 const state={status:'running',run_id:'first',source:'video',video_position_s:.5,auditory:{available:true,valid:true,neurons:102,source:'video',rms:.02}};
 const video={id:'local',has_audio:true,audio_status:'Audio ready'};
 audio.update(state,video);
 assert(audio.player.src.endsWith('/local.wav'));
 await audio.toggleVideo();assert(!audio.player.paused);assert(audio.enabled);
 audio.update({...state,video_position_s:1.2},video);assert.equal(audio.player.currentTime,1.2);
 await audio.toggleVideo();assert(audio.player.paused);assert(!audio.enabled);
 assert.equal(requests,0); // Mute never sends a neural-control or auditory-input command.
 assert(element('hearingStatus').textContent.includes('Hearing video'));
 await audio.toggleVideo();audio.update({...state,video_position_s:.1},video);assert.equal(audio.player.currentTime,.1); // loop
 audio.update({...state,video_position_s:3},video);assert(audio.player.paused); // short soundtrack must not restart
 audio.update({...state,status:'stopped'},video);assert(!audio.enabled);assert(audio.player.paused);
 audio.update({...state,source:'camera'},video);assert(!element('microphoneToggle').disabled);
 let stopped=false;audio.stream={getTracks:()=>[{stop(){stopped=true;}}]};
 audio.update({...state,status:'stopped'},video);assert(stopped);assert.equal(audio.stream,null);
 console.log('Source audio: mute independence, playback clock/loop/end, and microphone cleanup passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
