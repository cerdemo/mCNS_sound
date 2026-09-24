"""Optional hand/face measurement, independent of neural input and sound mapping."""
import threading
import time
from pathlib import Path

import numpy as np


class Features:
    def __init__(self):
        self.previous = {}

    def velocity(self, key, xy, stamp):
        old = self.previous.get(key)
        self.previous[key] = (np.asarray(xy), stamp)
        if old is None or not 0 < stamp - old[1] < .5:
            return [0., 0.]
        return ((np.asarray(xy) - old[0]) / (stamp - old[1])).tolist()

    def summarize(self, hands, face, stamp):
        result = {"Left": [0, 0., 0., 0., 0., 0., 0.],
                  "Right": [0, 0., 0., 0., 0., 0., 0.],
                  "face": [0, 0., 0., 0., 0., 0.]}
        selected = {}
        for landmarks, handedness in zip(hands.hand_landmarks, hands.handedness):
            label, score = handedness[0].category_name, float(handedness[0].score)
            if label not in ("Left", "Right"):
                continue
            if label not in selected or score > selected[label][1]:
                selected[label] = (landmarks, score)
        for label, (landmarks, score) in selected.items():
            xy = np.array([[p.x, p.y] for p in landmarks])
            center = xy[[0, 5, 9, 13, 17]].mean(axis=0)
            palm = max(float(np.linalg.norm(xy[9] - xy[0])), 1e-6)
            openness = float(np.linalg.norm(xy[[4, 8, 12, 16, 20]] - xy[0], axis=1).mean() / palm)
            result[label] = [1, *center.tolist(), *self.velocity(label, center, stamp), openness, score]
        if face.face_landmarks:
            xy = np.array([[p.x, p.y] for p in face.face_landmarks[0]])
            center = xy.mean(axis=0)
            size = float(np.ptp(xy[:, 0]))
            result["face"] = [1, *center.tolist(), *self.velocity("face", center, stamp), size]
        for key, values in result.items():
            if values[0] == 0:
                self.previous.pop(key, None)
        return result


class Tracker:
    """VIDEO inference in its own thread, always consuming only the newest frame."""
    def __init__(self, camera, model_dir):
        model_dir = Path(model_dir)
        for name in ("hand_landmarker.task", "face_landmarker.task"):
            if not (model_dir / name).is_file():
                raise FileNotFoundError(f"Missing {model_dir / name}; run scripts/download_models.py")
        self.camera, self.model_dir = camera, model_dir
        self.stop, self.lock = threading.Event(), threading.Lock()
        self.latest, self.error = None, None
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        try:
            import cv2
            import mediapipe as mp
            vision = mp.tasks.vision
            base = mp.tasks.BaseOptions
            hands_options = vision.HandLandmarkerOptions(
                base_options=base(model_asset_path=str(self.model_dir / "hand_landmarker.task"),
                                  delegate=base.Delegate.CPU),
                running_mode=vision.RunningMode.VIDEO, num_hands=2)
            face_options = vision.FaceLandmarkerOptions(
                base_options=base(model_asset_path=str(self.model_dir / "face_landmarker.task"),
                                  delegate=base.Delegate.CPU),
                running_mode=vision.RunningMode.VIDEO, num_faces=1)
            features = Features()
            last_seq, last_ms = 0, -1
            origin = time.monotonic()
            with vision.HandLandmarker.create_from_options(hands_options) as hands, \
                    vision.FaceLandmarker.create_from_options(face_options) as face:
                while not self.stop.is_set():
                    frame_info = self.camera.get()
                    if frame_info is None or frame_info[0] == last_seq:
                        self.stop.wait(.005)
                        continue
                    seq, stamp, frame = frame_info
                    milliseconds = max(last_ms + 1, round((stamp - origin) * 1000), 0)
                    image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                     data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    result = features.summarize(hands.detect_for_video(image, milliseconds),
                                                face.detect_for_video(image, milliseconds), stamp)
                    with self.lock:
                        self.latest = (seq, stamp, result)
                    last_seq, last_ms = seq, milliseconds
        except Exception as exc:
            self.error = exc

    def get(self):
        if self.error:
            raise RuntimeError(f"Tracking failed: {self.error}") from self.error
        with self.lock:
            return self.latest

    def close(self):
        self.stop.set()
        self.thread.join(timeout=5)


def send_tracking(osc, snapshot, now, stale_seconds=1.0):
    seq, stamp, features = snapshot if snapshot is not None else (-1, now, {})
    age = (now - stamp) * 1000 if snapshot is not None else -1.0
    stale = snapshot is None or now - stamp > stale_seconds
    for side in ("Left", "Right"):
        values = features.get(side, [0, 0., 0., 0., 0., 0., 0.])
        if stale:
            values = [0, 0., 0., 0., 0., 0., 0.]
        osc.send("/mcns/tracking/hand", int(seq), side, *values, float(age))
    values = features.get("face", [0, 0., 0., 0., 0., 0.])
    if stale:
        values = [0, 0., 0., 0., 0., 0.]
    osc.send("/mcns/tracking/face", int(seq), *values, float(age))
