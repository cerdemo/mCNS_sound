import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from scipy import sparse

from mcns.__main__ import load_config
from mcns.prepare import FILES, prepare
from mcns.runtime import run
from mcns.tracking import Features, send_tracking


def fixture(root):
    # Two inputs, a target, an excluded untraced cell, and an unknown NT cell.
    a = pd.DataFrame({"bodyId": [10, 20, 30, 40, 50],
                      "type": ["L1", "L2", "T4a", "L1", "Mi1"],
                      "somaSide": ["R"]*5, "status": ["Traced"]*3 + ["Orphan", "Traced"],
                      "superclass": ["ol_intrinsic"]*5,
                      "assignedOlHex1": [18., 19., np.nan, 18., 18.],
                      "assignedOlHex2": [19., 19., np.nan, 19., 20.]})
    nt = pd.DataFrame({"body": [10, 20, 30, 40],
                       "consensus_nt": ["acetylcholine", "gaba", "acetylcholine", "gaba"],
                       "predicted_nt": ["acetylcholine", "gaba", "acetylcholine", "gaba"],
                       "predicted_nt_confidence": [.9]*4})
    edges = pd.DataFrame({"body_pre": [10, 20, 10, 40, 30, 50],
                          "body_post": [30, 30, 30, 10, 999, 30],
                          "weight": [4, 2, 3, 10, 8, 6]}, dtype="int64")
    for key, frame in [("annotations", a), ("neurotransmitters", nt), ("connections", edges)]:
        frame.to_feather(root / FILES[key])


class GraphTests(unittest.TestCase):
    def test_selection_join_sign_duplicates_and_cut_edges(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                report = prepare(root, root / "graph", load_config("configs/default.json"))
            neurons = pd.read_feather(root / "graph/neurons.feather")
            self.assertEqual(neurons.bodyId.tolist(), [10, 20, 30, 50])
            self.assertEqual(report["duplicate_pairs_aggregated"], 1)
            self.assertEqual(report["missing_nt_rows"], 1)
            self.assertEqual(report["unmodelled_nt_neurons"], 1)
            self.assertEqual(report["cut_incoming_synapses"], 10)
            self.assertEqual(report["cut_outgoing_synapses"], 8)
            matrix = sparse.load_npz(root / "graph/weights.npz").toarray()
            self.assertEqual(matrix[2, 0], 7)
            self.assertEqual(matrix[2, 1], -2)
            self.assertEqual(matrix[2, 3], 0)
            self.assertEqual(matrix[0, 2], 0)


class TrackingTests(unittest.TestCase):
    def test_reacquisition_resets_velocity(self):
        f = Features()
        self.assertEqual(f.velocity("face", [.2, .3], 0), [0., 0.])
        np.testing.assert_allclose(f.velocity("face", [.3, .3], .1), [1, 0])
        empty = f.summarize(SimpleNamespace(hand_landmarks=[], handedness=[]),
                            SimpleNamespace(face_landmarks=[]), .2)
        self.assertEqual(empty["face"][0], 0)
        self.assertEqual(f.velocity("face", [.8, .3], .3), [0., 0.])

    def test_stale_features_send_absence(self):
        class Recorder:
            def __init__(self):
                self.messages = []
            def send(self, address, *values):
                self.messages.append((address, values))
        osc = Recorder()
        send_tracking(osc, (1, 0, {"Left": [1, .2, .3, 1., 0., 2., .9]}), 2)
        self.assertEqual(osc.messages[0][1][2], 0)
        self.assertEqual(osc.messages[2][1][1], 0)


class IntegrationTests(unittest.TestCase):
    @unittest.skipUnless(Path("build/visual-v1/manifest.json").exists(), "Requires prepared MaleCNS data")
    def test_real_graph_stimuli_and_persisted_metadata(self):
        config = load_config("configs/default.json")
        with tempfile.TemporaryDirectory() as folder:
            summaries = {}
            # Decode/send is tested over real UDP separately; isolate this stimulus comparison.
            with patch("mcns.runtime.Output") as output, contextlib.redirect_stdout(io.StringIO()):
                for source in ("black", "white", "static", "bar"):
                    summaries[source] = run("build/visual-v1", config, source, 2,
                                             Path(folder)/source, realtime=False)
                    output.return_value.activity.assert_called()
            self.assertEqual(summaries["black"]["total_spikes"], 0)
            self.assertGreater(summaries["white"]["non_input_spikes"], 0)
            self.assertGreater(summaries["bar"]["non_input_spikes"], 0)
            static = pd.read_csv(Path(folder)/"static/activity.csv")
            bar = pd.read_csv(Path(folder)/"bar/activity.csv")
            rates = [c for c in bar.columns if c.endswith("_hz")]
            self.assertFalse(np.array_equal(static[rates].to_numpy(), bar[rates].to_numpy()))
            info = json.loads((Path(folder)/"bar/run.json").read_text())
            self.assertEqual(len(info["populations"]), len(rates))
            self.assertEqual(summaries["bar"]["osc_windows"], 40)

    def test_camera_open_failure_still_writes_summary_and_stop(self):
        if not Path("build/visual-v1/manifest.json").exists():
            self.skipTest("Requires prepared graph")
        with tempfile.TemporaryDirectory() as folder:
            with patch("mcns.runtime.Camera", side_effect=RuntimeError("permission denied")), \
                    patch("mcns.runtime.Output") as out, contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, "permission denied"):
                    run("build/visual-v1", load_config("configs/default.json"), "camera", 1, folder)
            summary = json.loads((Path(folder)/"summary.json").read_text())
            self.assertEqual(summary["status"], "error")
            self.assertEqual(summary["simulation_seconds"], 0)
            out.return_value.send.assert_any_call("/mcns/state", "error")
            self.assertTrue(np.all(out.return_value.activity.call_args.args[-1] == 0))


if __name__ == "__main__":
    unittest.main()
