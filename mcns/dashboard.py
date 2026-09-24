"""Local read-only live view; holds only the newest activity snapshot."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np


class Dashboard:
    def __init__(self, neurons, populations, port=8765):
        self.lock = threading.Lock()
        self.state = {"status": "starting", "sequence": -1}
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
                            "hex": list(map(float, hex_coords)) if np.isfinite(hex_coords).all() else None})
        self.meta = json.dumps({"neurons": records, "populations": list(populations),
                               "dataset": "male-cns:v1.0"}, allow_nan=False).encode()
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                path = self.path.split("?", 1)[0]
                if path == "/":
                    content, content_type = owner.html, "text/html; charset=utf-8"
                elif path == "/api/meta":
                    content, content_type = owner.meta, "application/json"
                elif path == "/api/state":
                    with owner.lock:
                        content = json.dumps(owner.state, allow_nan=False).encode()
                    content_type = "application/json"
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

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
