"""Compare graded visual responses and actual descending spikes without conflating units."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.hybrid import HybridVisualNetwork
from mcns.retina import BinocularInput
from mcns.__main__ import load_config
from mcns.prepare import sha256


def validate():
    graph=Path('build/flight-audit-v1');config=load_config('configs/flight-audit.json')
    options=json.loads(Path('configs/hybrid-experiment.json').read_text())
    n=pd.read_feather(graph/'neurons.feather');w=sparse.load_npz(graph/'weights.npz')
    groups={};types=n.type.fillna('');params=config['model'];dt=params['dt_ms']/1000
    for side in ['L','R']:
        for name,mask in [('DNa02',types=='DNa02'),('DNg02',types.str.startswith('DNg02_'))]+[(f'T{k}{c}',types==f'T{k}{c}') for k in [4,5] for c in 'abcd']:
            groups[name+'_'+side]=np.flatnonzero(mask & (n.somaSide==side))
    x=np.tile(np.arange(128)/128,(128,1));trials=[]
    for disconnected,eye,direction in [(False,s,d) for s in ['L','R'] for d in [-1,0,1]]+[(True,'L',1)]:
        model=HybridVisualNetwork(w,n,params,options);model.set_connections(not disconnected)
        retina=BinocularInput(n,params,config['embodiment']);counts=np.zeros(len(n));sum_release=np.zeros(len(n))
        current=np.zeros(len(n));started=time.monotonic();saturated=0.;series=[];window=np.zeros(len(n))
        for step in range(round(3/dt)):
            t=step*dt
            if step%round(.033/dt)==0:
                current.fill(0)
                for side in ['L','R']:
                    phase=direction*max(0,t-1)*2 if side==eye else 0
                    gray=(.5+.45*np.sin(2*np.pi*(x*4-phase))).astype(np.float32)
                    current[retina.indices[side]]=retina.maps[side].current(gray)
            spikes,release=model.step(current)
            saturated=max(saturated,model.saturated_fraction)
            if t>=1:
                counts+=spikes;sum_release+=release*dt;window+=spikes
                if (step+1)%round(.05/dt)==0:
                    series.append({k:float(window[ix].mean()/.05) if len(ix) else None for k,ix in groups.items() if k.startswith('DN')});window.fill(0)
        record={'eye':eye,'direction':direction,'disconnected':disconnected,'wall_seconds':time.monotonic()-started,
            'max_spiking_hz':float(counts.max()/2),
            'spiking_cells_above_300hz':int(np.sum(counts[~model.graded]/2>300)),
            'spiking_cell_count':int(np.sum(~model.graded)),'max_graded_saturation_fraction':saturated,
            'descending_hz':{k:float(counts[ix].mean()/2) if len(ix) else None for k,ix in groups.items() if k.startswith('DN')},
            'visual_release_au':{k:float(sum_release[ix].mean()/2) if len(ix) else None for k,ix in groups.items() if k.startswith('T')},
            'descending_windows':series}
        trials.append(record);print(eye,direction,'off',disconnected,record['descending_hz'],'saturation',saturated,flush=True)
    direction_pairs={}
    for eye in ['L','R']:
        selected={t['direction']:t for t in trials if t['eye']==eye and not t['disconnected']}
        def asym(t):
            rates=t['descending_hz'];return rates['DNg02_R']-rates['DNg02_L']
        baseline=asym(selected[0])
        positive,negative=asym(selected[1])-baseline,asym(selected[-1])-baseline
        direction_pairs[eye]={'positive_minus_static_hz':positive,'negative_minus_static_hz':negative,
            'opposite_signs':positive*negative<0,'both_above_0_1hz':min(abs(positive),abs(negative))>=.1}
    gates={
        'descending_silent_when_disconnected':all(all(value==0 for value in t['descending_hz'].values()) for t in trials if t['disconnected']),
        'opposite_direction_responses_both_eyes':all(v['opposite_signs'] and v['both_above_0_1hz'] for v in direction_pairs.values()),
        'no_sustained_spiking_above_300hz':all(t['spiking_cells_above_300hz']==0 for t in trials),
        'no_graded_saturation':all(t['max_graded_saturation_fraction']==0 for t in trials)}
    report={'screen_gates':gates,'direction_pairs':direction_pairs,'eligible_for_runtime':all(gates.values()),
        'model':'experimental hybrid; graded output is a.u., descending output is simulated spikes/s',
        'options':options,'config':config,'graph_manifest_sha256':sha256(graph/'manifest.json'),
        'code_sha256':{str(p):sha256(p) for p in [Path('mcns/hybrid.py'),Path('mcns/model.py'),Path(__file__)]},
        'protocol':'Identical to validate_direction: 1 s settling + 2 s opposite/static gratings, mean luminance 0.5',
        'trials':trials,'biological_validation_passed':False}
    (graph/'hybrid-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':validate()
