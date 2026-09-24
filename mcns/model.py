"""Dimensionless current-based LIF with exponential synapses and fixed delay.

Rest/reset=0, threshold=1. This is not a reproduction of Shiu's Brian2 model.
Synaptic current decays during refractoriness and is not cleared by a spike.
"""
import numpy as np


class LIF:
    def __init__(self, weights, params):
        self.dt_ms = float(params["dt_ms"])
        tm, ts = params["tau_membrane_ms"], params["tau_synapse_ms"]
        if not (0 < self.dt_ms <= min(tm, ts)):
            raise ValueError("Require 0 < dt <= both time constants")
        self.em, self.es = np.exp(-self.dt_ms / tm), np.exp(-self.dt_ms / ts)
        self.coupling = ((self.dt_ms / tm) * self.em if tm == ts else
                         ts / (ts - tm) * (self.es - self.em))
        self.delay = max(1, int(round(params["delay_ms"] / self.dt_ms)))
        self.refractory = max(0, int(round(params["refractory_ms"] / self.dt_ms)))
        self.weights = weights.astype(np.float32) * params["synapse_gain"]
        self.n = weights.shape[0]
        if weights.shape != (self.n, self.n):
            raise ValueError("Weights must be square, row=target column=source")
        self.v = np.zeros(self.n, np.float32)
        self.g = np.zeros(self.n, np.float32)
        self.available_at = np.zeros(self.n, np.int64)
        self.pending = np.zeros((self.delay + 1, self.n), np.float32)
        self.tick = 0

    def step(self, external):
        slot = self.tick % len(self.pending)
        self.g += self.pending[slot]
        self.pending[slot].fill(0)
        active = self.tick >= self.available_at
        self.v[active] = (self.v * self.em + external * (1 - self.em)
                          + self.g * self.coupling)[active]
        self.g *= self.es
        spikes = active & (self.v >= 1)
        self.v[spikes] = 0
        self.available_at[spikes] = self.tick + self.refractory + 1
        if spikes.any():
            self.pending[(self.tick + self.delay) % len(self.pending)] += self.weights @ spikes.astype(np.float32)
        self.tick += 1
        if not np.isfinite(self.v).all() or not np.isfinite(self.g).all():
            raise FloatingPointError("Non-finite neural state; reduce gain/check graph")
        return spikes
