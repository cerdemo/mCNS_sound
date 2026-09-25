import json
import tempfile
import unittest
from pathlib import Path
from urllib.request import urlopen

import cv2
import numpy as np
import pandas as pd

from mcns.__main__ import load_config
from mcns.behavior import FlyBehavior, movement
from mcns.dashboard import Dashboard
from mcns.preview import encode_preview


class BehaviorTests(unittest.TestCase):
    def setUp(self):
        self.params = load_config("configs/default.json")["behavior"]
        self.model = FlyBehavior(self.params)
        self.quiet = {"valid": True, "present": True, "raw_motion": 0., "human_x": .2}
        self.moving = dict(self.quiet, raw_motion=1.)

    def advance(self, seconds, observation):
        states = []
        for _ in range(round(seconds/.05)):
            states.append(self.model.update(.05, observation))
        return states

    def test_fly_escape_hide_and_recover(self):
        calm = self.advance(1, self.quiet)
        self.assertEqual(calm[-1]["state"], "flying")
        self.assertEqual(calm[-1]["gain"], 1)
        self.assertNotEqual(calm[0]["x"], calm[-1]["x"])
        moving = self.advance(1.5, self.moving)
        self.assertIn("escaping", [s["state"] for s in moving])
        self.assertEqual(moving[-1]["state"], "hidden")
        self.assertEqual(moving[-1]["gain"], 0)
        self.assertEqual(moving[-1]["wing_hz"], 0)
        recovery = self.advance(6, self.quiet)
        self.assertIn("recovering", [s["state"] for s in recovery])
        self.assertEqual(recovery[-1]["state"], "flying")
        for s in calm+moving+recovery:
            self.assertTrue(0 <= s["gain"] <= 1)
            self.assertTrue(0 <= s["x"] <= 1 and 0 <= s["y"] <= 1)

    def test_sustained_movement_stays_hidden_and_stale_is_silent(self):
        states = self.advance(10, self.moving)
        self.assertTrue(all(s["state"] == "hidden" for s in states[-20:]))
        invalid = dict(self.quiet, valid=False)
        states = self.advance(5, invalid)
        self.assertTrue(all(s["gain"] == 0 for s in states))
        self.assertEqual(states[-1]["state"], "hidden")

    def test_tracking_motion_uses_velocity_not_presence(self):
        features = {"face": [1, .5, .5, 0., 0., .2]}
        quiet = movement((3, 1., features), 1.1, self.params)
        self.assertEqual(quiet["raw_motion"], 0)
        self.assertTrue(quiet["present"])
        features["face"][3] = .8
        self.assertEqual(movement((3, 1., features), 1.1, self.params)["raw_motion"], 1)
        self.assertFalse(movement((3, 1., features), 2., self.params)["valid"])


class DashboardTests(unittest.TestCase):
    def test_real_http_metadata_latest_state_and_camera_jpeg(self):
        neurons = pd.DataFrame({"bodyId": [123, 456], "population": ["A", "B"],
                                "is_input": [True, False],
                                "somaLocation": [np.array([1,2,3]), None],
                                "assignedOlHex1": [1., np.nan], "assignedOlHex2": [2., np.nan]})
        dashboard = Dashboard(neurons, ["A", "B"], port=0)
        try:
            meta = json.load(urlopen(dashboard.url+"/api/meta"))
            self.assertEqual(meta["neurons"][0]["id"], "123")
            self.assertIsNone(meta["neurons"][1]["soma"])
            self.assertIsNone(meta["neurons"][1]["hex"])
            for i in range(5):
                dashboard.update(sequence=i, neuron_hz=[1., 2.])
            self.assertEqual(json.load(urlopen(dashboard.url+"/api/state"))["sequence"], 4)
            jpeg = encode_preview(np.zeros((120,160,3), np.uint8))
            dashboard.set_image("camera", jpeg)
            with urlopen(dashboard.url+"/api/camera.jpg") as response:
                self.assertEqual(response.headers["Content-Type"], "image/jpeg")
                image = cv2.imdecode(np.frombuffer(response.read(), np.uint8), cv2.IMREAD_COLOR)
            self.assertEqual(image.shape, (120,160,3))
            with urlopen(dashboard.url) as response:
                self.assertIn(b'cameraPreview', response.read())
        finally:
            dashboard.close()


if __name__ == "__main__":
    unittest.main()
