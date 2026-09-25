import unittest
import numpy as np
import pandas as pd
from scipy import sparse
from mcns.hybrid import HybridVisualNetwork
from mcns.__main__ import load_config
import json
from pathlib import Path

class HybridTests(unittest.TestCase):
    def make(self,weight):
        n=pd.DataFrame({'superclass':['ol_intrinsic','descending_neuron'],'is_input':[True,False]})
        return HybridVisualNetwork(sparse.csr_matrix([[0.,0.],[weight,0.]]),n,
            load_config('configs/default.json')['model'],json.loads(Path('configs/hybrid-experiment.json').read_text()))

    def test_light_hyperpolarizes_graded_input_without_fake_spikes(self):
        a,b=self.make(0),self.make(0)
        for _ in range(400):
            sa,ra=a.step(np.array([.15,0]));sb,rb=b.step(np.array([2.15,0]))
            self.assertFalse(sa[0] or sb[0])
        self.assertGreater(ra[0],rb[0]);self.assertAlmostEqual(float(rb[0]),.2,places=3)

    def test_actual_excitatory_path_required_for_descending_spikes(self):
        a,b,c=self.make(200),self.make(200),self.make(-200);b.set_connections(False)
        totals=np.zeros(3)
        for _ in range(600):
            for j,m in enumerate([a,b,c]):totals[j]+=m.step(np.array([.15,0]))[0][1]
        self.assertGreater(totals[0],0);self.assertEqual(totals[1],0);self.assertEqual(totals[2],0)

    def test_no_weight_mutation_and_nonfinite_input_rejected(self):
        m=self.make(200);before=m.raw.copy();m.set_connections(False);m.set_connections(True)
        self.assertEqual((m.raw!=before).nnz,0)
        with self.assertRaises(ValueError):m.step(np.array([np.nan,0]))

if __name__=='__main__':unittest.main()
