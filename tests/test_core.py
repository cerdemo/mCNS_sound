import json
import socket
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from pythonosc.osc_packet import OscPacket

from mcns.__main__ import load_config
from mcns.model import LIF
from mcns.osc import Output
from mcns.vision import ImageInput, stimulus


def params():
    return load_config("configs/default.json")["model"]


class ModelTests(unittest.TestCase):
    def test_rest_and_analytic_constant_drive(self):
        model = LIF(sparse.csr_matrix((1, 1)), params())
        for _ in range(100):
            self.assertFalse(model.step(np.array([0.0])).any())
        for _ in range(20):
            self.assertFalse(model.step(np.array([.5])).any())
        self.assertAlmostEqual(model.v[0], .5 * (1-np.exp(-1)), places=6)

    def test_direction_delay_and_inhibitory_sign(self):
        p = dict(params(), synapse_gain=1)
        # Only neuron 0 drives neuron 1. The first spike reaches g two ticks later.
        model = LIF(sparse.csr_matrix([[0, 0], [8, 0]]), p)
        self.assertEqual(model.step(np.array([100., 0.])).tolist(), [True, False])
        model.step(np.zeros(2))
        self.assertEqual(model.g[1], 0)
        model.step(np.zeros(2))
        self.assertGreater(model.g[1], 0)
        target_spikes = 0
        for _ in range(100):
            target_spikes += model.step(np.array([2.0, 0.0]))[1]
        self.assertGreater(target_spikes, 0)
        inhibitory = LIF(sparse.csr_matrix([[0, 0], [-8, 0]]), p)
        inhibitory.step(np.array([100., 0.]))
        for _ in range(20):
            self.assertFalse(inhibitory.step(np.zeros(2))[1])
        self.assertLess(inhibitory.v[1], 0)

    def test_refractory_and_chunk_state_continuity(self):
        a, b = [LIF(sparse.csr_matrix((1, 1)), params()) for _ in range(2)]
        whole = [bool(a.step(np.array([100.]))[0]) for _ in range(60)]
        chunked = []
        for _ in range(3):
            chunked.extend(bool(b.step(np.array([100.]))[0]) for _ in range(20))
        self.assertEqual(whole, chunked)
        self.assertTrue(np.all(np.diff(np.flatnonzero(whole)) >= 3))
        np.testing.assert_equal(a.v, b.v)

    def test_external_input_does_not_drive_other_neurons(self):
        neurons = pd.DataFrame({"is_input": [True, True, False],
                                "assignedOlHex1": [1., 2., np.nan],
                                "assignedOlHex2": [1., 1., np.nan]})
        mapper = ImageInput(neurons, params())
        black, white = mapper.current(stimulus("black", 0)), mapper.current(stimulus("white", 0))
        self.assertEqual(white[2], 0)
        np.testing.assert_allclose(white[:2] - black[:2], params()["input_gain"])
        self.assertFalse(np.array_equal(stimulus("bar", 0), stimulus("bar", 1)))

    def test_non_finite_input_fails(self):
        model = LIF(sparse.csr_matrix((1, 1)), params())
        with self.assertRaises(FloatingPointError):
            model.step(np.array([np.nan]))


class OSCTests(unittest.TestCase):
    def test_udp_round_trip_and_normalized_contract(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        sender = Output("127.0.0.1", receiver.getsockname()[1])
        try:
            sender.activity(7, .35, [3., 10.], [.03, .1])
            packets = [OscPacket(receiver.recv(4096)).messages[0].message for _ in range(2)]
            self.assertEqual([p.address for p in packets], ["/mcns/rates", "/mcns/activity"])
            self.assertEqual(packets[0].params[0], 7)
            np.testing.assert_allclose(packets[0].params[1:], [.35, 3., 10.], rtol=1e-6)
            np.testing.assert_allclose(packets[1].params[2:], [.03, .1], rtol=1e-6)
        finally:
            sender.close()
            receiver.close()


if __name__ == "__main__":
    unittest.main()
