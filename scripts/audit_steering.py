"""Reproducible wiring and stimulation audit. Diagnostic injections are never runtime inputs."""
import argparse
import json
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.prepare import FILES,batches,sha256
from mcns.model import LIF
from mcns.retina import BinocularInput
from mcns.__main__ import load_config


def reachable_paths(weights, inputs):
    outgoing=weights.T.tocsr();parent=np.full(weights.shape[0],-1,dtype=int)
    queue=deque(int(i) for i in inputs)
    for i in queue:parent[i]=i
    while queue:
        i=queue.popleft()
        for j in outgoing.indices[outgoing.indptr[i]:outgoing.indptr[i+1]]:
            if parent[j]<0:parent[j]=i;queue.append(int(j))
    return parent


def audit(graph, config, output):
    graph=Path(graph);config=load_config(config)
    n=pd.read_feather(graph/'neurons.feather');w=sparse.load_npz(graph/'weights.npz')
    annotations=pd.read_feather('data/'+FILES['annotations']).set_index('bodyId')
    targets=annotations[annotations.type.fillna('').str.match(r'^(DNa02|DNg02_.*|DNp15|DNp20|DNp22)$')]
    parts=[]
    for pre,post,weight in batches('data/'+FILES['connections']):
        mask=np.isin(post,targets.index.to_numpy())
        if mask.any():parts.append(pd.DataFrame({'pre':pre[mask],'post':post[mask],'weight':weight[mask]}))
    incoming=pd.concat(parts).groupby(['pre','post'],as_index=False).weight.sum()
    ids=set(n.bodyId);index=pd.Index(n.bodyId)
    parents=reachable_paths(w,np.flatnonzero(n.is_input))
    positive=w.copy();positive.data=np.maximum(positive.data,0);positive.eliminate_zeros()
    excitatory_parents=reachable_paths(positive,np.flatnonzero(n.is_input))
    report={'graph':str(graph),'graph_manifest_sha256':sha256(graph/'manifest.json'),'anatomy':[],'probes':{}}
    for body,row in targets.iterrows():
        ins=incoming[incoming.post==body];kept=ins[ins.pre.isin(ids)];i=index.get_indexer([body])[0]
        path=[]
        if i>=0 and parents[i]>=0:
            step=i
            while True:
                cell=n.iloc[step];path.append({'bodyId':int(cell.bodyId),'type':str(cell.type),'side':str(cell.somaSide)})
                if parents[step]==step:break
                step=parents[step]
            path.reverse()
        top=[]
        for r in ins.nlargest(12,'weight').itertuples():
            a=annotations.loc[r.pre] if r.pre in annotations.index else None
            top.append({'bodyId':int(r.pre),'type':str(a.type) if a is not None else None,
                        'weight':int(r.weight),'retained':r.pre in ids})
        report['anatomy'].append({'bodyId':int(body),'type':row.type,'side':str(row.somaSide),
            'present':body in ids,'input_synapses_total':int(ins.weight.sum()),
            'input_synapses_retained':int(kept.weight.sum()),
            'input_fraction_retained':float(kept.weight.sum()/max(1,ins.weight.sum())),
            'shortest_input_path':path,'excitatory_only_reachable':bool(i>=0 and excitatory_parents[i]>=0),
            'top_inputs':top})
    target_indices=np.flatnonzero(n.type.isin(['DNa02','DNp01','DNp02','DNp04','DNp11']) | n.type.str.startswith('DNg02'))
    xx=np.tile(np.linspace(0,1,128),(128,1))
    for mode in ['left_white','right_white','both_white','both_gray','left_motion','right_motion','reverse_motion','direct_DNa02']:
        engine=LIF(w,config['model']);retina=BinocularInput(n,config['model'],config['embodiment'])
        counts=np.zeros(len(n));vmax=np.full(len(target_indices),-np.inf);gmax=vmax.copy();gmin=-vmax.copy()
        steps=round(2/ (engine.dt_ms/1000));frame=round(33/engine.dt_ms);current=np.zeros(len(n))
        for tick in range(steps):
            t=tick*engine.dt_ms/1000
            if tick%frame==0:
                current.fill(0)
                for side in ['L','R']:
                    if mode=='both_white' or mode==('left_white' if side=='L' else 'right_white'):gray=np.ones((128,128),np.float32)
                    elif 'motion' in mode:
                        moving=mode=='reverse_motion' or mode==('left_motion' if side=='L' else 'right_motion')
                        phase=(-t if mode=='reverse_motion' else t)*2 if moving else 0
                        gray=(.5+.45*np.sin(2*np.pi*(xx*3-phase))).astype(np.float32)
                    else:gray=np.full((128,128),.5 if mode=='both_gray' else 0,np.float32)
                    current[retina.indices[side]]=retina.maps[side].current(gray)
                if mode=='direct_DNa02':current[n.type=='DNa02']=2.
            spiked=engine.step(current)
            if t>=1:
                counts+=spiked;vmax=np.maximum(vmax,engine.v[target_indices]);gmax=np.maximum(gmax,engine.g[target_indices]);gmin=np.minimum(gmin,engine.g[target_indices])
        cells=[]
        for j,i in enumerate(target_indices):
            row=w.getrow(i);exc=row.data>0;inh=row.data<0
            cells.append({'bodyId':int(n.iloc[i].bodyId),'type':n.iloc[i].type,'side':str(n.iloc[i].somaSide),
               'hz':float(counts[i]),'max_voltage':float(vmax[j]),'min_synaptic_current':float(gmin[j]),'max_synaptic_current':float(gmax[j]),
               'excitatory_weighted_presynaptic_hz':float(np.dot(row.data[exc],counts[row.indices[exc]])),
               'inhibitory_weighted_presynaptic_hz':float(np.dot(row.data[inh],counts[row.indices[inh]]))})
        report['probes'][mode]={'input_spikes':int(counts[n.is_input].sum()),'other_spikes':int(counts[~n.is_input].sum()),'cells':cells}
        print(mode,[(c['type'],c['side'],c['hz'],round(c['max_voltage'],3)) for c in cells if c['type']=='DNa02'],flush=True)
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--graph',default='build/bilateral-v1');p.add_argument('--config',default='configs/bilateral.json');p.add_argument('--output',default='build/bilateral-v1/steering-audit.json')
    a=p.parse_args();audit(a.graph,a.config,a.output)
