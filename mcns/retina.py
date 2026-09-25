"""Fly-centred planar camera projection, not calibrated compound-eye optics/stereo."""
import numpy as np
import cv2
from .vision import ImageInput


class BinocularInput:
    def __init__(self,neurons,params,options):
        self.n=len(neurons);self.options=options;self.maps={};self.indices={}
        for side in ('L','R'):
            mask=(neurons.somaSide==side)&neurons.is_input
            subset=neurons[mask].reset_index(drop=True)
            if subset.empty:raise ValueError(f'No real {side} eye inputs')
            self.indices[side]=np.flatnonzero(mask)
            self.maps[side]=ImageInput(subset,params)
        self.eyes={}

    def current(self,gray,pose=None):
        pose=pose or {'x':.5,'y':.5,'angle':0.}
        x,y,angle=pose['x'],pose['y'],pose.get('angle',0.)
        radius=self.options.get('radius',.24);overlap=self.options.get('overlap',.16)
        output=np.zeros(self.n,np.float32)
        for side in ('L','R'):
            # Shared forward strip, separate lateral halves. No fictitious central blind gap.
            lateral=np.linspace(-1,overlap,128) if side=='L' else np.linspace(-overlap,1,128)
            forward=np.linspace(1,-.25,128)
            lat,fwd=np.meshgrid(lateral,forward)
            u=x+radius*(fwd*np.cos(angle)-lat*np.sin(angle))
            v=y+radius*(fwd*np.sin(angle)+lat*np.cos(angle))
            eye=cv2.remap(gray.astype(np.float32),(u*(gray.shape[1]-1)).astype(np.float32),
                         (v*(gray.shape[0]-1)).astype(np.float32),cv2.INTER_LINEAR,
                         borderMode=cv2.BORDER_CONSTANT,borderValue=0)
            self.eyes[side]=eye
            output[self.indices[side]]=self.maps[side].current(eye)
        return output
