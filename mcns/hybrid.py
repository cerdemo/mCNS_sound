"""Experimental graded visual cells + spiking remainder; never selected implicitly.

This is NOT Flyvis or calibrated physiology. Preserves edge support/sign/count ratios
within each graded postsynaptic row, with an explicitly disclosed row gain. Optical
cells use graded release; all other cells retain the baseline LIF model. No training.
"""
import numpy as np
from scipy import sparse
from .model import LIF


class HybridVisualNetwork:
    def __init__(self,weights,neurons,params,options):
        self.params=dict(params);self.options=dict(options)
        self.graded=neurons.superclass.isin(['ol_intrinsic','visual_projection']).to_numpy()
        self.inputs=neurons.is_input.to_numpy()
        if np.any(self.inputs & ~self.graded):raise ValueError('All retinal input cells must be graded')
        self.n=len(neurons);self.dt=params['dt_ms']/1000
        self.raw=weights.astype(np.float32).tocsr(copy=True)
        if self.raw.shape!=(self.n,self.n):raise ValueError('Graph dimensions differ from neuron table')
        for key in ['tau_visual_ms','release_equivalent_hz','visual_coupling','input_dark_level','input_contrast']:
            if not np.isfinite(options[key]) or options[key]<=0:raise ValueError(f'Invalid {key}')
        if not 0<=options['visual_bias']<=2:raise ValueError('Invalid visual_bias')
        if not 0<options['visual_coupling']<1:raise ValueError('Visual row gain must be contractive (<1)')
        if params['input_gain']<=0:raise ValueError('Input gain must be positive to recover luminance')
        self.engine=LIF(self.raw,params)
        # Graded cells are never integrated or thresholded by the spiking component.
        self.spiking_weights=sparse.diags((~self.graded).astype(np.float32))@self.engine.weights
        self.engine.weights=self.spiking_weights
        row_total=np.asarray(abs(self.raw).sum(axis=1)).ravel()
        self.normalizers=options['visual_coupling']/np.maximum(row_total,1)
        self.visual_weights=sparse.diags(self.normalizers*self.graded)@self.raw
        self.visual_v=np.zeros(self.n,np.float32);self.visual_v[self.graded]=options['visual_bias']
        self.synaptic_drive=np.zeros(self.n,np.float32);self.central_trace=np.zeros(self.n,np.float32)
        self.alpha=1-np.exp(-params['dt_ms']/options['tau_visual_ms'])
        self.syn_decay=np.exp(-params['dt_ms']/params['tau_synapse_ms'])
        self.delay=max(1,round(params['delay_ms']/params['dt_ms']))
        self.history=np.zeros((self.delay+1,self.n),np.float32);self.tick=0
        self.enabled=True;self.saturated_fraction=0.

    def set_connections(self,enabled):
        self.enabled=bool(enabled)
        self.engine.weights=self.spiking_weights if enabled else self.spiking_weights*0

    def step(self,retinal_current):
        retinal_current=np.asarray(retinal_current)
        if retinal_current.shape!=(self.n,) or not np.isfinite(retinal_current).all():
            raise ValueError('Expected finite retinal-current vector')
        delayed=self.history[self.tick%len(self.history)].copy()
        recurrent=self.visual_weights@delayed if self.enabled else np.zeros(self.n)
        target=self.options['visual_bias']+recurrent
        luminance=np.clip((retinal_current[self.inputs]-self.params['input_baseline'])/self.params['input_gain'],0,1)
        # L1/L2 hyperpolarize for light increments. This simplified input is not a
        # photoreceptor simulation and lacks measured biphasic adaptation.
        target[self.inputs]=self.options['input_dark_level']-self.options['input_contrast']*luminance
        self.visual_v[self.graded]+=self.alpha*(target[self.graded]-self.visual_v[self.graded])
        release=np.where(self.graded,np.clip(self.visual_v,0,2),0).astype(np.float32)
        self.saturated_fraction=float(np.mean(self.visual_v[self.graded]>=2))
        # Hz-equivalent release is a conversion parameter, NOT measured graded firing.
        visual_delayed=np.where(self.graded,delayed,0)
        drive=(self.spiking_weights@visual_delayed)*self.options['release_equivalent_hz']*self.params['tau_synapse_ms']/1000 if self.enabled else np.zeros(self.n)
        self.synaptic_drive=self.syn_decay*self.synaptic_drive+(1-self.syn_decay)*drive
        self.synaptic_drive[self.graded]=0
        spikes=self.engine.step(self.synaptic_drive)
        self.engine.v[self.graded]=0
        self.central_trace*=self.syn_decay
        self.central_trace+=spikes.astype(np.float32)
        signal=release+np.where(self.graded,0,self.central_trace/(self.options['release_equivalent_hz']*self.params['tau_synapse_ms']/1000))
        self.history[(self.tick+self.delay)%len(self.history)]=signal
        self.tick+=1
        if not np.isfinite(self.visual_v).all():raise FloatingPointError('Non-finite graded state')
        return spikes,release
