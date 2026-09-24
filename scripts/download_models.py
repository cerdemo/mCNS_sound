"""Fetch official MediaPipe assets explicitly; camera frames are never uploaded."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


def main():
    target = Path("models")
    target.mkdir(exist_ok=True)
    manifest = {}
    for task in ("hand_landmarker", "face_landmarker"):
        url = f"https://storage.googleapis.com/mediapipe-models/{task}/{task}/float16/1/{task}.task"
        path = target / f"{task}.task"
        if not path.exists():
            temporary = path.with_suffix(".part")
            print(f"Downloading {task}…", flush=True)
            with urlopen(url, timeout=60) as response, temporary.open("wb") as stream:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    stream.write(block)
            temporary.replace(path)
        manifest[path.name] = {"url": url, "bytes": path.stat().st_size,
                               "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
