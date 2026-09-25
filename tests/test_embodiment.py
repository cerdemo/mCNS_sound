import unittest
import numpy as np
import pandas as pd
from mcns.retina import BinocularInput
from mcns.scene import Instances
from mcns.__main__ import load_config
from mcns.readout import DescendingReadout

class EmbodimentTests(unittest.TestCase):
    def test_real_bilateral_inputs_pose_changes_retinal_images(self):
        c=load_config('configs/bilateral.json')
        n=pd.read_feather('build/bilateral-v1/neurons.feather')
        retina=BinocularInput(n,c['model'],c['embodiment'])
        gray=np.tile(np.linspace(0,1,128),(128,1)).astype(np.float32)
        a=retina.current(gray,{'x':.3,'y':.5,'angle':0})
        first={k:v.copy() for k,v in retina.eyes.items()}
        b=retina.current(gray,{'x':.7,'y':.5,'angle':0})
        self.assertGreater(float(b.sum()),float(a.sum()))
        self.assertTrue(np.all(a[~n.is_input.to_numpy()]==0))
        retina.current(gray,{'x':.3,'y':.5,'angle':np.pi/2})
        self.assertFalse(np.allclose(first['L'],retina.eyes['L']))
        self.assertFalse(np.allclose(retina.eyes['L'],retina.eyes['R']))
        self.assertTrue(all(len(retina.indices[k])>0 for k in ['L','R']))

    def test_multiple_people_keep_unique_ids_when_detection_order_changes(self):
        tracker=Instances()
        a={'label':'person','center':[.2,.5],'box':[.1,.1,.3,.9]}
        b={'label':'person','center':[.8,.5],'box':[.7,.1,.9,.9]}
        first=tracker.update([a,b],0)
        second=tracker.update([dict(b,center=[.79,.5]),dict(a,center=[.21,.5])],.1)
        self.assertEqual([x['id'] for x in second],[first[1]['id'],first[0]['id']])
        self.assertGreater(second[1]['velocity'][0],0)
        later=tracker.update([a],2)
        self.assertNotIn(later[0]['id'],[x['id'] for x in first])

    def test_descending_readout_requires_actual_descending_activity(self):
        n=pd.read_feather('build/bilateral-v1/neurons.feather')
        readout=DescendingReadout(n)
        rates=np.where(n.is_input,100.,0.)
        for _ in range(40):out=readout.update(rates,.05)
        self.assertEqual(out['escape_drive'],0)
        self.assertFalse(out['validated_looming'])
        self.assertTrue(all(out['readout_neurons'][k]>0 for k in ['escape_L','escape_R']))

if __name__=='__main__':unittest.main()
