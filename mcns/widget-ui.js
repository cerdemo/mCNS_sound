(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const {NeuralReadout, FlyAgent, EmbodiedAgent, crawlerRig, imageAnchors, clamp} = window.MCNSWidget;
  const scene = $('flyScene'), canvas = $('flyCanvas'), context = canvas.getContext('2d');
  let agent = new FlyAgent(), readout, drive = {x:.5,y:.5,activity:0,hz:0,leaders:[]};
  let telemetry = null, receivedAt = 0, lastTime = performance.now(), lastPost = 0;
  let runId = null, anchors = [], lastAnalysis = 0, sending = false;
  let uploading=false, importedVideo=null;
  let showPerches = false, recurrence = true, selectedProbe = 'antenna-L';
  let circuitGroups = null;
  const trails = new Map();
  const limbNames = ['leg-L1','leg-L2','leg-L3','leg-R1','leg-R2','leg-R3','antenna-L','antenna-R'];
  for (const name of limbNames) {
    const button=document.createElement('button');button.className='sensor-card';button.dataset.probe=name;
    const swatch=document.createElement('span');swatch.className='sensor-swatch';
    const text=document.createElement('span'), title=document.createElement('strong'), value=document.createElement('small');
    title.textContent=name.toUpperCase();value.textContent='No signal';text.append(title,value);button.append(swatch,text);
    button.onclick=()=>{selectedProbe=name;renderSensors();};$('probeCards').append(button);
  }
  const stages=[['auditory','Auditory input','JO-A / JO-B'],['input','Visual input','L1 / L2'],['optic','Optic network','Recurrent processing'],
    ['projection','Visual projection','Optic → central pathways'],['central','Central network','Selected upstream cells'],
    ['descending','Descending cells','Motor readout populations']];
  for(const [key,label,sub] of stages) {
    const node=document.createElement('div');node.className='circuit-node';node.id='stage-'+key;
    node.innerHTML='<small></small><strong>—</strong><small class="stage-count"></small><div class="meter"><div></div></div>';
    node.firstChild.textContent=label+' / '+sub;$('circuitStages').append(node);
  }
  const channels=[['locomotion_drive','Locomotion'],['turn_drive','Turn · DN + network L/R'],['escape_drive','Acceleration'],['landing_drive','Landing']];
  for(const [key,label] of channels) {
    const node=document.createElement('div');node.className='motor-channel';node.id='motor-'+key;
    node.innerHTML='<span></span><b>—</b><div class="meter"><div></div></div>';node.firstChild.textContent=label;$('motorChannels').append(node);
  }
  function renderCircuit(state,meta) {
    if(!circuitGroups) {
      circuitGroups=Object.fromEntries(stages.map(([key])=>[key,[]]));
      meta.neurons.forEach((n,i)=>{
        const key=n.auditory_input?'auditory':n.input?'input':({ol_intrinsic:'optic',visual_projection:'projection',descending_neuron:'descending'})[n.superclass]||'central';
        circuitGroups[key].push(i);
      });
    }
    for(const [key] of stages) {
      const indices=circuitGroups[key], rates=state.neuron_hz||[];
      const mean=indices.reduce((sum,i)=>sum+(rates[i]||0),0)/Math.max(1,indices.length);
      const active=indices.filter(i=>rates[i]>0).length, node=$('stage-'+key);
      node.querySelector('strong').textContent=mean.toFixed(1)+' Hz';
      node.querySelector('.stage-count').textContent=active+' / '+indices.length+' cells active';
      node.querySelector('.meter div').style.width=clamp(mean/50)*100+'%';
    }
    for(const [key] of channels) {
      const value=state.motor?.[key]||0, node=$('motor-'+key);
      node.querySelector('b').textContent=value.toFixed(3);node.querySelector('.meter div').style.width=Math.abs(value)*100+'%';
    }
    $('circuitProof').textContent=state.status==='running' ? (state.recurrent_enabled?'REAL CONNECTIONS ON':'SYNAPSES DISCONNECTED')+' · '+(state.window_ms||0).toFixed(0)+' ms window' : 'Circuit stopped';
  }
  function renderSensors() {
    const live=telemetry?.status==='running' && performance.now()-receivedAt<1000;
    const samples=live?(telemetry?.limbs||[]):[];
    for(const button of $('probeCards').children) {
      const p=samples.find(p=>p.id===button.dataset.probe);
      button.classList.toggle('selected',button.dataset.probe===selectedProbe);
      button.querySelector('.sensor-swatch').style.background=p?.valid?'rgb('+p.rgb.map(v=>Math.round(255*v)).join(',')+')':'#263746';
      button.querySelector('small').textContent=p?.valid?'Y '+p.luminance.toFixed(2)+' · '+(p.object?.label||'image'):'No fresh sample';
    }
    const p=samples.find(p=>p.id===selectedProbe);
    $('sensorDetail').textContent=p?.valid ? selectedProbe.toUpperCase()+' / RGB '+p.rgb.map(v=>Math.round(255*v)).join(' ')+' / Y '+p.luminance.toFixed(3)+' / contrast '+p.contrast.toFixed(3)+' / '+(p.motion.valid?'speed '+p.motion.speed.toFixed(3)+' u/s · accel '+p.motion.acceleration.toFixed(3)+' u/s²':'motion initializing')+' / '+(p.object?p.object.label+' #'+p.object.id+' ('+Math.round(p.object.score*100)+'%)':p.semantic_valid?'no object overlap':'object inference unavailable')+' / frame '+p.frame_id+' · '+p.frame_age_ms.toFixed(0)+' ms' : selectedProbe.toUpperCase()+' / Waiting for a fresh image and endpoint sample';
    $('streamStatus').textContent=samples.filter(p=>p.valid).length+' / 8 PROBES · OSC '+(telemetry?.osc_target||'127.0.0.1:9000');
  }
  const scratch = document.createElement('canvas'); scratch.width = scratch.height = 128;
  const scratchContext = scratch.getContext('2d', {willReadFrequently: true});

  class Buzz {
    constructor() {this.ctx = null; this.enabled = false; this.volume = .3;}
    async enable() {
      if (!this.ctx) {
        const Audio = window.AudioContext || window.webkitAudioContext;
        this.ctx = new Audio(); const c = this.ctx;
        this.osc = c.createOscillator(); this.osc.type = 'sawtooth';
        this.filter = c.createBiquadFilter(); this.filter.type = 'lowpass'; this.filter.Q.value = .7;
        this.gain = c.createGain(); this.gain.gain.value = 0;
        this.pan = c.createStereoPanner();
        this.compressor = c.createDynamicsCompressor();
        this.compressor.threshold.value = -18; this.compressor.ratio.value = 8;
        this.osc.connect(this.filter).connect(this.gain).connect(this.pan).connect(this.compressor).connect(c.destination);
        this.flutter = c.createOscillator(); this.flutter.frequency.value = 8;
        this.flutterDepth = c.createGain(); this.flutterDepth.gain.value = 4;
        this.flutter.connect(this.flutterDepth).connect(this.osc.frequency);
        this.osc.start(); this.flutter.start();
      }
      await this.ctx.resume(); this.enabled = true;
    }
    mute() {this.enabled = false; if (this.ctx) this.gain.gain.setTargetAtTime(0,this.ctx.currentTime,.025);}
    update(fly, neural, connected) {
      if (!this.ctx) return;
      const t = this.ctx.currentTime;
      const audible = connected && this.enabled && !document.hidden && fly.mode !== 'walking';
      const level = audible ? .06 * this.volume * fly.gain * (.35 + .65 * neural.activity) : 0;
      this.gain.gain.setTargetAtTime(level,t,.035);
      this.osc.frequency.setTargetAtTime(Math.max(80,fly.wing_hz || 180),t,.04);
      this.filter.frequency.setTargetAtTime(700 + 3300 * neural.activity,t,.07);
      this.flutter.frequency.setTargetAtTime(5 + 14 * neural.activity,t,.1);
      this.pan.pan.setTargetAtTime(clamp(2*fly.x-1,-1,1),t,.04);
    }
  }
  const reactionControl=document.createElement('label');
  reactionControl.textContent='Reaction gain ';
  const reactionSlider=document.createElement('input');reactionSlider.type='range';
  reactionSlider.min='.5';reactionSlider.max='2.5';reactionSlider.step='.1';reactionSlider.value='1.4';
  reactionSlider.setAttribute('aria-label','Reaction gain');
  const reactionValue=document.createElement('span');reactionValue.textContent='1.4×';
  reactionSlider.oninput=()=>{reactionValue.textContent=(+reactionSlider.value).toFixed(1)+'×';};
  reactionControl.append(reactionSlider,reactionValue);$('toggleRecurrence').parentElement.append(reactionControl);
  const buzz = new Buzz();
  const hearing = new window.MCNSSourceAudio();
  async function control(body) {
    $('widgetError').textContent = '';
    try {
      const response = await fetch('/api/control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if (!response.ok) throw Error(await response.text());
      return await response.json();
    } catch (error) {$('widgetError').textContent = 'Control failed. Check the simulation status and camera access.'; return null;}
  }
  function sourceControls() {
    const busy=uploading||['running','starting','stopping'].includes(telemetry?.status);
    const source=$('widgetSource').value;
    $('startWidget').disabled=busy||(source==='video'&&!importedVideo);
    $('widgetSource').disabled=busy;
    $('cameraDevice').disabled=busy||source!=='camera';
    $('mirrorCamera').disabled=busy||source!=='camera';
    $('videoLoop').disabled=busy;
    $('videoFile').disabled=busy;
  }
  function videoLabel() {
    $('videoInfo').textContent=importedVideo ? importedVideo.name+' · '+importedVideo.width+'×'+importedVideo.height+
      (importedVideo.duration_s?' · '+importedVideo.duration_s.toFixed(1)+' s':'')+' · '+(importedVideo.audio_status||'ready') : 'Choose a local video · up to 1 GB · stays on this computer';
  }
  fetch('/api/video').then(r=>r.json()).then(data=>{importedVideo=data.video;if(importedVideo && telemetry?.status!=='running')$('widgetSource').value='video';videoLabel();sourceControls();}).catch(()=>{});
  $('widgetSource').onchange=sourceControls;
  $('videoFile').onchange=async event=>{
    const file=event.target.files[0];if(!file)return;
    if(file.size>1024**3){$('widgetError').textContent='Choose a video smaller than 1 GB.';event.target.value='';return;}
    uploading=true;sourceControls();$('widgetError').textContent='';$('videoInfo').textContent='Importing '+file.name+'…';
    try {
      const response=await fetch('/api/video?name='+encodeURIComponent(file.name),{
        method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
      if(!response.ok)throw Error('Video import failed. Stop the simulation and choose a supported video (e.g. MP4 / H.264).');
      const result=await response.json();importedVideo=result.video;$('widgetSource').value='video';
    } catch(error){$('widgetError').textContent=error.message;}
    finally{uploading=false;event.target.value='';videoLabel();sourceControls();}
  };
  $('startWidget').onclick = () => control({action:'start',source:$('widgetSource').value,
    device:+$('cameraDevice').value,mirror:$('mirrorCamera').checked,
    video_id:importedVideo?.id,video_loop:$('videoLoop').checked});
  $('stopWidget').onclick = () => {hearing.stop();buzz.mute(); $('audioToggle').textContent='Turn fly sound on'; control({action:'stop'});};
  $('audioToggle').onclick = async () => {
    if (buzz.enabled) {buzz.mute(); $('audioToggle').textContent='Turn fly sound on';}
    else try {await buzz.enable(); $('audioToggle').textContent='Turn fly sound off';}
    catch(error) {$('widgetError').textContent='The browser could not start audio. Click the sound button again.';}
  };
  $('widgetVolume').oninput = event => {buzz.volume = +event.target.value;};
  $('showPerches').onchange = event => {showPerches = event.target.checked;};
  $('toggleRecurrence').onclick = async () => {
    const result = await control({action:'recurrence',enabled:!recurrence});
    if (result) recurrence = result.enabled;
  };
  document.addEventListener('visibilitychange', () => {if(document.hidden) buzz.update({gain:0,x:.5},drive,false);});
  window.addEventListener('pagehide', () => buzz.mute());

  window.addEventListener('mcns-state', event => {
    const {state, meta} = event.detail;
    hearing.update(state, importedVideo);
    telemetry = state; receivedAt = performance.now();
    if (state.run_id && state.run_id !== runId) {
      $('widgetError').textContent='';
      runId = state.run_id; agent = state.embodied ? new EmbodiedAgent(42) : new FlyAgent(42); readout = new NeuralReadout(meta.neurons); anchors = []; trails.clear();
    }
    renderCircuit(state,meta);renderSensors();
    $('eyePanel').hidden = !state.embodied;
    if(state.embodied && state.status==='running'){
      $('eyeLeft').src='/api/eye-L.jpg?s='+state.sequence; $('eyeRight').src='/api/eye-R.jpg?s='+state.sequence;
      const m=state.motor;
      $('motorReadout').textContent=m ? 'LC4/LPLC2 left/right: '+m.rates.visual_L.toFixed(1)+' / '+m.rates.visual_R.toFixed(1)+' Hz · Escape DN left/right: '+m.rates.escape_L.toFixed(1)+' / '+m.rates.escape_R.toFixed(1)+' Hz · Motor response '+m.escape_drive.toFixed(2)+' · turn '+m.turn_drive.toFixed(2)+' (DN '+m.turn_dn.toFixed(3)+' + network '+m.turn_network.toFixed(3)+') · looming selectivity not yet validated' : 'Waiting for the DN measurement';
      $('sceneReadout').textContent=(state.scene?.objects||[]).map(o=>o.label+' #'+o.id).join(' · ')||'Waiting for an object / none detected';
    }
    if (state.neuron_hz && readout) drive = readout.update(state.neuron_hz);
    if (state.sequence >= 0 && state.status === 'running') scene.src = '/api/scene.jpg?s='+state.sequence;
    recurrence = state.recurrent_enabled !== false;
    $('toggleRecurrence').textContent = recurrence ? 'A/B: disconnect wiring' : 'A/B: reconnect wiring';
    $('couplingStatus').textContent = recurrence ? 'Real connections on' : 'Connections off · neural drive decays';
    if(state.status==='running') {
      $('widgetSource').value=state.source;
      if(state.camera_device!==undefined)$('cameraDevice').value=state.camera_device;
      if(state.source==='camera')$('mirrorCamera').checked=state.mirror!==false;
      if(state.source==='video')$('videoLoop').checked=state.video_loop!==false;
    }
    sourceControls();
    $('stopWidget').disabled = !['running','starting'].includes(state.status);
    $('neuralDrive').textContent = drive.hz.toFixed(2)+' Hz/neuron';
    $('neuralLeaders').textContent = drive.leaders.filter(p=>p.hz>0).map(p=>p.name+' '+p.hz.toFixed(1)+' Hz').join(' · ') || 'No activity outside the input';
    if (state.error) $('widgetError').textContent=state.error;
    if (meta.manifest?.anatomical_edges) $('circuitSize').textContent=meta.neurons.length.toLocaleString('en')+' cells · '+meta.manifest.anatomical_edges.toLocaleString('en')+' real connections';
  });

  scene.onload = () => {
    scene.hidden=false;
    if (performance.now()-lastAnalysis < 800) return;
    lastAnalysis=performance.now();
    scratchContext.drawImage(scene,0,0,128,128);
    const pixels=scratchContext.getImageData(0,0,128,128).data;
    const gray=new Uint8Array(128*128);
    for(let i=0;i<gray.length;i++)gray[i]=.299*pixels[4*i]+.587*pixels[4*i+1]+.114*pixels[4*i+2];
    anchors=imageAnchors(gray,128,128);
    const tr=telemetry && telemetry.tracking;
    if (tr && telemetry.tracking_age_ms<500) for(const key of ['Left','Right','face']) {
      const a=tr[key]; if(a && a[0])anchors.push({x:clamp(a[1]),y:clamp(a[2]),score:255,kind:'human'});
    }
  };

  function drawFly(fly, time, width, height, rect) {
    context.clearRect(0,0,width,height);
    if(showPerches && telemetry?.embodied){
      context.font='12px system-ui';
      for(const object of telemetry.scene?.objects||[]){
        const b=object.box;context.strokeStyle=object.label==='person'?'#efbd7d':'#9ce8bd';context.fillStyle=context.strokeStyle;
        context.strokeRect(rect.x+b[0]*rect.w,rect.y+b[1]*rect.h,(b[2]-b[0])*rect.w,(b[3]-b[1])*rect.h);
        context.fillText(object.label+' #'+object.id+' '+Math.round(object.score*100)+'%',rect.x+b[0]*rect.w,rect.y+b[1]*rect.h-5);
      }
      context.strokeStyle='#80c8ed';context.beginPath();context.moveTo(rect.x+fly.x*rect.w,rect.y+fly.y*rect.h);
      context.lineTo(rect.x+(fly.x+.12*Math.cos(fly.angle))*rect.w,rect.y+(fly.y+.12*Math.sin(fly.angle))*rect.h);context.stroke();
    }
    if(showPerches && !telemetry?.embodied) for(const point of anchors){
      context.strokeStyle=point.kind==='human'?'#efbd7d':'#9ce8bd';
      context.beginPath();context.arc(rect.x+point.x*rect.w,rect.y+point.y*rect.h,5,0,Math.PI*2);context.stroke();
    }
    if(fly.mode==='offline')return;
    const rig=crawlerRig(fly,rect.w/rect.h,+$('flySize').value);
    const xy=p=>[rect.x+p.x*rect.w,rect.y+p.y*rect.h];
    function path(points,stroke,width=1) {
      context.strokeStyle=stroke;context.lineWidth=width;context.beginPath();
      points.forEach((p,i)=>{const [x,y]=xy(p);i?context.lineTo(x,y):context.moveTo(x,y);});context.stroke();
    }
    const samples=new Map((telemetry?.limbs||[]).map(p=>[p.id,p]));
    for(const limb of rig.limbs) {
      const left=limb.id.includes('-L'),color=left?'#58f1e7':'#f26acb';
      const tip=limb.points[limb.points.length-1],sample=samples.get(limb.id);
      const colorPixel=sample?.valid?'rgb('+sample.rgb.map(v=>Math.round(v*255)).join(',')+')':color;
      const trail=trails.get(limb.id)||[];trail.push(tip);if(trail.length>24)trail.shift();trails.set(limb.id,trail);
      context.globalAlpha=.17;path(trail,color,1);context.globalAlpha=1;
      path(limb.points,'#02060be6',3.8);path(limb.points,color,limb.id===selectedProbe?1.7:1);
      for(let i=1;i<limb.points.length;i++) {
        const [x,y]=xy(limb.points[i]);context.fillStyle=i===limb.points.length-1?colorPixel:color;
        context.beginPath();context.arc(x,y,i===limb.points.length-1?3.1:1.8,0,Math.PI*2);context.fill();
        if(i===limb.points.length-1){context.strokeStyle=color;context.lineWidth=.7;context.beginPath();context.arc(x,y,5.2,0,Math.PI*2);context.stroke();}
      }
      if(limb.id===selectedProbe) {
        const [x,y]=xy(tip),label=sample?.object?sample.object.label+' #'+sample.object.id:'PIXEL / '+limb.id.toUpperCase();
        context.font='10px ui-monospace,monospace';const width=context.measureText(label).width+14;
        const lx=clamp(x+24,8,Math.max(8,rect.x+rect.w-width-8)),ly=clamp(y-32,16,rect.y+rect.h-40);
        context.strokeStyle=color;context.lineWidth=.7;context.beginPath();context.moveTo(x,y);context.lineTo(lx,ly+8);context.stroke();
        context.fillStyle='#071019e8';context.fillRect(lx,ly-3,width,21);context.strokeRect(lx,ly-3,width,21);
        context.fillStyle=color;context.fillText(label,lx+7,ly+11);
      }
    }
    for(const wing of rig.wings){context.globalAlpha=fly.mode==='walking'?.2:.55;path([...wing,wing[0]],'#85b6de',.8);}context.globalAlpha=1;
    const body=rig.body;context.fillStyle='#0c1829dc';context.beginPath();body.forEach((p,i)=>{const [x,y]=xy(p);i?context.lineTo(x,y):context.moveTo(x,y);});context.fill();path(body,'#b7cad8',1);
    path([body[1],body[5],body[2],body[4],body[1]],'#507582',.6);
    const [hx,hy]=xy(rig.head),[tx,ty]=xy(rig.thorax);
    context.fillStyle='#74efcb';context.beginPath();context.arc(tx,ty,2+fly.activity*3,0,Math.PI*2);context.fill();
    context.strokeStyle='#e6edf2';context.lineWidth=1;context.beginPath();context.arc(hx,hy,4,0,Math.PI*2);context.stroke();
  }
  function animate(now) {
    const dt=Math.min(.05,(now-lastTime)/1000);lastTime=now;
    const connected=telemetry && telemetry.status==='running' && now-receivedAt<1000 && !document.hidden;
    const fly=telemetry?.embodied ? agent.update(dt,drive,telemetry.motor,telemetry.scene,connected,+reactionSlider.value) : agent.update(dt,drive,telemetry && telemetry.behavior,anchors,connected);
    const box=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
    if(canvas.width!==Math.round(box.width*ratio)||canvas.height!==Math.round(box.height*ratio)){
      canvas.width=Math.round(box.width*ratio);canvas.height=Math.round(box.height*ratio);
    }
    context.setTransform(ratio,0,0,ratio,0,0);
    const naturalRatio=(scene.naturalWidth||4)/(scene.naturalHeight||3);
    const w=Math.min(box.width,box.height*naturalRatio),h=w/naturalRatio;
    drawFly(fly,now/1000,box.width,box.height,{x:(box.width-w)/2,y:(box.height-h)/2,w,h});
    if(!connected)trails.clear();
    buzz.update(fly,drive,connected);
    const labels={flying:'Flying',walking:'Walking',escaping:telemetry?.embodied?'DN response · acceleration':'Escaping',hidden:'Hidden',offline:'Stopped'};
    $('flyMode').textContent=telemetry?.embodied && fly.mode==='flying' && fly.burst>.2 ? 'Neural burst · dart' : labels[fly.mode];
    $('flightReadout').textContent=fly.speed.toFixed(2)+' u/s · reaction '+(fly.urgency||0).toFixed(2)+' · burst '+(fly.burst||0).toFixed(2);
    if(connected && now-lastPost>=50 && !sending){
      lastPost=now;sending=true;
      fetch('/api/widget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fly,run_id:runId,sample_time:(performance.timeOrigin+now)/1000,probes:crawlerRig(fly,naturalRatio,+$('flySize').value).probes})})
        .catch(()=>{}).finally(()=>{sending=false;});
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
