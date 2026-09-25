"""Local widget control and live view; holds only the newest activity snapshot."""
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np


class Dashboard:
    def __init__(self, neurons, populations, port=8765, on_control=None, manifest=None):
        self.lock = threading.Lock()
        self.state = {"status": "starting", "sequence": -1}
        self.images = {}
        self.widget = None
        self.recurrent_enabled = True
        self.on_control = on_control
        self.html = Path(__file__).with_name("dashboard.html").read_bytes()
        records = []
        for row in neurons.itertuples():
            soma = row.somaLocation
            coords = [float(v) for v in soma] if soma is not None else None
            if coords is not None and (len(coords) != 3 or not np.isfinite(coords).all()):
                coords = None
            hex_coords = [row.assignedOlHex1, row.assignedOlHex2]
            records.append({"id": str(row.bodyId), "population": row.population,
                            "input": bool(row.is_input), "soma": coords,
                            "type": row.type if hasattr(row,"type") else row.population,
                            "side": row.somaSide if hasattr(row,"somaSide") and isinstance(row.somaSide,str) else "unknown",
                            "hex": list(map(float, hex_coords)) if np.isfinite(hex_coords).all() else None})
        self.meta = json.dumps({"neurons": records, "populations": list(populations),
                               "dataset": "male-cns:v1.0", "manifest": manifest or {}}, allow_nan=False).encode()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/":
                    content, content_type = owner.html, "text/html; charset=utf-8"
                elif path in ("/widget-core.js", "/widget-ui.js"):
                    content = Path(__file__).with_name(path[1:]).read_bytes()
                    content_type = "application/javascript; charset=utf-8"
                elif path == "/api/meta":
                    content, content_type = owner.meta, "application/json"
                elif path == "/api/state":
                    with owner.lock:
                        content = json.dumps(owner.state, allow_nan=False).encode()
                    content_type = "application/json"
                elif path in ("/api/camera.jpg", "/api/input.jpg", "/api/scene.jpg", "/api/eye-L.jpg", "/api/eye-R.jpg"):
                    with owner.lock:
                        content = owner.images.get(path)
                    if content is None:
                        self.send_response(204)
                        self.end_headers()
                        return
                    content_type = "image/jpeg"
                else:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (BrokenPipeError, ConnectionResetError):
                    pass

            def do_POST(self):
                # JSON + same-origin checks prevent third-party pages from starting a camera.
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    self.send_error(415); return
                origin = self.headers.get("Origin")
                host = self.headers.get("Host")
                if host not in (f"127.0.0.1:{owner.server.server_port}", f"localhost:{owner.server.server_port}"):
                    self.send_error(403); return
                if origin and origin != f"http://{host}":
                    self.send_error(403); return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if not 0 < length <= 8192:
                        raise ValueError("Invalid request size")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError("Expected a JSON object")
                    if self.path == "/api/widget":
                        fields = ("x", "y", "vx", "vy", "gain", "wing_hz", "speed", "activity")
                        body["angle"] = body.get("angle", 0.)
                        if not isinstance(body["angle"], (int,float)) or not math.isfinite(body["angle"]):
                            raise ValueError("Invalid heading")
                        if body.get("mode") not in ("flying", "walking", "escaping", "hidden", "offline"):
                            raise ValueError("Invalid widget mode")
                        if any(not isinstance(body.get(k), (int,float)) or not math.isfinite(body[k]) for k in fields):
                            raise ValueError("Non-finite widget value")
                        if any(not 0 <= body[k] <= 1 for k in ("x","y","gain","activity")):
                            raise ValueError("Widget value outside 0..1")
                        if not 0 <= body["wing_hz"] <= 1000 or not 0 <= body["speed"] <= 10:
                            raise ValueError("Invalid flight parameters")
                        with owner.lock:
                            if body.get("run_id") != owner.state.get("run_id"):
                                raise ValueError("Widget belongs to a different run")
                            owner.widget = (time.monotonic(), {k: body[k] for k in fields + ("mode", "angle")})
                        result = {"ok": True}
                    elif self.path == "/api/control":
                        action = body.get("action")
                        if action == "recurrence" and isinstance(body.get("enabled"), bool):
                            with owner.lock:
                                owner.recurrent_enabled = body["enabled"]
                            result = {"ok": True, "enabled": body["enabled"]}
                        elif owner.on_control and action in ("start", "stop"):
                            result = owner.on_control(body)
                        else:
                            raise ValueError("Control is unavailable")
                    else:
                        self.send_error(404); return
                    content = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                except (ValueError, TypeError) as exc:
                    self.send_error(400, str(exc))

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        print(f"Live view: {self.url}", flush=True)

    def update(self, **state):
        with self.lock:
            self.state = state

    def set_image(self, name, jpeg):
        with self.lock:
            self.images[f"/api/{name}.jpg"] = jpeg

    def get_controls(self):
        with self.lock:
            return self.recurrent_enabled, self.widget

    def finish(self, status, error=None):
        with self.lock:
            self.state = {**self.state, "status": status, "error": error}

    def reset(self):
        with self.lock:
            self.state = {"status": "starting", "sequence": -1}
            self.widget = None
            self.images.clear()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
