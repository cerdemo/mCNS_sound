"""Persistent browser widget host; camera/simulation lifecycle is controlled by the UI."""
import threading
from datetime import datetime
from pathlib import Path
import json

import pandas as pd

from .dashboard import Dashboard
from .runtime import run


class Controller:
    def __init__(self, graph, config, models, port):
        self.graph, self.config, self.models = graph, config, models
        self.lock = threading.Lock()
        self.worker = None
        self.stop_event = threading.Event()
        neurons = pd.read_feather(Path(graph)/"neurons.feather")
        manifest = json.loads((Path(graph)/"manifest.json").read_text())
        self.dashboard = Dashboard(neurons, sorted(neurons.population.unique()), port,
                                   self.control, manifest)
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
            if source not in ("camera", "bar", "static", "white", "black"):
                raise ValueError("Invalid source")
            device = body.get("device", 0)
            if not isinstance(device, int) or not 0 <= device <= 10:
                raise ValueError("Invalid camera index")
            self.stop_event = threading.Event()
            self.dashboard.reset()
            self.worker = threading.Thread(target=self._run, args=(source, device), daemon=True)
            self.worker.start()
            return {"ok": True}

    def _run(self, source, device):
        try:
            output = "runs/widget-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            run(self.graph, self.config, source, None, output, True, device, False,
                source == "camera", self.models, behavior=source == "camera",
                dashboard_instance=self.dashboard, stop_event=self.stop_event)
        except Exception as exc:
            self.dashboard.finish("error", str(exc))

    def close(self):
        self.stop_event.set()
        if self.worker:
            self.worker.join(timeout=10)
        self.dashboard.close()


def serve(graph, config, models, port):
    controller = Controller(graph, config, models, port)
    print("Open the widget and press Başlat. Ctrl-C stops the server.", flush=True)
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
    finally:
        controller.close()
