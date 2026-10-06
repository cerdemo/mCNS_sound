"""Latest-frame capture and an explicitly approximate image-to-column mapping."""
import threading
import time

import numpy as np


def stimulus(kind, seconds, size=128):
    image = np.zeros((size, size), np.float32)
    if kind == "white":
        image.fill(1)
    elif kind == "gray":
        image.fill(.5)
    elif kind in ("bar", "static"):
        x = .5 if kind == "static" else (seconds * .25) % 1.0
        image[:, np.abs(np.linspace(0, 1, size) - x) < .08] = 1
    elif kind != "black":
        raise ValueError(f"Unknown stimulus: {kind}")
    return image


class ImageInput:
    def __init__(self, neurons, params):
        self.indices = np.flatnonzero(neurons.is_input.to_numpy())
        inp = neurons.iloc[self.indices]
        q, r = inp.assignedOlHex1.to_numpy(), inp.assignedOlHex2.to_numpy()
        if not np.isfinite(q).all() or not np.isfinite(r).all():
            raise ValueError("Input neurons require finite column coordinates")
        x, y = q - .5 * r, np.sqrt(3) / 2 * r
        self.u = (x - x.min()) / max(float(np.ptp(x)), 1)
        self.v = (y - y.min()) / max(float(np.ptp(y)), 1)
        self.n = len(neurons)
        self.baseline, self.gain = params["input_baseline"], params["input_gain"]

    def current(self, gray):
        if gray.ndim != 2 or not np.isfinite(gray).all():
            raise ValueError("Expected finite grayscale image")
        gray = np.clip(gray, 0, 1)
        # Bilinear sampling; camera axes are a design choice, not a calibrated eye.
        x, y = self.u * (gray.shape[1] - 1), self.v * (gray.shape[0] - 1)
        x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
        x1, y1 = np.minimum(x0 + 1, gray.shape[1] - 1), np.minimum(y0 + 1, gray.shape[0] - 1)
        fx, fy = x - x0, y - y0
        values = ((1-fx)*(1-fy)*gray[y0, x0] + fx*(1-fy)*gray[y0, x1]
                  + (1-fx)*fy*gray[y1, x0] + fx*fy*gray[y1, x1])
        current = np.zeros(self.n, np.float32)
        current[self.indices] = self.baseline + self.gain * values
        return current


class Camera:
    """A single capture owner, one replaceable frame, no frame queue."""
    def __init__(self, device=0, mirror=True):
        import cv2
        self.cv2, self.mirror = cv2, mirror
        self.capture = cv2.VideoCapture(device)
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError("Camera could not open. Check device index and macOS Camera permission.")
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.capture.set(cv2.CAP_PROP_FPS, 30)
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.latest, self.error, self.sequence = None, None, 0
        self.thread = threading.Thread(target=self._capture, daemon=True)
        self.thread.start()

    def _capture(self):
        try:
            failed_reads = 0
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    failed_reads += 1
                    if failed_reads >= 5:
                        raise RuntimeError("Camera stopped returning frames")
                    self.stop.wait(.05)
                    continue
                failed_reads = 0
                if self.mirror:
                    frame = self.cv2.flip(frame, 1)
                stamp = time.monotonic()
                with self.lock:
                    self.sequence += 1
                    self.latest = (self.sequence, stamp, frame)
        except Exception as exc:
            self.error = exc
        finally:
            self.capture.release()

    def get(self):
        if self.error:
            raise self.error
        with self.lock:
            return self.latest

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)


def grayscale(frame):
    import cv2
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (128, 128)).astype(np.float32) / 255


def inspect_video(path):
    """Validate actual decodability, not just the filename supplied by the browser."""
    import cv2
    capture = cv2.VideoCapture(str(path))
    try:
        ok, frame = capture.read()
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not ok or frame is None or not np.isfinite(fps) or not 0 < fps <= 240:
            raise ValueError('Video could not be decoded. Try an MP4 (H.264) or MOV file.')
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        count = int(count) if np.isfinite(count) and count > 0 else 0
        h, w = frame.shape[:2]
        return dict(fps=fps, frames=count, duration_s=count/fps if count else None, width=w, height=h)
    finally:
        capture.release()


class VideoFile:
    """Paced, local video frames with the same latest-frame interface as Camera.

    Uses the container's nominal FPS; ignores the audio track. Sequence numbers
    remain monotonic across loops so trackers never confuse a rewind with old data.
    """
    def __init__(self, path, loop=True):
        import cv2
        self.metadata = inspect_video(path)
        self.cv2, self.loop = cv2, loop
        self.capture = cv2.VideoCapture(str(path))
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError('Video could not open')
        self.lock, self.stop, self.ended = threading.Lock(), threading.Event(), threading.Event()
        self.latest, self.error, self.sequence = None, None, 0
        self.position_s = 0.
        self.thread = threading.Thread(target=self._capture, daemon=True)
        self.thread.start()

    def _capture(self):
        try:
            deadline = time.monotonic()
            while not self.stop.is_set():
                ok, frame = self.capture.read()
                if not ok:
                    if not self.loop:
                        self.ended.set()
                        break
                    self.capture.set(self.cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = self.capture.read()
                    if not ok:
                        raise RuntimeError('Video could not rewind')
                with self.lock:
                    self.sequence += 1
                    self.position_s = max(0., (self.capture.get(self.cv2.CAP_PROP_POS_FRAMES)-1)/self.metadata["fps"])
                    self.latest = (self.sequence, time.monotonic(), frame)
                deadline += 1/self.metadata['fps']
                self.stop.wait(max(0, deadline-time.monotonic()))
        except Exception as exc:
            self.error = exc
        finally:
            self.capture.release()

    def get(self):
        if self.error:
            raise self.error
        with self.lock:
            # A low-FPS video's held frame is still a valid current presentation.
            if self.latest is None:
                return None
            return self.latest[0], time.monotonic(), self.latest[2]

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
