"""Select real bilateral visual-to-descending paths, without mirrored synthetic cells."""
import numpy as np
import pandas as pd

ESCAPE_TYPES = ['LC4', 'LPLC2', 'DNp01', 'DNp02', 'DNp04', 'DNp11']
READOUT_TYPES = ['DNp01', 'DNp02', 'DNp04', 'DNp11', 'DNp07', 'DNp10', 'DNa02']


def select_bilateral(a, path, selection, batches):
    eligible = a[(a.status == 'Traced') & a.somaSide.isin(['L','R'])]
    h = eligible[(eligible.superclass == 'ol_intrinsic') & eligible.assignedOlHex1.notna()
                 & eligible.assignedOlHex2.notna()]
    dq, dr = h.assignedOlHex1-selection['center'][0], h.assignedOlHex2-selection['center'][1]
    core = h[np.maximum.reduce([abs(dq),abs(dr),abs(dq-dr)]) <= selection['radius']]
    core_ids = core.bodyId.to_numpy()
    motion = eligible[eligible.type.isin([f'T{n}{c}' for n in (4,5) for c in 'abcd'])]
    index = pd.Index(motion.bodyId)
    scores = np.zeros(len(motion),np.int64)
    rows = 0
    for pre,post,weight in batches(path):
        rows += len(pre)
        mask = np.isin(pre,core_ids)
        dest = index.get_indexer(post[mask]); valid=dest>=0
        np.add.at(scores,dest[valid],weight[mask][valid])
    motion = motion.assign(input_synapses=scores)
    motion = (motion[motion.input_synapses>0].sort_values(['input_synapses','bodyId'],ascending=[False,True])
              .groupby(['type','somaSide']).head(selection['downstream_per_type']))
    names = selection.get('seed_types', ESCAPE_TYPES+READOUT_TYPES)
    prefixes = tuple(selection.get('seed_prefixes', []))
    seed_mask = eligible.type.isin(names)
    if prefixes:
        seed_mask |= eligible.type.fillna('').str.startswith(prefixes)
    seeds = eligible[seed_mask]
    wide_mask = eligible.type.isin(selection.get('wide_input_types', []))
    if prefixes:
        wide_mask |= eligible.type.fillna('').str.startswith(prefixes)
    wide_ids = set(eligible[wide_mask].bodyId)
    selected = set(core_ids)|set(motion.bodyId)|set(seeds.bodyId)
    frontier = seeds.bodyId.to_numpy()
    # Two upstream layers preserve actual intermediates into the chosen VPN/DN cells.
    allowed = a[(a.status=='Traced') & a.superclass.isin(
        ['ol_intrinsic','visual_projection','cb_intrinsic','descending_neuron'])].bodyId.to_numpy()
    for depth in range(2):
        pieces=[]
        for pre,post,weight in batches(path):
            mask=np.isin(post,frontier)&np.isin(pre,allowed)
            if mask.any():pieces.append(pd.DataFrame({'pre':pre[mask],'post':post[mask],'weight':weight[mask]}))
        if not pieces:break
        parents=(pd.concat(pieces).groupby(['pre','post'],as_index=False).weight.sum()
                 .sort_values(['weight','pre'],ascending=[False,True]))
        rank = parents.groupby('post').cumcount()
        limit = np.where(parents.post.isin(wide_ids), selection.get('upstream_per_seed',6),
                         selection.get('upstream_per_cell',6))
        parents = parents[rank < limit]
        frontier=np.array(sorted(set(parents.pre)-selected),dtype=np.int64)
        selected.update(frontier)
        print(f'Bilateral upstream layer {depth+1}: {len(frontier)} actual cells',flush=True)
    neurons=a[a.bodyId.isin(selected)].sort_values('bodyId').reset_index(drop=True).copy()
    neurons['is_readout']=neurons.type.isin(READOUT_TYPES+['DNp15','DNp20','DNp22']) | neurons.type.fillna('').str.startswith('DNg02_')
    return neurons, rows
