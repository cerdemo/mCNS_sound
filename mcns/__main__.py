import argparse
import json
import math
from datetime import datetime
from pathlib import Path

from .prepare import prepare
from .runtime import run


def load_config(path):
    config = json.loads(Path(path).read_text())
    for section, keys in {
        "model": ["dt_ms", "tau_membrane_ms", "tau_synapse_ms", "delay_ms"],
        "runtime": ["frame_hz", "osc_hz", "normalization_hz", "max_lag_seconds", "camera_stale_seconds"],
    }.items():
        for key in keys:
            if not math.isfinite(config[section][key]) or config[section][key] <= 0:
                raise ValueError(f"{section}.{key} must be finite and positive")
    for key in ["input_gain", "input_baseline", "synapse_gain", "refractory_ms"]:
        if not math.isfinite(config["model"][key]) or config["model"][key] < 0:
            raise ValueError(f"model.{key} must be finite and non-negative")
    s = config["selection"]
    if s["side"] not in ("L", "R") or s["radius"] < 1 or s["downstream_per_type"] < 0:
        raise ValueError("Invalid graph selection")
    return config


def main():
    parser = argparse.ArgumentParser(description="MaleCNS camera → LIF → OSC prototype")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("prepare", help="Extract and fingerprint a small real connectome circuit")
    build.add_argument("--data", default="data")
    build.add_argument("--graph", default="build/visual-v1")
    build.add_argument("--config", default="configs/default.json")
    live = sub.add_parser("run", help="Run controlled stimulus or live camera input")
    live.add_argument("--graph", default="build/visual-v1")
    live.add_argument("--config", default="configs/default.json")
    live.add_argument("--source", choices=["black", "gray", "white", "static", "bar", "camera"], default="bar")
    live.add_argument("--duration", type=float, default=60)
    live.add_argument("--output", default=None)
    live.add_argument("--fast", action="store_true", help="Run synthetic input without wall-clock pacing")
    live.add_argument("--device", type=int, default=0)
    live.add_argument("--mirror", action="store_true", help="Mirror camera horizontally (default: off)")
    live.add_argument("--track", action="store_true", help="Measure hand/face movement separately from neural input")
    live.add_argument("--models", default="models")
    live.add_argument("--dashboard", action="store_true", help="Serve live neuron maps at localhost:8765")
    live.add_argument("--dashboard-port", type=int, default=8765)
    live.add_argument("--host")
    live.add_argument("--port", type=int)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.command == "prepare":
        prepare(args.data, args.graph, config)
        return
    if not math.isfinite(args.duration) or args.duration <= 0:
        parser.error("--duration must be finite and positive")
    if args.fast and args.source == "camera":
        parser.error("--fast is only supported for synthetic stimuli")
    if args.track and args.source != "camera":
        parser.error("--track requires --source camera")
    if args.host:
        config["runtime"]["host"] = args.host
    if args.port is not None:
        config["runtime"]["port"] = args.port
    if not 1 <= config["runtime"]["port"] <= 65535:
        parser.error("OSC port must be in 1..65535")
    if not 1 <= args.dashboard_port <= 65535:
        parser.error("Dashboard port must be in 1..65535")
    output = args.output or ("runs/" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
    run(args.graph, config, args.source, args.duration, output, not args.fast, args.device,
        args.mirror, args.track, args.models, args.dashboard_port if args.dashboard else None)


if __name__ == "__main__":
    main()
