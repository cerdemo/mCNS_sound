import csv
from contextlib import suppress
import json
import itertools
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
        track=False, models="models", dashboard_port=None, behavior=False,
        dashboard_instance=None, stop_event=None):
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
    embodied = config.get("embodiment", {}).get("enabled", False)
    if embodied:
        from .retina import BinocularInput
        from .readout import DescendingReadout
        mapper = BinocularInput(neurons, config["model"], config["embodiment"])
        descending = DescendingReadout(neurons)
        behavior = False
    else:
        mapper = ImageInput(neurons, config["model"])
    runtime = config["runtime"]
    populations = sorted(neurons.population.unique())
    group = pd.Categorical(neurons.population, categories=populations).codes
    sizes = np.bincount(group, minlength=len(populations))
    dt = engine.dt_ms / 1000
    frame_steps = max(1, round(1 / runtime["frame_hz"] / dt))
    osc_steps = max(1, round(1 / runtime["osc_hz"] / dt))
    pace_steps = max(1, round(.01 / dt))
    total_steps = round(duration / dt) if duration is not None else None
    original_weights = engine.weights
    zero_weights = sparse.csr_matrix(original_weights.shape, dtype=np.float32)
    output.mkdir(parents=True, exist_ok=True)
    run_info = {
        "application_version": __version__,
        "code_sha256": {p.name: sha256(p) for p in Path(__file__).parent.iterdir() if p.suffix in (".py", ".js", ".html")},
        "environment_lock_sha256": sha256("requirements.lock.txt") if Path("requirements.lock.txt").exists() else None,
        "config": config, "source": source, "duration_requested_seconds": duration,
        "realtime": realtime, "camera_device": device, "mirror": mirror,
        "tracking_enabled": track,
        "dashboard_port": dashboard_port,
        "behavior_enabled": behavior,
        "graph_manifest_sha256": sha256(graph / "manifest.json"),
        "populations": [{"index": i, "name": name, "neurons": int(sizes[i])}
                        for i, name in enumerate(populations)],
        "effective_frame_hz": 1 / (frame_steps * dt),
        "effective_osc_hz": 1 / (osc_steps * dt),
        "effective_delay_ms": engine.delay * engine.dt_ms,
        "effective_refractory_ms": engine.refractory * engine.dt_ms,
    }
    if track:
        run_info["tracking_model_sha256"] = {p.name: sha256(p) for p in Path(models).iterdir() if p.suffix in (".task", ".tflite")}
    (output / "run.json").write_text(json.dumps(run_info, indent=2) + "\n")
    camera = osc = tracker = tracking_stream = scene_tracker = scene_stream = None
    dashboard = dashboard_instance
    recurrent_enabled = True
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
    behavior_stream = widget_stream = None
    fly = None
    last_preview_seq = -1
    preview_stamp = None
    last_preview_time = -1.
    if behavior:
        if not track or source != "camera":
            raise ValueError("Behavior requires camera input and tracking")
        from .behavior import FlyBehavior
        fly = FlyBehavior(config["behavior"])
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
            if embodied:
                from .scene import SceneTracker
                scene_tracker = SceneTracker(camera, models, config["embodiment"].get("object_hz", 8))
                scene_stream = (output / "scene.jsonl").open("w")
            if track:
                from .tracking import Tracker
                tracker = Tracker(camera, models, preview=dashboard is not None)
                tracking_stream = (output / "tracking.jsonl").open("w")
        if fly:
            behavior_stream = (output / "behavior.jsonl").open("w")
        if dashboard:
            widget_stream = (output / "widget.jsonl").open("w")
        start = wall_origin = time.monotonic()
        osc.hello(populations, sizes)
        with (output / "activity.csv").open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["sequence", "simulation_s", "wall_s", "frame_age_ms", "rss_mb",
                             "skipped_clock_s", "input_spikes", "other_spikes"] +
                            [f"{name}_hz" for name in populations])
            for _ in range(total_steps) if total_steps is not None else itertools.count():
                if stop_event is not None and stop_event.is_set():
                    reason = "stopped"
                    break
                compute_start = time.monotonic()
                if engine.tick % frame_steps == 0:
                    pose = None
                    if embodied and dashboard:
                        _, pose_sample = dashboard.get_controls()
                        if pose_sample and time.monotonic()-pose_sample[0] < 1:
                            pose = pose_sample[1]
                    if camera:
                        seq, stamp, frame = camera.get()
                        frame_age = time.monotonic() - stamp
                        if frame_age > runtime["camera_stale_seconds"]:
                            raise RuntimeError("Stale camera image; stopping instead of replaying old input")
                        if seq != last_frame_seq:
                            overwritten += max(0, seq - last_frame_seq - 1)
                            last_frame_seq, frame_stamp = seq, stamp
                            gray = grayscale(frame)
                            current = mapper.current(gray, pose) if embodied else mapper.current(gray)
                            frames += 1
                            if dashboard and time.monotonic() - last_preview_time >= .1:
                                from .preview import encode_preview
                                dashboard.set_image("input", encode_preview((gray*255).astype(np.uint8)))
                                dashboard.set_image("scene", encode_preview(frame))
                                if not tracker:
                                    dashboard.set_image("camera", encode_preview(frame))
                                    preview_stamp = stamp
                                last_preview_time = time.monotonic()
                    else:
                        gray = stimulus(source, engine.tick * dt)
                        current = mapper.current(gray, pose) if embodied else mapper.current(gray)
                        frames += 1
                        if dashboard and time.monotonic()-last_preview_time >= .1:
                            from .preview import encode_preview
                            jpeg = encode_preview((gray*255).astype(np.uint8))
                            dashboard.set_image("scene", jpeg)
                            dashboard.set_image("input", jpeg)
                            last_preview_time = time.monotonic()
                    if embodied and dashboard and mapper.eyes:
                        from .preview import encode_preview
                        for side, eye in mapper.eyes.items():
                            dashboard.set_image("eye-"+side, encode_preview((eye*255).astype(np.uint8)))
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
                    fly_state = None
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
                            preview = tracker.get_preview()
                            if preview and preview[0] != last_preview_seq:
                                last_preview_seq, preview_stamp, jpeg = preview
                                dashboard.set_image("camera", jpeg)
                    if fly:
                        from .behavior import movement
                        fly_state = fly.update(window, movement(snapshot, now, config["behavior"]))
                        osc.send("/mcns/behavior", sequence, fly_state["state"], fly_state["motion"],
                                 int(fly_state["human_present"]), int(fly_state["tracking_valid"]))
                        osc.send("/mcns/flight", sequence, fly_state["gain"], fly_state["wing_hz"],
                                 fly_state["speed"], fly_state["x"], fly_state["y"])
                        behavior_stream.write(json.dumps({"simulation_s": sim_s, **fly_state}) + "\n")
                    scene_snapshot = scene_tracker.get() if scene_tracker else None
                    scene_state = scene_snapshot[2] if scene_snapshot and now-scene_snapshot[1] < .6 else None
                    if scene_stream and scene_snapshot:
                        scene_stream.write(json.dumps({"simulation_s": sim_s, "age_ms": (now-scene_snapshot[1])*1000,
                            "objects": scene_snapshot[2]["objects"]}) + "\n")
                    motor = descending.update(neuron_counts/window, window) if embodied else None
                    if motor:
                        osc.send("/mcns/descending", sequence, motor["escape_drive"], motor["turn_drive"], motor["landing_drive"])
                    if dashboard:
                        recurrent_enabled, widget = dashboard.get_controls()
                        engine.weights = original_weights if recurrent_enabled else zero_weights
                        widget_stream.write(json.dumps({"simulation_s": sim_s,
                            "recurrent_enabled_next_window": recurrent_enabled,
                            "motor": motor, "retina_pose": pose if embodied else None,
                            "widget": widget[1] if widget and now-widget[0] < 1 else None}) + "\n")
                        if widget and now-widget[0] < 1:
                            w = widget[1]
                            osc.send("/mcns/widget/flight", sequence, w["mode"], w["gain"],
                                     w["wing_hz"], w["speed"], w["x"], w["y"], w["activity"])
                        else:
                            osc.send("/mcns/widget/flight", sequence, "offline", 0., 0., 0., .5, .5, 0.)
                        neuron_rates = neuron_counts / window
                        dashboard.update(status="running", sequence=sequence, simulation_s=sim_s,
                            run_id=output.name, recurrent_enabled=recurrent_enabled,
                            embodied=embodied, motor=motor, scene=scene_state,
                            scene_age_ms=(now-scene_snapshot[1])*1000 if scene_snapshot else -1,
                            source=source, osc_target=f"{runtime['host']}:{runtime['port']}",
                            active_neurons=int((neuron_counts > 0).sum()),
                            mean_hz=float(neuron_rates.mean()),
                            input_mean_hz=float(neuron_rates[input_mask].mean()),
                            other_mean_hz=float(neuron_rates[~input_mask].mean()) if (~input_mask).any() else 0.,
                            population_hz=rates.tolist(), neuron_hz=neuron_rates.tolist(),
                            window_ms=window*1000, frame_age_ms=float(age_ms), rss_mb=float(rss),
                            behavior=fly_state, behavior_config=config["behavior"],
                            preview_available=preview_stamp is not None,
                            preview_age_ms=(now-preview_stamp)*1000 if preview_stamp is not None else -1,
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
                        if tracking_stream:
                            tracking_stream.flush()
                        if behavior_stream:
                            behavior_stream.flush()
                        if widget_stream:
                            widget_stream.flush()
                        if scene_stream:
                            scene_stream.flush()
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
        if osc:
            try:
                with suppress(OSError):
                    osc.send("/mcns/state", reason)
                    # Explicit final zero so a receiver need not latch the last activity.
                    osc.activity(sequence, engine.tick * dt, np.zeros(len(populations)),
                                 np.zeros(len(populations)))
                    if embodied:
                        osc.send("/mcns/descending", sequence, 0., 0., 0.)
                    if fly:
                        osc.send("/mcns/flight", sequence, 0., 0., 0., float(fly.position[0]), float(fly.position[1]))
                    if dashboard:
                        osc.send("/mcns/widget/flight", sequence, "offline", 0., 0., 0., .5, .5, 0.)
            finally:
                osc.close()
        if scene_tracker:
            scene_tracker.close()
        if scene_stream:
            scene_stream.close()
        if tracker:
            tracker.close()
        if tracking_stream:
            tracking_stream.close()
        if behavior_stream:
            behavior_stream.close()
        if widget_stream:
            widget_stream.close()
        if camera:
            camera.close()
        if dashboard and dashboard_instance is None:
            dashboard.close()
        elif dashboard:
            dashboard.finish(reason, failure)
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
        print(json.dumps(summary, indent=2), flush=True)
    return summary
