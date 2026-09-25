"""Authored installation behavior, NOT an inferred emotion of the neural model."""
import math

import numpy as np


def movement(snapshot, now, params):
    """Use fresh tracked human landmarks; no image-difference/background heuristic."""
    if snapshot is None or now - snapshot[1] > .5:
        return {"valid": False, "present": False, "raw_motion": 0., "human_x": .5}
    features = snapshot[2]
    visible = [values for values in features.values() if values[0]]
    if not visible:
        return {"valid": True, "present": False, "raw_motion": 0., "human_x": .5}
    speed = max(math.hypot(values[3], values[4]) for values in visible)
    raw = np.clip((speed - params["motion_deadband"]) / params["motion_scale"], 0, 1)
    return {"valid": True, "present": True, "raw_motion": float(raw),
            "human_x": float(np.mean([values[1] for values in visible]))}


class FlyBehavior:
    """Flying → escaping → hidden → recovering, with hysteresis and bounded output."""
    def __init__(self, params):
        self.p = params
        self.state = "flying"
        self.t = self.entered = self.last_motion = self.above_for = self.motion = 0.
        self.position = np.array([.5, .5])
        self.escape_start = self.position.copy()
        self.shelter = np.array([.05, .08])

    def update(self, dt, observation):
        self.t += dt
        p = self.p
        self.motion += (1 - math.exp(-dt / p["smoothing_seconds"])) * (observation["raw_motion"] - self.motion)
        self.above_for = self.above_for + dt if self.motion >= p["trigger_threshold"] else 0.
        if self.motion >= p["quiet_threshold"] or not observation["valid"]:
            self.last_motion = self.t
        triggered = observation["valid"] and self.above_for >= p["trigger_hold_seconds"]
        if self.state in ("flying", "recovering") and triggered:
            self.state, self.entered = "escaping", self.t
            self.escape_start = self.position.copy()
            self.shelter = np.array([.95 if observation["human_x"] < .5 else .05, .08])
        phase = self.t - self.entered
        if self.state == "escaping" and phase >= p["escape_seconds"]:
            self.state, self.entered = "hidden", self.t
        elif (self.state == "hidden" and observation["valid"]
              and self.t - self.last_motion >= p["hide_quiet_seconds"]):
            self.state, self.entered = "recovering", self.t
        elif self.state == "recovering" and phase >= p["recover_seconds"]:
            self.state, self.entered = "flying", self.t
        previous = self.position.copy()
        cruise = np.array([.5 + .32*math.sin(.71*self.t), .5 + .24*math.sin(1.13*self.t + .4)])
        phase = self.t - self.entered
        if self.state == "escaping":
            u = min(1., phase / p["escape_seconds"])
            self.position = (1-u)*self.escape_start + u*self.shelter
            gain = (1-u)**2
        elif self.state == "hidden":
            self.position = self.shelter.copy()
            gain = 0.
        elif self.state == "recovering":
            u = min(1., phase / p["recover_seconds"])
            smooth = u*u*(3-2*u)
            self.position = (1-smooth)*self.shelter + smooth*cruise
            gain = smooth
        else:
            self.position = cruise
            gain = 1.
        speed = min(1., float(np.linalg.norm(self.position-previous) / max(dt, 1e-6)))
        # A stale tracker is not evidence of stillness: fail silent until fresh observations resume.
        if not observation["valid"]:
            gain = 0.
        wing = (p["wing_base_hz"] + p["wing_range_hz"]*speed) if gain > 0 else 0.
        return {"state": self.state, "motion": float(self.motion),
                "raw_motion": observation["raw_motion"], "tracking_valid": observation["valid"],
                "human_present": observation["present"], "gain": float(gain),
                "wing_hz": float(wing), "speed": speed,
                "x": float(self.position[0]), "y": float(self.position[1]),
                "quiet_remaining_s": max(0., p["hide_quiet_seconds"]-(self.t-self.last_motion))
                if self.state == "hidden" else 0.}
