(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const {NeuralReadout, FlyAgent, EmbodiedAgent, imageAnchors, clamp} = window.MCNSWidget;
  const scene = $('flyScene'), canvas = $('flyCanvas'), context = canvas.getContext('2d');
  let agent = new FlyAgent(), readout, drive = {x:.5,y:.5,activity:0,hz:0,leaders:[]};
  let telemetry = null, receivedAt = 0, lastTime = performance.now(), lastPost = 0;
  let runId = null, anchors = [], lastAnalysis = 0, sending = false;
  let showPerches = false, recurrence = true;
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
  const buzz = new Buzz();
  async function control(body) {
    $('widgetError').textContent = '';
    try {
      const response = await fetch('/api/control', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
      if (!response.ok) throw Error(await response.text());
      return await response.json();
    } catch (error) {$('widgetError').textContent = 'Kontrol başarısız. Simülasyon durumunu ve kamera erişimini kontrol edin.'; return null;}
  }
  $('startWidget').onclick = () => control({action:'start',source:$('widgetSource').value,device:+$('cameraDevice').value});
  $('stopWidget').onclick = () => {buzz.mute(); $('audioToggle').textContent='Sesi aç'; control({action:'stop'});};
  $('audioToggle').onclick = async () => {
    if (buzz.enabled) {buzz.mute(); $('audioToggle').textContent='Sesi aç';}
    else try {await buzz.enable(); $('audioToggle').textContent='Sesi kapat';}
    catch(error) {$('widgetError').textContent='Tarayıcı sesi başlatamadı. Ses düğmesine tekrar tıklayın.';}
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
    telemetry = state; receivedAt = performance.now();
    if (state.run_id && state.run_id !== runId) {
      runId = state.run_id; agent = state.embodied ? new EmbodiedAgent(42) : new FlyAgent(42); readout = new NeuralReadout(meta.neurons); anchors = [];
    }
    $('eyePanel').hidden = !state.embodied;
    if(state.embodied && state.status==='running'){
      $('eyeLeft').src='/api/eye-L.jpg?s='+state.sequence; $('eyeRight').src='/api/eye-R.jpg?s='+state.sequence;
      const m=state.motor;
      $('motorReadout').textContent=m ? 'LC4/LPLC2 sol/sağ: '+m.rates.visual_L.toFixed(1)+' / '+m.rates.visual_R.toFixed(1)+' Hz · Kaçış DN sol/sağ: '+m.rates.escape_L.toFixed(1)+' / '+m.rates.escape_R.toFixed(1)+' Hz · Motor yanıtı '+m.escape_drive.toFixed(2)+' · dönüş '+m.turn_drive.toFixed(2)+' · yaklaşma seçiciliği henüz doğrulanmadı' : 'DN ölçümü bekleniyor';
      $('sceneReadout').textContent=(state.scene?.objects||[]).map(o=>o.label+' #'+o.id).join(' · ')||'Nesne bekleniyor / algılanmadı';
    }
    if (state.neuron_hz && readout) drive = readout.update(state.neuron_hz);
    if (state.sequence >= 0 && state.status === 'running') scene.src = '/api/scene.jpg?s='+state.sequence;
    recurrence = state.recurrent_enabled !== false;
    $('toggleRecurrence').textContent = recurrence ? 'A/B: bağlantıları kapat' : 'A/B: bağlantıları aç';
    $('couplingStatus').textContent = recurrence ? 'Gerçek bağlantılar açık' : 'Bağlantılar kapalı · yalnızca giriş ve keşif';
    $('startWidget').disabled = ['running','starting','stopping'].includes(state.status);
    $('stopWidget').disabled = !['running','starting'].includes(state.status);
    $('neuralDrive').textContent = drive.hz.toFixed(2)+' Hz/nöron';
    $('neuralLeaders').textContent = drive.leaders.filter(p=>p.hz>0).map(p=>p.name+' '+p.hz.toFixed(1)+' Hz').join(' · ') || 'Giriş dışı aktivite yok';
    if (state.error) $('widgetError').textContent=state.error;
    if (meta.manifest?.anatomical_edges) $('circuitSize').textContent=meta.neurons.length.toLocaleString('tr')+' hücre · '+meta.manifest.anatomical_edges.toLocaleString('tr')+' gerçek bağlantı';
  });

  scene.onload = () => {
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
    const x=rect.x+fly.x*rect.w,y=rect.y+fly.y*rect.h;
    context.save();context.translate(x,y);context.rotate(fly.angle);
    const scale=+$('flySize').value;context.scale(scale,scale);
    context.globalAlpha=fly.mode==='hidden'?.15:1;
    const walking=fly.mode==='walking';
    context.strokeStyle='#0b100e';context.lineWidth=1.2;
    for(let side of [-1,1])for(let i=0;i<3;i++){
      const stride=walking?Math.sin(time*23+i*2+side)*2:0;
      context.beginPath();context.moveTo(-3+i*3,side*2);
      context.lineTo(-6+i*4+stride,side*7);context.lineTo(-8+i*5+stride,side*10);context.stroke();
    }
    const flutter=walking?0:Math.sin(time*95)*.5;
    context.fillStyle='rgba(221,239,225,.65)';context.strokeStyle='rgba(50,75,62,.8)';context.lineWidth=.5;
    for(let side of [-1,1]){
      context.save();context.rotate(side*(walking?.3:1.0+flutter));
      context.beginPath();context.ellipse(-4,side*3,10,3.4,0,0,Math.PI*2);context.fill();context.stroke();context.restore();
    }
    context.fillStyle='#59402a';context.strokeStyle='#eddec1';context.lineWidth=.7;
    context.beginPath();context.ellipse(-5,0,6,3.3,0,0,Math.PI*2);context.fill();context.stroke();
    context.fillStyle='#292c25';context.beginPath();context.ellipse(1,0,4,3.6,0,0,Math.PI*2);context.fill();context.stroke();
    context.fillStyle='#241e18';context.beginPath();context.arc(6,0,2.6,0,Math.PI*2);context.fill();
    context.fillStyle='#a95131';context.beginPath();context.arc(6,-1.9,1.4,0,Math.PI*2);context.arc(6,1.9,1.4,0,Math.PI*2);context.fill();
    context.restore();
  }
  function animate(now) {
    const dt=Math.min(.05,(now-lastTime)/1000);lastTime=now;
    const connected=telemetry && telemetry.status==='running' && now-receivedAt<1000;
    const fly=telemetry?.embodied ? agent.update(dt,drive,telemetry.motor,telemetry.scene,connected) : agent.update(dt,drive,telemetry && telemetry.behavior,anchors,connected);
    const box=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1;
    if(canvas.width!==Math.round(box.width*ratio)||canvas.height!==Math.round(box.height*ratio)){
      canvas.width=Math.round(box.width*ratio);canvas.height=Math.round(box.height*ratio);
    }
    context.setTransform(ratio,0,0,ratio,0,0);
    const naturalRatio=(scene.naturalWidth||4)/(scene.naturalHeight||3);
    const w=Math.min(box.width,box.height*naturalRatio),h=w/naturalRatio;
    drawFly(fly,now/1000,box.width,box.height,{x:(box.width-w)/2,y:(box.height-h)/2,w,h});
    buzz.update(fly,drive,connected);
    const labels={flying:'Uçuyor',walking:'Yürüyor',escaping:telemetry?.embodied?'DN yanıtı · hızlanma':'Kaçıyor',hidden:'Saklanıyor',offline:'Durduruldu'};
    $('flyMode').textContent=labels[fly.mode];
    $('flightReadout').textContent=fly.wing_hz.toFixed(0)+' Hz · ses kapısı '+fly.gain.toFixed(2);
    if(connected && now-lastPost>=50 && !sending){
      lastPost=now;sending=true;
      fetch('/api/widget',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...fly,run_id:runId})})
        .catch(()=>{}).finally(()=>{sending=false;});
    }
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
})();
