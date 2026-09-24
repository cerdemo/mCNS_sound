"""Start both real MediaPipe models on a blank image, without accessing a camera."""
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mcns.tracking import Tracker


class BlankCamera:
    def __init__(self):
        self.frame = (1, time.monotonic(), np.zeros((240, 320, 3), np.uint8))

    def get(self):
        return self.frame


def main():
    tracker = Tracker(BlankCamera(), "models")
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            result = tracker.get()
            if result is not None:
                if any(values[0] for values in result[2].values()):
                    raise AssertionError("Unexpected detection in blank frame")
                print("Both models ran successfully; blank frame has no detections.")
                return
            time.sleep(.05)
        raise RuntimeError("Tracker startup timed out")
    finally:
        tracker.close()


if __name__ == "__main__":
    main()
