import csv
from contextlib import suppress
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import psutil
from scipy import sparse

from .model import LIF
from .osc import Output
from .prepare import sha256
from .vision import Camera, ImageInput, grayscale, stimulus
from . import __version__


def run(graph, config, source, duration, output, realtime=True, device=0, mirror=False,
        track=False, models="models", dashboard_port=None):
    graph, output = Path(graph), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Run output is not empty; choose a new --output directory")
    manifest = json.loads((graph / "manifest.json").read_text())
    if manifest["selection"] != config["selection"]:
        raise ValueError("Config selection differs from prepared graph; use matching config or rebuild")
    for name, digest in manifest["artifacts"].items():
        if sha256(graph / name) != digest:
            raise ValueError(f"Graph artifact changed: {name}. Rebuild into a new directory.")
    neurons = pd.read_feather(graph / "neurons.feather")
    engine = LIF(sparse.load_npz(graph / "weights.npz"), config["model"])
    mapper = ImageInput(neurons, config["model"])
    runtime = config["runtime"]
    populations = sorted(neurons.population.unique())
    group = pd.Categorical(neurons.population, categories=populations).codes
    sizes = np.bincount(group, minlength=len(populations))
    dt = engine.dt_ms / 1000
    frame_steps = max(1, round(1 / runtime["frame_hz"] / dt))
    osc_steps = max(1, round(1 / runtime["osc_hz"] / dt))
    pace_steps = max(1, round(.01 / dt))
    total_steps = round(duration / dt)
    output.mkdir(parents=True, exist_ok=True)
    run_info = {
        "application_version": __version__,
        "code_sha256": {p.name: sha256(p) for p in Path(__file__).parent.glob("*.py")},
        "environment_lock_sha256": sha256("requirements.lock.txt") if Path("requirements.lock.txt").exists() else None,
        "config": config, "source": source, "duration_requested_seconds": duration,
        "realtime": realtime, "camera_device": device, "mirror": mirror,
        "tracking_enabled": track,
        "dashboard_port": dashboard_port,
        "graph_manifest_sha256": sha256(graph / "manifest.json"),
        "populations": [{"index": i, "name": name, "neurons": int(sizes[i])}
                        for i, name in enumerate(populations)],
        "effective_frame_hz": 1 / (frame_steps * dt),
        "effective_osc_hz": 1 / (osc_steps * dt),
        "effective_delay_ms": engine.delay * engine.dt_ms,
        "effective_refractory_ms": engine.refractory * engine.dt_ms,
    }
    if track:
        run_info["tracking_model_sha256"] = {p.name: sha256(p) for p in Path(models).glob("*.task")}
    (output / "run.json").write_text(json.dumps(run_info, indent=2) + "\n")
    camera = osc = tracker = tracking_stream = dashboard = None
    process = psutil.Process()
    counts = np.zeros(len(populations), np.int64)
    neuron_counts = np.zeros(engine.n, np.int64)
    total_spikes = np.zeros(engine.n, np.int64)
    current = np.zeros(engine.n, np.float32)
    frames = overwritten = last_frame_seq = sequence = 0
    frame_age = 0.0
    frame_stamp = None
    skipped_clock = max_lag = max_compute = 0.0
    max_rss = start_rss = process.memory_info().rss / 1024**2
    start = time.monotonic()
    wall_origin = start
    last_sent_tick = 0
    reason = "completed"
    failure = None
    last_tracking_seq = -1
    tracking_samples = 0
    input_mask = neurons.is_input.to_numpy()
    print(f"{engine.n} neurons / {len(populations)} populations → "
          f"OSC {runtime['host']}:{runtime['port']} ({source})", flush=True)
    try:
        osc = Output(runtime["host"], runtime["port"])
        if dashboard_port is not None:
            from .dashboard import Dashboard
            dashboard = Dashboard(neurons, populations, dashboard_port)
        if source == "camera":
            camera = Camera(device, mirror)
            # Do not advance the network until the first real image is available.
            deadline = time.monotonic() + 5
            while camera.get() is None:
                if time.monotonic() >= deadline:
                    raise RuntimeError("No camera frame within five seconds")
                time.sleep(.01)
            if track:
                from .tracking import Tracker
                tracker = Tracker(camera, models)
                tracking_stream = (output / "tracking.jsonl").open("w")
        start = wall_origin = time.monotonic()
        osc.hello(populations, sizes)
        with (output / "activity.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["sequence", "simulation_s", "wall_s", "frame_age_ms", "rss_mb",
                             "skipped_clock_s", "input_spikes", "other_spikes"] +
                            [f"{name}_hz" for name in populations])
            for _ in range(total_steps):
                compute_start = time.monotonic()
                if engine.tick % frame_steps == 0:
                    if camera:
                        seq, stamp, frame = camera.get()
                        frame_age = time.monotonic() - stamp
                        if frame_age > runtime["camera_stale_seconds"]:
                            raise RuntimeError("Stale camera image; stopping instead of replaying old input")
                        if seq != last_frame_seq:
                            overwritten += max(0, seq - last_frame_seq - 1)
                            last_frame_seq, frame_stamp = seq, stamp
                            current = mapper.current(grayscale(frame))
                            frames += 1
                    else:
                        current = mapper.current(stimulus(source, engine.tick * dt))
                        frames += 1
                spiked = engine.step(current)
                total_spikes += spiked
                neuron_counts += spiked
                counts += np.bincount(group[spiked], minlength=len(populations))
                max_compute = max(max_compute, time.monotonic() - compute_start)
                if engine.tick % osc_steps == 0 or engine.tick == total_steps:
                    window = (engine.tick - last_sent_tick) * dt
                    rates = counts / sizes / window
                    normalized = np.clip(rates / runtime["normalization_hz"], 0, 1)
                    now = time.monotonic()
                    age_ms = (now - frame_stamp) * 1000 if frame_stamp is not None else 0
                    rss = process.memory_info().rss / 1024**2
                    max_rss = max(max_rss, rss)
                    sim_s = engine.tick * dt
                    osc.activity(sequence, sim_s, rates, normalized)
                    snapshot = None
                    if tracker:
                        from .tracking import send_tracking
                        snapshot = tracker.get()
                        send_tracking(osc, snapshot, now)
                        if snapshot is not None and snapshot[0] != last_tracking_seq:
                            tracking_stream.write(json.dumps({"frame": snapshot[0],
                                "capture_wall_s": snapshot[1] - start,
                                "features": snapshot[2]}) + "\n")
                            last_tracking_seq = snapshot[0]
                            tracking_samples += 1
                    if dashboard:
                        neuron_rates = neuron_counts / window
                        dashboard.update(status="running", sequence=sequence, simulation_s=sim_s,
                            source=source, osc_target=f"{runtime['host']}:{runtime['port']}",
                            active_neurons=int((neuron_counts > 0).sum()),
                            mean_hz=float(neuron_rates.mean()),
                            input_mean_hz=float(neuron_rates[input_mask].mean()),
                            other_mean_hz=float(neuron_rates[~input_mask].mean()) if (~input_mask).any() else 0.,
                            population_hz=rates.tolist(), neuron_hz=neuron_rates.tolist(),
                            window_ms=window*1000, frame_age_ms=float(age_ms), rss_mb=float(rss),
                            tracking_enabled=track, tracking=snapshot[2] if snapshot else None,
                            tracking_age_ms=(now-snapshot[1])*1000 if snapshot else -1)
                    osc.send("/mcns/health", sequence, sim_s, now - start, float(age_ms),
                             float(rss), float(skipped_clock), overwritten)
                    writer.writerow([sequence, sim_s, now-start, age_ms, rss, skipped_clock,
                                     int(total_spikes[input_mask].sum()),
                                     int(total_spikes[~input_mask].sum())] + rates.tolist())
                    counts.fill(0)
                    neuron_counts.fill(0)
                    last_sent_tick = engine.tick
                    if sequence % max(1, round(runtime["osc_hz"])) == 0:
                        osc.hello(populations, sizes)
                        stream.flush()
                    if sequence % max(1, round(runtime["osc_hz"] * 5)) == 0:
                        print(f"sim={sim_s:.1f}s wall={now-start:.1f}s "
                              f"mean={rates.mean():.2f}Hz rss={rss:.0f}MB "
                              f"clock-slip={skipped_clock:.3f}s", flush=True)
                    sequence += 1
                if realtime and (engine.tick % pace_steps == 0 or engine.tick == total_steps):
                    deadline = wall_origin + engine.tick * dt
                    lag = time.monotonic() - deadline
                    max_lag = max(max_lag, lag)
                    if lag > runtime["max_lag_seconds"]:
                        # Slow the simulation clock; never reset neural state or replay a frame queue.
                        skipped_clock += lag
                        wall_origin += lag
                    elif lag < 0:
                        time.sleep(-lag)
    except KeyboardInterrupt:
        reason = "interrupted"
    except Exception as exc:
        reason, failure = "error", str(exc)
        raise
    finally:
        wall_seconds = time.monotonic() - start
        if tracker:
            tracker.close()
        if tracking_stream:
            tracking_stream.close()
        if camera:
            camera.close()
        if dashboard:
            dashboard.close()
        summary = {
            "status": reason, "error": failure, "simulation_seconds": engine.tick * dt,
            "wall_seconds": wall_seconds, "osc_windows": sequence, "frames_used": frames,
            "tracking_samples": tracking_samples,
            "camera_frames_overwritten": overwritten, "max_clock_lag_seconds": max_lag,
            "skipped_wall_clock_seconds": skipped_clock,
            "max_single_step_compute_ms": max_compute * 1000,
            "start_rss_mb": start_rss, "peak_sampled_rss_mb": max_rss,
            "end_rss_mb": process.memory_info().rss / 1024**2,
            "total_spikes": int(total_spikes.sum()),
            "input_spikes": int(total_spikes[input_mask].sum()),
            "non_input_spikes": int(total_spikes[~input_mask].sum()),
            "silent_neuron_fraction": float(np.mean(total_spikes == 0)),
            "max_neuron_mean_hz": float(total_spikes.max() / max(engine.tick * dt, dt)),
        }
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        if osc:
            try:
                with suppress(OSError):
                    osc.send("/mcns/state", reason)
                    # Explicit final zero so a receiver need not latch the last activity.
                    osc.activity(sequence, engine.tick * dt, np.zeros(len(populations)),
                                 np.zeros(len(populations)))
            finally:
                osc.close()
        print(json.dumps(summary, indent=2), flush=True)
    return summary
