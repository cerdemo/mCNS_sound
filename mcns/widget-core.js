/* Pure, seeded locomotion and connectome readout. Also executable in Node tests. */
(function (root) {
  'use strict';
  const clamp = (v, lo = 0, hi = 1) => Math.max(lo, Math.min(hi, v));
  function randomSeed(seed) {
    return () => {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }

  class NeuralReadout {
    constructor(neurons) {
      this.cells = neurons.map((n, i) => ({...n, i})).filter(n => !n.input && !n.auditory_input && n.hex);
      const xs = this.cells.map(n => n.hex[0] - .5 * n.hex[1]);
      const ys = this.cells.map(n => Math.sqrt(3) / 2 * n.hex[1]);
      const minX = Math.min(...xs), maxX = Math.max(...xs);
      const minY = Math.min(...ys), maxY = Math.max(...ys);
      this.cells.forEach((n, i) => {
        n.x = (xs[i] - minX) / Math.max(1, maxX - minX);
        n.y = (ys[i] - minY) / Math.max(1, maxY - minY);
      });
    }
    update(rates) {
      let total = 0, x = 0, y = 0;
      const populations = {};
      for (const n of this.cells) {
        const r = Math.max(0, rates[n.i] || 0);
        total += r; x += n.x * r; y += n.y * r;
        const p = populations[n.population] || (populations[n.population] = {sum: 0, count: 0});
        p.sum += r; p.count++;
      }
      const leaders = Object.entries(populations).map(([name, p]) => ({name, hz: p.sum / p.count}))
        .sort((a, b) => b.hz - a.hz).slice(0, 3);
      const mean = total / Math.max(1, this.cells.length);
      return {x: total ? x / total : .5, y: total ? y / total : .5,
        activity: clamp(mean / 18), hz: mean, leaders, hasSignal: total > 0};
    }
  }

  class FlyAgent {
    constructor(seed = 42) {
      this.random = randomSeed(seed);
      this.x = .5; this.y = .4; this.vx = 0; this.vy = 0;
      this.mode = 'flying'; this.time = 0; this.sinceMode = 0;
      this.target = {x: .7, y: .3}; this.nextTarget = 0;
      this.walkUntil = 0; this.surface = null; this.angle = 0;
      this.previousFear = 'flying';
    }
    chooseTarget(anchors, drive) {
      if (anchors.length && this.random() < .8) {
        // Neural activity changes which visible feature the insect explores.
        const scored = anchors.map(a => ({a, score: Math.hypot(a.x - drive.x, a.y - drive.y)
          + .2 * this.random()})).sort((a, b) => a.score - b.score);
        this.target = {...scored[0].a};
      } else this.target = {x: .08 + .84 * this.random(), y: .1 + .75 * this.random(), kind: 'air'};
      this.nextTarget = this.time + 2 + 3 * this.random();
    }
    update(dt, drive, fear, anchors = [], connected = true) {
      if (!connected) return {...this.output(drive, 0), mode: 'offline'};
      dt = Math.max(0, Math.min(.05, dt)); this.time += dt; this.sinceMode += dt;
      const state = fear && fear.tracking_valid ? fear.state : 'flying';
      let gain = fear ? fear.gain : 1;
      if (!connected) gain = 0;
      if (state === 'hidden') {
        this.mode = 'hidden'; this.vx = this.vy = 0;
        if (fear) {this.x = fear.x; this.y = fear.y;}
        this.previousFear = state;
        return this.output(drive, 0);
      }
      if (state === 'escaping') {
        this.mode = 'escaping'; this.surface = null;
        const oldX = this.x, oldY = this.y;
        const x = fear.x, y = fear.y;
        this.x += (x - this.x) * Math.min(1, dt * 12);
        this.y += (y - this.y) * Math.min(1, dt * 12);
        this.vx = (this.x - oldX) / Math.max(dt, .001);
        this.vy = (this.y - oldY) / Math.max(dt, .001);
      } else {
        if (['hidden', 'escaping'].includes(this.mode)) {
          this.mode = 'flying'; this.sinceMode = 0; this.nextTarget = 0;
        }
        if (this.time >= this.nextTarget && this.mode !== 'walking') this.chooseTarget(anchors, drive);
        if (this.mode === 'walking') {
          this.vx = (this.surface.direction || 1) * (.018 + .04 * drive.activity);
          this.vy = 0;
          this.x += this.vx * dt;
          this.y = this.surface.y;
          if (this.x < this.surface.left || this.x > this.surface.right) this.surface.direction *= -1;
          this.x = clamp(this.x, this.surface.left, this.surface.right);
          if (this.time > this.walkUntil || drive.activity > .8) {
            this.mode = 'flying'; this.sinceMode = 0; this.y -= .025; this.nextTarget = 0;
          }
        } else {
          this.mode = 'flying';
          const tx = .65 * this.target.x + .35 * drive.x;
          const ty = .65 * this.target.y + .35 * drive.y;
          const dx = tx - this.x, dy = ty - this.y, distance = Math.hypot(dx, dy);
          const speed = .08 + .19 * drive.activity;
          const turn = 1 - Math.exp(-dt * 4);
          this.vx += turn * (dx / Math.max(distance, .01) * speed - this.vx);
          this.vy += turn * (dy / Math.max(distance, .01) * speed - this.vy);
          this.vx += (this.random() - .5) * dt * .08;
          this.vy += (this.random() - .5) * dt * .08;
          this.x += this.vx * dt; this.y += this.vy * dt;
          if (this.sinceMode > 4 && drive.activity < .8) {
            const nearby = anchors.filter(a => a.kind !== 'air'
              && Math.hypot(a.x - this.x, a.y - this.y) < .065);
            if (nearby.length) {
              this.surface = {...nearby[0], left: clamp(nearby[0].x - .055, .03, .9),
                right: clamp(nearby[0].x + .055, .1, .97), direction: this.random() < .5 ? -1 : 1};
              this.mode = 'walking'; this.sinceMode = 0;
              this.walkUntil = this.time + 2 + 4 * this.random();
            }
          }
        }
      }
      this.x = clamp(this.x, .025, .975); this.y = clamp(this.y, .03, .96);
      if (Math.hypot(this.vx, this.vy) > .002) this.angle = Math.atan2(this.vy, this.vx);
      this.previousFear = state;
      return this.output(drive, this.mode === 'walking' ? 0 : gain);
    }
    output(drive, gain) {
      const speed = Math.hypot(this.vx, this.vy);
      return {mode: this.mode, x: this.x, y: this.y, vx: this.vx, vy: this.vy,
        angle: this.angle, speed, gain: clamp(gain), activity: drive.activity,
        wing_hz: gain > 0 ? 165 + 80 * drive.activity + 50 * clamp(speed / .3) : 0,
        neural_x: drive.x, neural_y: drive.y};
    }
  }

  // Expressive motor layer: amplify measured neural output, never infer danger
  // from labels or object velocity. Brief impulses are not extra sensory evidence.
  class NeuralMotion {
    constructor() { this.reset(); }
    reset() {
      this.baseline=null;this.burst=0;this.saccade=0;this.cooldown=0;this.armed=true;
    }
    update(dt,motor={},reaction=1.4) {
      reaction=clamp(reaction,.5,2.5);
      const raw=clamp(motor.locomotion_drive||0), escape=clamp(motor.escape_drive||0);
      const turn=clamp(motor.turn_drive||0,-1,1);
      const boost=v=>v>1e-6 ? 1-Math.exp(-3*reaction*Math.pow(clamp(v),.55)) : 0;
      const urgency=escape>1e-6 ? 1-Math.exp(-8*reaction*escape) : 0;
      if(this.baseline===null)this.baseline={raw,escape};
      const onset=Math.max(0,raw-this.baseline.raw,2*(escape-this.baseline.escape));
      const adapt=1-Math.exp(-dt/.45);
      this.baseline.raw+=adapt*(raw-this.baseline.raw);
      this.baseline.escape+=adapt*(escape-this.baseline.escape);
      this.burst*=Math.exp(-dt/.14);this.saccade*=Math.exp(-dt/.065);
      this.cooldown=Math.max(0,this.cooldown-dt);
      if(onset<.015)this.armed=true;
      if(onset>.045 && this.armed && this.cooldown===0) {
        this.burst=1-Math.exp(-7*reaction*onset);this.armed=false;this.cooldown=.3;
        // An asymmetric neural signal supplies direction; no coin-flip saccades.
        const side=Math.sign(turn || ((motor.probe_right||0)-(motor.probe_left||0)));
        this.saccade=side*Math.min(18,(5+12*this.burst)*reaction);
      }
      const locomotion=boost(raw);
      const alive=Math.max(raw,escape,Math.abs(turn),motor.probe_left||0,motor.probe_right||0)>1e-6;
      if(!alive){this.burst=0;this.saccade=0;}
      const turnRate=clamp(7*Math.tanh(3*reaction*turn)+this.saccade,-22,22);
      return {locomotion,urgency,burst:this.burst,turnRate,
        speed:Math.min(1.8,.34*locomotion+.8*urgency+.95*this.burst),
        phaseRate:34*locomotion+52*urgency+45*this.burst,
        probe_left:clamp(boost(motor.probe_left||0)+.65*urgency+.6*this.burst),
        probe_right:clamp(boost(motor.probe_right||0)+.65*urgency+.6*this.burst)};
    }
  }

  class EmbodiedAgent extends FlyAgent {
    constructor(seed=42) {
      super(seed);this.contact=null;this.lastBox=null;this.phase=0;this.antennaPhase=0;
      this.motion=new NeuralMotion();this.flightSpeed=0;
    }
    update(dt,drive,motor,scene,connected=true,reaction=1.4) {
      if(!connected) {
        this.vx=this.vy=this.flightSpeed=0;this.motion.reset();
        return {...this.output(drive,0),mode:'offline',phase:this.phase,antenna_phase:this.antennaPhase};
      }
      dt=clamp(dt,0,.05);this.time+=dt;
      const objects=scene?.objects||[],landing=clamp(motor?.landing_drive||0);
      const movement=this.motion.update(dt,motor||{},reaction);
      const {locomotion,urgency,burst,turnRate}=movement;
      const energy=Math.max(locomotion,urgency,burst);
      const oldX=this.x,oldY=this.y;
      this.angle+=dt*turnRate;
      this.phase+=dt*movement.phaseRate;
      this.antennaPhase+=dt*(18*Math.max(movement.probe_left,movement.probe_right)+65*urgency+40*burst);
      const takeoff=urgency>.18;
      if(this.contact!==null) {
        const surface=objects.find(o=>o.id===this.contact);
        if(!surface||takeoff){this.contact=null;this.lastBox=null;this.sinceMode=0;}
        else {
          const b=surface.box;
          if(this.lastBox){this.x+=b[0]-this.lastBox[0];this.y+=b[1]-this.lastBox[1];}
          this.x+=Math.cos(this.angle)*(.16*locomotion+.18*burst)*dt;
          this.x=clamp(this.x,b[0]+.01,Math.max(b[0]+.01,b[2]-.01));
          this.y=b[1]+.012;this.lastBox=[...b];this.mode='walking';this.flightSpeed=0;
          if(locomotion>0 && (this.x<=b[0]+.011||this.x>=b[2]-.011))this.angle=Math.PI-this.angle;
        }
      }
      if(this.contact===null) {
        this.sinceMode+=dt;
        const target=movement.speed*(1-.6*landing*(1-urgency));
        // Fast attack, short braking: an impulse has acceleration, not a position jump.
        const tau=target>this.flightSpeed ? .035 : .075;
        this.flightSpeed+=(target-this.flightSpeed)*(1-Math.exp(-dt/tau));
        if(this.flightSpeed<1e-6)this.flightSpeed=0;
        this.x+=Math.cos(this.angle)*this.flightSpeed*dt;this.y+=Math.sin(this.angle)*this.flightSpeed*dt;
        this.mode=takeoff?'escaping':'flying';
        if(this.flightSpeed>0 && ((this.x<.03 && Math.cos(this.angle)<0)||(this.x>.97 && Math.cos(this.angle)>0)))this.angle=Math.PI-this.angle;
        if(this.flightSpeed>0 && ((this.y<.03 && Math.sin(this.angle)<0)||(this.y>.96 && Math.sin(this.angle)>0)))this.angle=-this.angle;
        // Strong neural reactions override landing; detections supply geometry only.
        if(landing>.05 && urgency<.1 && burst<.15)for(const object of objects){
          const b=object.box;
          if(this.x>b[0]+.01&&this.x<b[2]-.01&&Math.abs(this.y-b[1])<.025){
            this.contact=object.id;this.lastBox=[...b];this.mode='walking';this.y=b[1]+.012;
            this.flightSpeed=0;break;
          }
        }
      }
      this.x=clamp(this.x,.03,.97);this.y=clamp(this.y,.03,.96);
      this.vx=dt?(this.x-oldX)/dt:0;this.vy=dt?(this.y-oldY)/dt:0;
      return {...this.output(drive,this.mode==='walking'?0:energy),phase:this.phase,
        antenna_phase:this.antennaPhase,burst,urgency,turn_rate:turnRate,
        contact_id:this.contact,locomotion,probe_left:movement.probe_left,probe_right:movement.probe_right};
    }
  }

  // Shared rendering/measurement geometry. All points are in normalized image space.
  // Aspect correction keeps lengths stable across portrait/landscape previews and resizing.
  function crawlerRig(fly, aspect=4/3, size=1.4) {
    const scale=.0018*size, phase=fly.phase||0;
    const heading=Math.atan2(Math.sin(fly.angle),aspect*Math.cos(fly.angle));
    const transform=([x,y])=>({x:fly.x+scale*(x*Math.cos(heading)-y*Math.sin(heading))/aspect,
      y:fly.y+scale*(x*Math.sin(heading)+y*Math.cos(heading))});
    const limbs=[];
    for(const side of [-1,1])for(let i=0;i<3;i++) {
      const activity=side<0?(fly.probe_left||0):(fly.probe_right||0);
      // Alternating tripods, quick swing and slower stance; gain comes from the circuit.
      const cycle=phase+i*Math.PI+(side>0?Math.PI:0);
      const stride=Math.tanh(1.6*Math.sin(cycle))*13*activity;
      const forward=[26,0,-27][i];
      const points=[[7-i*7,side*5],[forward*.6+stride,side*(19+4*activity)],
        [forward+stride,side*(32+5*activity)],[forward+stride-8,side*(43+4*activity)]];
      limbs.push({id:'leg-'+(side<0?'L':'R')+(i+1),points:points.map(transform)});
    }
    for(const side of [-1,1]) {
      const activity=side<0?(fly.probe_left||0):(fly.probe_right||0);
      const sweep=Math.sin((fly.antenna_phase??phase*.63)+side)*17*activity;
      limbs.push({id:'antenna-'+(side<0?'L':'R'),points:[[17,side*4],[31,side*(14+sweep*.25)],
        [52+sweep,side*(26+sweep)]].map(transform)});
    }
    return {limbs,probes:limbs.map(l=>({id:l.id,...l.points[l.points.length-1]})),
      body:[[-24,0],[-11,-8],[5,-7],[18,0],[5,7],[-11,8],[-24,0]].map(transform),
      head:transform([14,0]),thorax:transform([0,0]),
      wings:[-1,1].map(side=>[[0,side*5],[-22,side*(18+Math.sin(phase*4)*4)],[-29,side*9],[-8,side*3]].map(transform))};
  }

  // Strong image edges are candidate 2D perches, not semantic object detections.
  function imageAnchors(gray, width, height) {
    const candidates = [];
    for (let y = 6; y < height - 6; y += 6) for (let x = 6; x < width - 6; x += 6) {
      const above = gray[(y - 3) * width + x], below = gray[(y + 3) * width + x];
      const score = Math.abs(below - above);
      if (score > 28) candidates.push({x: x / width, y: y / height, score, kind: 'edge'});
    }
    candidates.sort((a, b) => b.score - a.score);
    const chosen = [];
    for (const a of candidates) {
      if (chosen.every(b => Math.hypot(a.x - b.x, a.y - b.y) > .09)) chosen.push(a);
      if (chosen.length >= 18) break;
    }
    return chosen;
  }
  const api = {NeuralReadout, FlyAgent, EmbodiedAgent, NeuralMotion, crawlerRig, imageAnchors, clamp};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.MCNSWidget = api;
})(typeof window === 'undefined' ? globalThis : window);
