"""Controlled evidence; a structural path does not imply validated looming selectivity."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import json
import time
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.model import LIF
from mcns.retina import BinocularInput
from mcns.readout import DescendingReadout
from mcns.__main__ import load_config

config=load_config('configs/bilateral.json')
neurons=pd.read_feather('build/bilateral-v1/neurons.feather')
weights=sparse.load_npz('build/bilateral-v1/weights.npz')
y,x=np.mgrid[:128,:128]/127
report={'scope':'Uniform LIF, planar virtual eyes, uncalibrated input; NOT biological validation','stimuli':{}}
for mode in ['static','looming','receding','translation','looming_disconnected']:
    engine=LIF(weights if mode!='looming_disconnected' else weights*0,config['model'])
    retina=BinocularInput(neurons,config['model'],config['embodiment']);readout=DescendingReadout(neurons)
    counts=np.zeros(len(neurons));series=[];start=time.monotonic();current=np.zeros(len(neurons))
    steps=round(3/ (engine.dt_ms/1000));frame=max(1,round(33/engine.dt_ms))
    for step in range(steps):
        t=step*engine.dt_ms/1000
        if step%frame==0:
            r=.02+.18*min(1,max(0,(t-1)/1.5)) if 'looming' in mode else .20-.18*min(1,max(0,(t-1)/1.5)) if mode=='receding' else .06
            cx=.5+.18*np.sin(t*2) if mode=='translation' else .64
            gray=np.where((x-cx)**2+(y-.5)**2<r*r,0.,1.).astype(np.float32)
            current=retina.current(gray,{'x':.5,'y':.5,'angle':0})
        counts+=engine.step(current)
        if (step+1)%round(50/engine.dt_ms)==0:
            state=readout.update(counts/.05,.05);counts.fill(0)
            if t>1:series.append(state)
    report['stimuli'][mode]={'wall_seconds':time.monotonic()-start,
       'max_escape_drive':max(s['escape_drive'] for s in series),
       'mean_rates':{k:float(np.mean([s['rates'][k] for s in series])) for k in series[0]['rates']}}
    print(mode,report['stimuli'][mode],flush=True)
report['looming_selective']=report['stimuli']['looming']['max_escape_drive']>max(report['stimuli'][k]['max_escape_drive'] for k in ['static','receding','translation'])
Path('build/bilateral-v1/validation.json').write_text(json.dumps(report,indent=2)+'\n')
print('Looming selective in this screen: ',report['looming_selective'])
