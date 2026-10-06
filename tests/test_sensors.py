import unittest
import numpy as np
from mcns.sensors import LIMB_IDS, LimbSensors, validate_probes


class SensorTests(unittest.TestCase):
    def sample(self, t, x=.5, y=.5):
        return (t, {'sample_time': t, 'probes': [dict(id=name, x=x, y=y) for name in LIMB_IDS]})

    def test_pixels_semantics_motion_and_stale_exit(self):
        sensors = LimbSensors()
        # BGR: red, not blue. The smallest overlapping detection wins.
        frame = np.zeros((20, 40, 3), np.uint8)
        frame[..., 2] = 255
        scene = {'objects': [dict(id=1, label='person', box=[0, 0, 1, 1], score=.9),
                             dict(id=2, label='cup', box=[.4, .4, .7, .7], score=.8)]}
        a, events = sensors.update(frame, 4, 10, self.sample(1), scene, 1)
        self.assertEqual(len(a), 8)
        self.assertEqual(a[0]['rgb'], [1., 0., 0.])
        self.assertAlmostEqual(a[0]['luminance'], .2126)
        self.assertEqual(a[0]['object']['label'], 'cup')
        self.assertEqual(len(events), 8)
        self.assertFalse(a[0]['motion']['valid'])
        b, events = sensors.update(frame, 5, 10, self.sample(1.05, .51), scene, 1.05)
        self.assertFalse(events)
        self.assertAlmostEqual(b[0]['motion']['vx'], .2)
        c, _ = sensors.update(frame, 6, 10, self.sample(1.1, .53), scene, 1.1)
        self.assertAlmostEqual(c[0]['motion']['ax'], 4.)
        repeated, _ = sensors.update(frame, 6, 10, self.sample(1.1, .53), scene, 1.12)
        self.assertEqual(c[0]['motion'], repeated[0]['motion'])
        stale, events = sensors.update(frame, 6, 10, self.sample(1.1, .53), scene, 1.6)
        self.assertTrue(all(not p['valid'] and not p['motion']['valid'] for p in stale))
        self.assertEqual([e['event'] for e in events], ['exit']*8)
        fresh, _ = sensors.update(frame, 8, 10, self.sample(1.65), scene, 1.65)
        self.assertFalse(fresh[0]['motion']['valid'])

    def test_bounds_frame_age_and_missing_inference(self):
        sensors = LimbSensors()
        frame = np.full((4, 4), 128, np.uint8)
        p, _ = sensors.update(frame, 1, 0, self.sample(1, 0, 1), None, 1)
        self.assertTrue(p[0]['valid'])
        self.assertFalse(p[0]['semantic_valid'])
        self.assertAlmostEqual(p[0]['luminance'], 128/255)
        p, _ = sensors.update(frame, 1, 351, self.sample(1), None, 1)
        self.assertFalse(p[0]['valid'])
        p, _ = sensors.update(frame, 1, 0, self.sample(1, -.01), None, 1)
        self.assertFalse(p[0]['valid'])
        self.assertEqual(p[0]['rgb'], [0., 0., 0.])

    def test_malformed_probe_payloads_rejected(self):
        good = self.sample(1)[1]
        self.assertEqual(len(validate_probes(good)[0]), 8)
        for bad in (dict(good, probes=[good['probes'][0]]), dict(good, sample_time=float('nan')),
                    dict(good, probes=[dict(p, x=float('inf')) for p in good['probes']]),
                    dict(good, probes=[dict(p, id='antenna-L') for p in good['probes']])):
            with self.assertRaises(ValueError):
                validate_probes(bad)

if __name__ == '__main__':
    unittest.main()
