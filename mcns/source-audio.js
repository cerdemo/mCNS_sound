/* Imported soundtrack playback is independent from auditory neural input and buzz. */
(function () {
  'use strict';
  class SourceAudio {
    constructor() {
      this.player = new Audio(); this.player.preload = 'metadata';
      this.enabled = false; this.state = null; this.video = null;
      this.stream = null; this.context = null; this.pending = false; this.generation = 0;
      this.videoButton = document.getElementById('videoAudioToggle');
      this.micButton = document.getElementById('microphoneToggle');
      this.status = document.getElementById('hearingStatus');
      this.videoButton.onclick = () => this.toggleVideo();
      this.micButton.onclick = () => this.toggleMicrophone();
      this.player.onerror = () => {this.enabled=false;this.labels();this.message('Video audio could not play.');};
      document.addEventListener('visibilitychange', () => {
        if(document.hidden) {this.player.pause();this.stopMicrophone();}
      });
      window.addEventListener('pagehide', () => this.stop());
      this.timer = setInterval(() => this.sample(), 50);
    }
    message(text) {document.getElementById('widgetError').textContent=text;}
    labels() {
      this.videoButton.textContent = this.enabled ? 'Mute video audio' : 'Unmute video audio';
      this.micButton.textContent = this.stream ? 'Stop microphone' : 'Listen to microphone';
      this.micButton.disabled = this.pending || this.state?.status!=='running' || this.state?.source!=='camera';
      this.videoButton.disabled = !this.video?.has_audio || this.state?.source!=='video' || this.state?.status!=='running';
    }
    async toggleVideo() {
      if(this.enabled) {this.enabled=false;this.player.pause();}
      else {
        try {
          this.player.currentTime = this.state?.video_position_s || 0;
          await this.player.play();this.enabled=true;
        } catch(error) {this.message('Click Unmute video audio again to allow playback.');}
      }
      this.labels();
    }
    stopMicrophone() {
      this.generation++;
      if(this.stream)this.stream.getTracks().forEach(track=>track.stop());
      this.stream=null;
      if(this.context)this.context.close().catch(()=>{});
      this.context=null;this.analyser=null;this.pending=false;this.labels();
    }
    async toggleMicrophone() {
      if(this.stream){this.stopMicrophone();return;}
      const generation=++this.generation;
      this.pending=true;this.labels();
      try {
        const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:false,autoGainControl:false}});
        if(generation!==this.generation || this.state?.status!=='running' || this.state?.source!=='camera') {
          stream.getTracks().forEach(track=>track.stop());return;
        }
        this.stream=stream;
        this.context=new (window.AudioContext||window.webkitAudioContext)();
        const input=this.context.createMediaStreamSource(stream);
        const high=this.context.createBiquadFilter();high.type='highpass';high.frequency.value=80;high.Q.value=Math.SQRT1_2;
        const low=this.context.createBiquadFilter();low.type='lowpass';low.frequency.value=1000;low.Q.value=Math.SQRT1_2;
        this.analyser=this.context.createAnalyser();this.analyser.fftSize=2048;
        this.samples=new Float32Array(this.analyser.fftSize);
        const silent=this.context.createGain();silent.gain.value=0;
        input.connect(high).connect(low).connect(this.analyser).connect(silent).connect(this.context.destination);
        await this.context.resume();
      } catch(error) {this.stopMicrophone();this.message('Microphone could not start. Allow microphone access, then click Listen to microphone.');}
      finally {this.pending=false;this.labels();}
    }
    sample() {
      if(this.stream && performance.now()-this.updatedAt>1500){this.stopMicrophone();return;}
      if(!this.analyser || this.sending || document.hidden || this.state?.status!=='running' || this.state?.source!=='camera')return;
      this.analyser.getFloatTimeDomainData(this.samples);
      let sum=0;for(const value of this.samples)sum+=value*value;
      const rms=Math.min(1,Math.sqrt(sum/this.samples.length));
      this.sending=true;
      fetch('/api/audio',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({run_id:this.state.run_id,rms})})
        .catch(()=>{}).finally(()=>{this.sending=false;});
    }
    stop() {this.enabled=false;this.player.pause();this.stopMicrophone();this.labels();}
    update(state, video) {
      const changed=this.state?.run_id!==state.run_id;
      this.state=state;this.updatedAt=performance.now();
      if(this.video?.id!==video?.id) {
        this.player.pause();this.enabled=false;
        if(video?.has_audio)this.player.src='/api/video-audio/'+video.id+'.wav';
        else this.player.removeAttribute('src');
      }
      this.video=video;
      if(state.status!=='running' || state.source!=='camera') {
        if(this.stream || this.pending)this.stopMicrophone();
      }
      if(state.status!=='running' || state.source!=='video') {this.enabled=false;this.player.pause();}
      else if(this.enabled && !document.hidden) {
        const target=state.video_position_s||0;
        // Backend frame presentation is the clock, including loop boundaries.
        if(Number.isFinite(this.player.duration) && target>=this.player.duration) {
          this.player.pause();
        } else {
        if(changed || Math.abs(this.player.currentTime-target)>.18)this.player.currentTime=target;
        if(this.player.paused)this.player.play().catch(()=>{this.enabled=false;this.labels();});
        }
      }
      const a=state.auditory;
      this.status.textContent = !a?.available ? 'Hearing: auditory circuit not loaded' :
        a.valid ? 'Hearing '+a.source+' · '+a.neurons+' JO cells · '+(20*Math.log10(Math.max(a.rms,1e-9))).toFixed(0)+' dBFS' :
        state.source==='video' ? 'Hearing: '+(video?.audio_status||'no audio signal') : 'Hearing ready · enable microphone';
      if(state.status!=='running')this.status.textContent='Hearing paused';
      this.labels();
    }
  }
  window.MCNSSourceAudio=SourceAudio;
})();
