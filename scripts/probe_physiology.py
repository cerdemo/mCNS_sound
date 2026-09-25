"""Sensitivity probes only: do NOT deploy unmeasured gains/tonic drive as physiology."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.model import LIF
from mcns.retina import BinocularInput
from mcns.__main__ import load_config

def probe(graph,config_path,out):
    n=pd.read_feather(Path(graph)/'neurons.feather');w=sparse.load_npz(Path(graph)/'weights.npz')
    config=load_config(config_path);report={'scope':'Uncalibrated diagnostic interventions, not biological parameter estimates','conditions':{}}
    visual=n.superclass.isin(['ol_intrinsic','visual_projection']).to_numpy() & ~n.is_input.to_numpy()
    types=n.type.fillna('');groups={}
    for side in ['L','R']:
        for name,mask in [('DNa02',types=='DNa02'),('DNg02',types.str.startswith('DNg02_')),('DNp15',types=='DNp15'),('T4',types.str.match('^T4[abcd]$')),('T5',types.str.match('^T5[abcd]$'))]:
            groups[name+'_'+side]=np.flatnonzero(mask & (n.somaSide==side))
    for name,gain,tonic,polarity in [('reference',.04,0,1),('gain_x2',.08,0,1),('gain_x4',.16,0,1),('visual_tonic',.04,1.05,1),('dark_driven_tonic',.04,1.05,-1)]:
        condition={}
        for side_stim in ['L','R']:
            params={**config['model'],'synapse_gain':gain};engine=LIF(w,params);retina=BinocularInput(n,params,config['embodiment'])
            counts=np.zeros(len(n));current=np.zeros(len(n));xx=np.tile(np.linspace(0,1,128),(128,1));dt=engine.dt_ms/1000
            for step in range(round(2/dt)):
                t=step*dt
                if step%round(.033/dt)==0:
                    current.fill(0);current[visual]=tonic
                    for side in ['L','R']:
                        phase=t*2 if side==side_stim else 0
                        gray=(.5+.45*np.sin(2*np.pi*(xx*3-phase))).astype(np.float32)
                        current[retina.indices[side]]=retina.maps[side].current(gray if polarity>0 else 1-gray)
                spikes=engine.step(current)
                if t>=1:counts+=spikes
            condition[side_stim]={'total_mean_hz':float(counts.mean()),'groups':{k:float(counts[ix].mean()) if len(ix) else None for k,ix in groups.items()}}
        report['conditions'][name]=condition;print(name,condition,flush=True)
    Path(out).write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    probe('build/flight-audit-v1','configs/flight-audit.json','build/flight-audit-v1/physiology-probes.json')
