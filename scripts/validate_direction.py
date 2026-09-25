"""Matched left/right-eye direction probes; no injected motion or motor labels."""
import argparse,json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.model import LIF
from mcns.retina import BinocularInput
from mcns.__main__ import load_config


def validate(graph,config_path,output):
    config=load_config(config_path);n=pd.read_feather(Path(graph)/'neurons.feather');w=sparse.load_npz(Path(graph)/'weights.npz')
    params=config['model'];dt=params['dt_ms']/1000
    types=n.type.fillna('');groups={}
    for side in ['L','R']:
        for name,mask in [('DNa02',types=='DNa02'),('DNg02',types.str.startswith('DNg02_'))]+[(f'T{k}{c}',types==f'T{k}{c}') for k in [4,5] for c in 'abcd']:
            groups[name+'_'+side]=np.flatnonzero(mask & (n.somaSide==side))
    watched=np.array(sorted(set(i for indices in groups.values() for i in indices)),dtype=int)
    # Endpoint-exclusive periodic grid: both directions have matched frame luminance.
    x=np.tile(np.arange(128)/128,(128,1));trials=[]
    for disconnected,eye,direction in [(False,s,d) for s in ['L','R'] for d in [-1,0,1]]+[(True,'L',1)]:
        engine=LIF(w*0 if disconnected else w,params);retina=BinocularInput(n,params,config['embodiment'])
        counts=np.zeros(len(n));current=np.zeros(len(n));means=[];started=time.monotonic()
        for tick in range(round(3/dt)):
            t=tick*dt
            if tick%round(.033/dt)==0:
                current.fill(0)
                for side in ['L','R']:
                    phase=direction*max(0,t-1)*2 if side==eye else 0
                    gray=(.5+.45*np.sin(2*np.pi*(x*4-phase))).astype(np.float32)
                    if side==eye:means.append(float(gray.mean()))
                    current[retina.indices[side]]=retina.maps[side].current(gray)
            spikes=engine.step(current)
            if t>=1:counts+=spikes
        hz=counts/2
        record={'eye':eye,'direction':direction,'disconnected':disconnected,'mean_luminance_range':[min(means),max(means)],
            'wall_seconds':time.monotonic()-started,'max_neuron_hz':float(hz.max()),
            'population_hz':{k:float(hz[ix].mean()) if len(ix) else None for k,ix in groups.items()},
            'cells':{str(n.iloc[i].bodyId):{'type':n.iloc[i].type,'side':str(n.iloc[i].somaSide),'hz':float(hz[i])} for i in watched}}
        trials.append(record);print(eye,direction,'disconnected',disconnected,{k:v for k,v in record['population_hz'].items() if k.startswith('DN')},flush=True)
    metrics={}
    for eye in ['L','R']:
        pos=next(r for r in trials if r['eye']==eye and r['direction']==1 and not r['disconnected'])
        neg=next(r for r in trials if r['eye']==eye and r['direction']==-1 and not r['disconnected'])
        metrics[eye]={}
        for group,a in pos['population_hz'].items():
            b=neg['population_hz'][group]
            if a is not None and b is not None:
                metrics[eye][group]={'positive_hz':a,'negative_hz':b,'dsi':(a-b)/(a+b) if a+b>0 else None,
                                    'response_at_least_1hz':max(a,b)>=1}
    active_cells={}
    for eye in ['L','R']:
        pair=[next(r for r in trials if r['eye']==eye and r['direction']==d and not r['disconnected']) for d in [1,-1]]
        cells=[]
        for body,a in pair[0]['cells'].items():
            b=pair[1]['cells'][body]
            if max(a['hz'],b['hz'])>=1:
                cells.append({'bodyId':body,'type':a['type'],'side':a['side'],'positive_hz':a['hz'],
                    'negative_hz':b['hz'],'dsi':(a['hz']-b['hz'])/(a['hz']+b['hz'])})
        active_cells[eye]=cells
    report={'graph':graph,'config':config,'protocol':'1 s static settling + 2 s grating; mean luminance matched; one eye moves, other static',
        'limits':'One contrast/frequency/phase. A nonzero index alone is not validated direction selectivity.',
        'trials':trials,'active_cell_direction_indices':active_cells,'direction_indices':metrics,'biological_validation_passed':False}
    Path(output).write_text(json.dumps(report,indent=2)+'\n');return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph',default='build/flight-audit-v1');p.add_argument('--config',default='configs/flight-audit.json');p.add_argument('--output',default='build/flight-audit-v1/direction-validation.json')
    a=p.parse_args();validate(a.graph,a.config,a.output)
