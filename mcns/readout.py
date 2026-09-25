"""Explicit continuous decoder of real descending-cell rates; no fear state machine.

Uniform LIF physiology is not validated as a looming detector. Keep rates and
baseline-relative response visible rather than labelling every spike as fear.
"""
import numpy as np


class DescendingReadout:
    def __init__(self,neurons):
        self.groups={}
        for side in ('L','R'):
            for name,types in [('escape',['DNp01','DNp02','DNp04','DNp11']),
                               ('landing',['DNp07','DNp10']),('turn',['DNa02']),
                               ('visual',['LC4','LPLC2'])]:
                self.groups[name+'_'+side]=np.flatnonzero((neurons.somaSide==side)&neurons.type.isin(types))
        self.smooth={key:0. for key in self.groups};self.baseline=self.smooth.copy();self.elapsed=0.

    def update(self,rates,dt):
        self.elapsed+=dt
        for key,indices in self.groups.items():
            rate=float(np.mean(rates[indices])) if len(indices) else 0.
            self.smooth[key]+=(1-np.exp(-dt/.15))*(rate-self.smooth[key])
            self.baseline[key]+=(1-np.exp(-dt/3.))*(self.smooth[key]-self.baseline[key])
        response={key: max(0.,self.smooth[key]-self.baseline[key]) for key in self.groups}
        escape=max(response['escape_L'],response['escape_R']) if self.elapsed>1 else 0.
        return {'rates':self.smooth.copy(),'baseline':self.baseline.copy(),
                'escape_drive':float(np.clip(escape/30,0,1)),
                'turn_drive':float(np.clip((self.smooth['turn_R']-self.smooth['turn_L'])/40,-1,1)),
                'landing_drive':float(np.clip((self.smooth['landing_L']+self.smooth['landing_R'])/80,0,1)),
                'readout_neurons':{key:len(v) for key,v in self.groups.items()},
                'validated_looming':False}
