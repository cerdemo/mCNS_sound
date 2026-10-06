"""Local widget control and live view; holds only the newest activity snapshot."""
import json
import math
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import numpy as np
from .sensors import validate_probes


class Dashboard:
    def __init__(self, neurons, populations, port=8765, on_control=None, manifest=None, on_upload=None):
        self.lock = threading.Lock()
        self.state = {"status": "starting", "sequence": -1}
        self.images = {}
        self.widget = None
        self.recurrent_enabled = True
        self.on_control = on_control
        self.on_upload = on_upload
        self.video = None
        self.audio_path = None
        self.audio_sample = None
        self.html = Path(__file__).with_name("dashboard.html").read_bytes()
        records = []
        for row in neurons.itertuples():
            soma = row.somaLocation
            coords = [float(v) for v in soma] if soma is not None else None
            if coords is not None and (len(coords) != 3 or not np.isfinite(coords).all()):
                coords = None
            hex_coords = [row.assignedOlHex1, row.assignedOlHex2]
            records.append({"id": str(row.bodyId), "population": row.population,
                            "input": bool(row.is_input), "auditory_input": bool(getattr(row, "is_auditory_input", False)), "soma": coords,
                            "superclass": getattr(row, 'superclass', 'unknown'),
                            "type": row.type if hasattr(row,"type") else row.population,
                            "side": row.somaSide if hasattr(row,"somaSide") and isinstance(row.somaSide,str) else "unknown",
                            "hex": list(map(float, hex_coords)) if np.isfinite(hex_coords).all() else None})
        self.meta = json.dumps({"neurons": records, "populations": list(populations),
                               "dataset": "male-cns:v1.0", "manifest": manifest or {}}, allow_nan=False).encode()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path.startswith('/api/video-audio/'):
                    with owner.lock:
                        valid = owner.video and path == '/api/video-audio/'+owner.video['id']+'.wav'
                        audio_path = owner.audio_path if valid else None
                        try:
                            stream = audio_path.open('rb') if audio_path else None
                        except OSError:
                            stream = None
                    if stream is None:
                        self.send_error(404); return
                    with stream:
                        import os
                        size = os.fstat(stream.fileno()).st_size
                        start, end = 0, size-1
                        partial = self.headers.get('Range')
                        if partial:
                            try:
                                unit, span = partial.split('=')
                                left, right = span.split('-')
                                if unit != 'bytes' or (not left and not right):
                                    raise ValueError()
                                start = int(left) if left else max(0, size-int(right))
                                end = min(size-1, int(right)) if left and right else size-1
                                if start < 0 or start > end:
                                    raise ValueError()
                            except ValueError:
                                self.send_response(416)
                                self.send_header('Content-Range', f'bytes */{size}')
                                self.end_headers(); return
                        self.send_response(206 if partial else 200)
                        self.send_header('Content-Type', 'audio/wav')
                        self.send_header('Accept-Ranges', 'bytes')
                        self.send_header('Cache-Control', 'no-store')
                        self.send_header('Content-Length', str(end-start+1))
                        if partial:
                            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
                        self.end_headers()
                        stream.seek(start)
                        remaining = end-start+1
                        try:
                            while remaining:
                                chunk = stream.read(min(65536, remaining))
                                if not chunk:
                                    break
                                self.wfile.write(chunk); remaining -= len(chunk)
                        except (BrokenPipeError, ConnectionResetError):
                            pass
                    return
                if path == "/":
                    content, content_type = owner.html, "text/html; charset=utf-8"
                elif path in ("/widget-core.js", "/widget-ui.js", "/source-audio.js"):
                    content = Path(__file__).with_name(path[1:]).read_bytes()
                    content_type = "application/javascript; charset=utf-8"
                elif path == "/api/meta":
                    content, content_type = owner.meta, "application/json"
                elif path == '/api/video':
                    with owner.lock:
                        content = json.dumps({'video': owner.video}, allow_nan=False).encode()
                    content_type = 'application/json'
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
                # Same-origin checks cover both camera control and local video import.
                origin = self.headers.get("Origin")
                host = self.headers.get("Host")
                if host not in (f"127.0.0.1:{owner.server.server_port}", f"localhost:{owner.server.server_port}"):
                    self.send_error(403); return
                if origin and origin != f"http://{host}":
                    self.send_error(403); return
                content_type = self.headers.get('Content-Type', '').split(';')[0]
                if urlsplit(self.path).path == '/api/video':
                    if content_type != 'application/octet-stream':
                        self.send_error(415); return
                    try:
                        length = int(self.headers.get('Content-Length', 0))
                        if not 0 < length <= 1024**3:
                            raise ValueError('Video size must be between 1 byte and 1 GB')
                        if owner.on_upload is None:
                            raise ValueError('Video import is unavailable')
                        name = parse_qs(urlsplit(self.path).query).get('name', [''])[0]
                        self.connection.settimeout(60)
                        result = owner.on_upload(self.rfile, length, name)
                        self.json_response(result)
                    except (ValueError, TypeError, OSError) as exc:
                        self.send_error(400, str(exc))
                    return
                if content_type != 'application/json':
                    self.send_error(415); return
                try:
                    length = int(self.headers.get("Content-Length", 0))
                    if not 0 < length <= 8192:
                        raise ValueError("Invalid request size")
                    body = json.loads(self.rfile.read(length))
                    if not isinstance(body, dict):
                        raise ValueError("Expected a JSON object")
                    if self.path == '/api/audio':
                        rms = body.get('rms')
                        if isinstance(rms, bool) or not isinstance(rms, (int, float)) or not math.isfinite(rms) or not 0 <= rms <= 1:
                            raise ValueError('Invalid audio envelope')
                        with owner.lock:
                            if owner.state.get('status') != 'running' or owner.state.get('source') != 'camera' or body.get('run_id') != owner.state.get('run_id'):
                                raise ValueError('Audio belongs to a different source/run')
                            owner.audio_sample = (time.monotonic(), float(rms))
                        result = {'ok': True}
                    elif self.path == "/api/widget":
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
                        probes, sample_time = validate_probes(body)
                        with owner.lock:
                            if body.get("run_id") != owner.state.get("run_id"):
                                raise ValueError("Widget belongs to a different run")
                            if probes and owner.widget and sample_time <= owner.widget[1].get('sample_time', -1):
                                raise ValueError('Out-of-order probe sample')
                            owner.widget = (time.monotonic(), {
                                **{k: body[k] for k in fields + ("mode", "angle")},
                                'probes': probes, 'sample_time': sample_time})
                        result = {"ok": True}
                    elif self.path == "/api/control":
                        action = body.get("action")
                        if action == "recurrence" and isinstance(body.get("enabled"), bool):
                            with owner.lock:
                                owner.recurrent_enabled = body["enabled"]
                                owner.state['recurrent_enabled'] = body['enabled']
                            result = {"ok": True, "enabled": body["enabled"]}
                        elif owner.on_control and action in ("start", "stop"):
                            result = owner.on_control(body)
                        else:
                            raise ValueError("Control is unavailable")
                    else:
                        self.send_error(404); return
                    self.json_response(result)
                except (ValueError, TypeError) as exc:
                    self.send_error(400, str(exc))

            def json_response(self, result):
                content = json.dumps(result, allow_nan=False).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)

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

    def get_audio(self):
        with self.lock:
            return self.audio_sample

    def finish(self, status, error=None):
        with self.lock:
            self.state = {**self.state, "status": status, "error": error}

    def reset(self):
        with self.lock:
            self.state = {"status": "starting", "sequence": -1}
            self.widget = None
            self.audio_sample = None
            self.images.clear()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
