"""Persistent browser widget host; camera/simulation lifecycle is controlled by the UI."""
import threading
from datetime import datetime
from pathlib import Path
import json
import tempfile
import uuid

import pandas as pd

from .dashboard import Dashboard
from .runtime import run
from .vision import inspect_video
from .audio import extract_audio


class Controller:
    def __init__(self, graph, config, models, port):
        self.graph, self.config, self.models = graph, config, models
        self.lock = threading.Lock()
        self.worker = None
        self.stop_event = threading.Event()
        self.video_directory = tempfile.TemporaryDirectory(prefix='mcns-video-')
        self.video_path = None
        self.video_meta = None
        self.audio_track = None
        neurons = pd.read_feather(Path(graph)/"neurons.feather")
        manifest = json.loads((Path(graph)/"manifest.json").read_text())
        self.dashboard = Dashboard(neurons, sorted(neurons.population.unique()), port,
                                   self.control, manifest, self.import_video)
        self.dashboard.finish("idle")

    def control(self, body):
        with self.lock:
            if body["action"] == "stop":
                self.stop_event.set()
                self.dashboard.finish("stopping")
                return {"ok": True}
            if self.worker and self.worker.is_alive():
                raise ValueError("Simulation is already running or still stopping")
            source = body.get("source", "camera")
            if source not in ("camera", "video", "bar", "static", "white", "black"):
                raise ValueError("Invalid source")
            device = body.get("device", 0)
            if not isinstance(device, int) or not 0 <= device <= 10:
                raise ValueError("Invalid camera index")
            mirror, loop = body.get('mirror', True), body.get('video_loop', True)
            if not isinstance(mirror, bool) or not isinstance(loop, bool):
                raise ValueError('Invalid mirror/loop option')
            if source == 'video' and (not self.video_meta or body.get('video_id') != self.video_meta['id']):
                raise ValueError('Import a video before starting')
            self.stop_event = threading.Event()
            self.dashboard.reset()
            self.worker = threading.Thread(target=self._run, args=(source, device, mirror, loop), daemon=True)
            self.worker.start()
            return {"ok": True}

    def import_video(self, stream, length, name):
        with self.lock:
            if self.worker and self.worker.is_alive():
                raise ValueError('Stop the simulation before importing a video')
            name = Path(name).name[:200]
            suffix = Path(name).suffix.lower()
            if suffix not in ('.mp4', '.mov', '.m4v', '.avi', '.webm', '.mkv'):
                raise ValueError('Choose an MP4, MOV, M4V, AVI, WebM or MKV video')
            identity = uuid.uuid4().hex
            path = Path(self.video_directory.name)/(identity+suffix)
            try:
                remaining = length
                with path.open('wb') as target:
                    while remaining:
                        chunk = stream.read(min(1024*1024, remaining))
                        if not chunk:
                            raise ValueError('Video import was interrupted')
                        target.write(chunk)
                        remaining -= len(chunk)
                metadata = dict(inspect_video(path), id=identity, name=name)
                audio, audio_status = extract_audio(path, path.with_suffix('.wav'))
                metadata.update(has_audio=audio is not None, audio_status=audio_status)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            if self.video_path:
                self.video_path.unlink(missing_ok=True)
            if self.audio_track:
                self.audio_track.path.unlink(missing_ok=True)
            self.audio_track = audio
            self.video_path, self.video_meta = path, metadata
            with self.dashboard.lock:
                self.dashboard.video = metadata
                self.dashboard.audio_path = audio.path if audio else None
            return {'ok': True, 'video': metadata}

    def _run(self, source, device, mirror, loop):
        try:
            output = "runs/widget-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            run(self.graph, self.config, source, None, output, True, device, mirror,
                source in ('camera', 'video'), self.models, behavior=source in ('camera', 'video'),
                dashboard_instance=self.dashboard, stop_event=self.stop_event,
                video_path=self.video_path if source == 'video' else None, video_loop=loop,
                audio_track=self.audio_track if source == 'video' else None)
        except Exception as exc:
            self.dashboard.finish("error", str(exc))

    def close(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=10)
        self.dashboard.close()
        if not self.worker or not self.worker.is_alive():
            self.video_directory.cleanup()


def serve(graph, config, models, port):
    controller = Controller(graph, config, models, port)
    print("Open the widget and press Start. Ctrl-C stops the server.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
