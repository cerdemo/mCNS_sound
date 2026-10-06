"""Explicit artistic decoder of real descending and downstream rates; no fear rule.

Uniform LIF physiology is not validated as a looming detector. Keep rates and
baseline-relative response visible rather than labelling every spike as fear.
"""
import numpy as np


class DescendingReadout:
    def __init__(self,neurons,options=None):
        self.options = {'network_scale_hz': 2., 'bilateral_turn_scale_hz': 6., **(options or {})}
        if any(not np.isfinite(v) or v <= 0 for v in self.options.values()):
            raise ValueError('Motor decoder scales must be finite and positive')
        self.groups={}
        for side in ('L','R'):
            for name,types in [('escape',['DNp01','DNp02','DNp04','DNp11']),
                               ('landing',['DNp07','DNp10']),('turn',['DNa02']),
                               ('visual',['LC4','LPLC2'])]:
                self.groups[name+'_'+side]=np.flatnonzero((neurons.somaSide==side)&neurons.type.isin(types))
            self.groups['network_'+side] = np.flatnonzero((neurons.somaSide == side) & ~neurons.is_input & (neurons.get("is_auditory_input", False) == False))
        self.smooth={key:0. for key in self.groups};self.baseline=self.smooth.copy();self.elapsed=0.

    def update(self,rates,dt):
        self.elapsed+=dt
        for key,indices in self.groups.items():
            rate=float(np.mean(rates[indices])) if len(indices) else 0.
            self.smooth[key]+=(1-np.exp(-dt/.15))*(rate-self.smooth[key])
            self.baseline[key]+=(1-np.exp(-dt/3.))*(self.smooth[key]-self.baseline[key])
        response={key: max(0.,self.smooth[key]-self.baseline[key]) for key in self.groups}
        escape=max(response['escape_L'],response['escape_R']) if self.elapsed>1 else 0.
        left, right = self.smooth['network_L'], self.smooth['network_R']
        scale = self.options['network_scale_hz']
        turn_dn = (self.smooth['turn_R']-self.smooth['turn_L'])/40
        turn_network = (right-left)/self.options['bilateral_turn_scale_hz']
        return {'rates':self.smooth.copy(),'baseline':self.baseline.copy(),
                'escape_drive':float(np.clip(escape/30,0,1)),
                'turn_drive':float(np.clip(turn_dn+turn_network,-1,1)),
                'turn_dn':float(turn_dn), 'turn_network':float(turn_network),
                'landing_drive':float(np.clip((self.smooth['landing_L']+self.smooth['landing_R'])/80,0,1)),
                # Artistic decoder of real downstream activity, not fitted muscle physiology.
                # No constant exploration drive: a silent disconnected graph comes to rest.
                'locomotion_drive':float(1-np.exp(-(left+right)/(2*scale))),
                'probe_left':float(1-np.exp(-left/scale)),
                'probe_right':float(1-np.exp(-right/scale)),
                'decoder':self.options.copy(),
                'readout_neurons':{key:len(v) for key,v in self.groups.items()},
                'validated_looming':False}
