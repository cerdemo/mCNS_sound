import unittest
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.circuit import select_bilateral
from scripts.audit_steering import reachable_paths

class SteeringAuditTests(unittest.TestCase):
    def test_reachability_follows_source_to_target_and_keeps_inhibition_distinct(self):
        w=sparse.csr_matrix(np.array([[0,0,0,0],[2,0,0,0],[0,-3,0,0],[0,0,0,0]],dtype=float))
        parents=reachable_paths(w,[0])
        self.assertEqual(parents.tolist(),[0,0,1,-1])
        positive=w.copy();positive.data=np.maximum(positive.data,0);positive.eliminate_zeros()
        self.assertEqual(reachable_paths(positive,[0]).tolist(),[0,0,-1,-1])

    def test_flight_subtype_seed_and_wider_inputs_use_real_ids_and_weights(self):
        a=pd.DataFrame({'bodyId':[10,20,30,40,50], 'type':['L2','DNg02_a','PS1','PS2','PS3'],
            'somaSide':['R']*5,'status':['Traced']*5,
            'superclass':['ol_intrinsic','descending_neuron','cb_intrinsic','cb_intrinsic','cb_intrinsic'],
            'assignedOlHex1':[18.,np.nan,np.nan,np.nan,np.nan],
            'assignedOlHex2':[19.,np.nan,np.nan,np.nan,np.nan]})
        def stream(_):
            yield np.array([30,40,50,10]),np.array([20,20,20,30]),np.array([9,8,7,6])
        s={'center':[18,19],'radius':1,'downstream_per_type':0,'seed_types':[],
           'seed_prefixes':['DNg02_'],'upstream_per_cell':1,'upstream_per_seed':2}
        neurons,rows=select_bilateral(a,None,s,stream)
        self.assertEqual(neurons.bodyId.tolist(),[10,20,30,40])
        self.assertEqual(neurons[neurons.is_readout].bodyId.tolist(),[20])
        self.assertEqual(rows,4)

if __name__=='__main__':unittest.main()
