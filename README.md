# MaleCNS browser widget → sound + OSC

Camera or controlled image → continuous LIF simulation on MaleCNS connections → OSC.
The Max/MSP patch is outside this project's scope. The default target is `127.0.0.1:9000`.

## Binocular browser widget (default)

```sh
source .mcns/bin/activate
python -m mcns serve
```

[Open the widget](http://127.0.0.1:8765), then use **Start** and **Turn sound on**.
The default graph is `build/bilateral-v1`, config `configs/bilateral.json`.
The camera index and the controlled image source are chosen in the browser. Stop closes the camera and
the simulation; the server stays up. Ctrl-C in the terminal shuts the server down.
OSC continues to `127.0.0.1:9000`. Camera frames are not sent out or saved to disk.

### Simulation assumptions versus the real circuit

**8,440 real cells, 278,080 anatomical connections** (277,784 signed connections with a nonzero effect).
The left and right optic columns, a T4/T5 sample, LC4/LPLC2, selected DN cells, and their
two-layer real upstream partners are simulated together. No mirrored or synthetic neurons are added.
The circuit is not the full CNS; graph selection and severed connections are recorded in `manifest.json`.

- The fly's position and heading in the browser are sent back to Python. The camera image is sampled,
  from that pose, into two **local, planar virtual-eye** images. There is no artificial blind gap in the middle;
  the frontal views overlap. A single camera cannot provide stereo or 360° imagery. Heading, scale, and
  eye projection are not calibrated; this does not claim to be real compound-eye optics.
- Input is delivered only to real left/right **L1/L2** cells. Photoreceptors and
  receptor/physiology detail are not modeled yet. Some cell types on the left lack
  column annotations; the right-side map is not copied over as the left.
- Smoothed activity of DNp01/02/04/11 above baseline is mapped to the acceleration/takeoff
  readout; the right-minus-left activity difference of DNa02 is mapped to turning. DNp07/10 activity is measured
  and is not yet used in landing control. This output mapping is not a biological motor-muscle simulation.
- The rules **a person moves → flee** and **wait three seconds → come back out** are absent in this version.
  A small baseline exploration speed, heading noise, screen bounds, and object contact are still modeled physics
  assumptions. The `escaping` widget OSC mode means experimental DN acceleration; it is not validated fear.
- Landing is a geometric encounter with the top edge of a detected object's box. The fly is carried
  with the box and walks. The box is not a 3D surface or a segmentation mask; false detections
  and perspective can produce landing in mid-air. When the object disappears, the fly takes off.
- Mean column activity outside the input affects speed and timbre; the flight sound is silent while walking.
  Sound is synthesized in the browser with a harmonic oscillator, a filter, frequency modulation, and stereo pan.
- **A/B: disconnect wiring** zeros the real synaptic matrix; the same camera input and
  L1/L2 drive remain. Synaptic state decays naturally. Baseline exploration physics continues.

### Objects and multiple people

Local **MediaPipe EfficientDet-Lite0** detects objects (COCO classes, threshold 0.4, at most 20 boxes,
target 8 Hz). Each person is tracked as a separate `person #id`. Assignment uses class and a motion-estimated
position; this is not identity recognition. IDs can change on occlusion or intersection, or after a 0.8 s loss.
MediaPipe also returns at most 4 faces and 6 hands; the legacy OSC hand/face channels
keep one summary each for compatibility, and `tracking.jsonl` contains the extra face and hand lists.

**Show objects and heading** turns the boxes on; the real input to the two eyes appears just below.
Object classes and person labels are not injected into the neural network. Object boxes go to contact physics;
pixels go to visual neural input. Dense optical flow is also measured and is not a fear trigger.
Use a single active widget tab. If browser telemetry is older than 1 second, the widget OSC sound is zeroed.
In a background tab the local sound goes silent; the sound button and level do not change the OSC behavior gain.

### Validation result and open limits

`python scripts/validate_bilateral.py` compares stationary, approaching, receding, and horizontally moving
controlled stimuli from the same pose; a disconnected control also runs.
The result is in `build/bilateral-v1/validation.json`. With the current uniform LIF, **looming
selectivity was not validated**: the DN response to a receding stimulus was larger than to an approaching one.
In the disconnected network the DN response is zero. That supports a connectional cause; it is not evidence of
natural escape or biological accuracy. The UI keeps this limit visible.

Next scientific requirements: cell-type-specific temporal and graded dynamics, input
polarity and adaptation, retinotopic calibration, an audit of missing upstream pathways, and
selectivity checks on stationary, translating, approaching, and receding stimuli. Increasing the real connection
count is not assumed to solve these automatically.

On a fresh install:

```sh
python scripts/download_models.py
python -m mcns prepare --config configs/bilateral.json --graph build/bilateral-v1
```

If the existing graph directory is already populated it is not overwritten; choose another `--graph` path.
To compare the older behavioral prototype:
`python -m mcns serve --graph build/visual-v1 --config configs/default.json`.

Widget OSC: `/mcns/widget/flight sequence:int mode:string gain:float wing_hz:float speed:float x:float y:float activity:float`.
DN OSC: `/mcns/descending sequence:int escape_drive:float turn_drive:float landing_drive:float`.
`escape_drive` and `landing_drive` are 0..1, `turn_drive` is −1..1; these are explicit decoder parameters.
The legacy `/mcns/flight` address is sent only in the older `--behavior` version. The population count is now
682; a Max mapping should follow the `/mcns/population` metadata.

## Timed runs from the command line

Run commands in the project folder. The existing `.mcns` environment is already set up.

```sh
source .mcns/bin/activate
python -m mcns run --source bar --duration 60
```

With camera, hand, and head tracking:

```sh
python -m mcns run --source camera --track --duration 600
```

To also open the live neural activity map:

```sh
python -m mcns run --source camera --behavior --dashboard --duration 600
```

Open [127.0.0.1:8765](http://127.0.0.1:8765) in the browser. The page is bound to the local computer
and is not published outward. Change the port with `--dashboard-port 8766`.
To try it without a camera, use `--source bar --dashboard`.

The fixed counts below belong to the older `visual-v1` graph; the new graph uses UI metadata.

- **Anatomical soma positions:** XY, XZ, and YZ projections of the 862 cells that have a position in the annotation.
- **Visual columns:** mean activity of the 915 cells with assigned coordinates, across 61 columns.
- **Population bars:** all 1,107 cells, including those without a position annotation.
- **Time plot:** separate mean firing rates of input cells and the other cells.

There is a cell-type filter, an Hz color scale, and cell details. Color is the spikes per neuron per second
in the latest OSC window. For a single cell, one spike in a 50 ms window
is 20 Hz; flicker in the display is expected. In the column view, overlapping
cells are averaged. Missing column positions for T4/T5 are not invented.
This view is not a neuropil or ROI activity map of the whole brain. A soma is a cell's
body; it does not show the region where its synapses lie. Showing regional synapse activity
requires additional ROI or synapse location data.

Freezing the view affects only the browser. When `run --dashboard` exits, the page
says "Connection lost" and keeps the last image. The `serve` server stays up and can be started again.
The server keeps the newest measurement; the browser stores only the last 20 seconds. The camera preview
and the 128×128 neural input image are streamed to the browser over localhost only.
Hand and face marks in the preview are drawn on the frame that was inferred; their ages are shown in the UI.
Images are not saved to disk.

## Older prototype: flight / escape / hide behavior (off in the binocular version)

`--behavior` also turns on hand and face tracking. This is the scene
behavior requested later; it is not a learned or emergent fear response of the network.
Neural connections and neural OSC values are unaffected by this layer.

- **flying:** in calm conditions the virtual 2D sound position wanders, and the flight-sound gain is 1.
- **escaping:** if hand or face motion stays above threshold for at least 0.1 s, the position
  is pulled in 0.6 s to the edge opposite the tracked person's horizontal position, and the gain fades.
- **hidden:** flight gain and the wing parameter become 0. New motion resets the calm counter.
- **recovering:** if motion stays low for 3 s, position and gain return over 1.5 s.
  If motion occurs again during that time, escape starts over.

The motion score is computed from the 2D speed of tracked hand and face centers; a stationary person
is not motion. Raw pixel difference is not used for camera or other object motion.
Speeds have a 0.025 image-unit/s deadband and 0.12 s smoothing. The start threshold
is 0.22 and the calm threshold is 0.10; all parameters are in `configs/default.json → behavior`.
Because the speed mapping depends on the camera field of view, it should be adjusted during setup.
This version does not separately classify approach, a closing hand, or an intent to catch.

Tracking data older than 0.5 s produces silence and holds the return from hiding.
Absence of a person in the current inference is treated as an empty scene; after calm, flight
can return. **No detection** and **stale or dropped data** are separate states.

The virtual position is an acoustic design parameter. It is not real 3D fly physics, a camera viewpoint,
or a human–fly distance. `wing_hz` is a sound-synthesis parameter chosen in the 190–230 Hz range
and should not be read as a measured biological wingbeat frequency.

Additional messages to Max:

- `/mcns/behavior`: `sequence:int state:string motion:float human_present:int tracking_valid:int`.
- `/mcns/flight`: `sequence:int gain:float wing_hz:float speed:float x:float y:float`.

`gain`, `speed`, `x`, and `y` are in 0–1; `gain=0` should mute the flight sound.
A starting mapping on the Max side: multiply the flight-sound amplitude by `gain`,
drive the buzz or periodic modulation rate with `wing_hz`, and control sound position with `x` and `y`.
Raw neural `/mcns/activity` values continue to modulate timbre and resonances.
Neural rates are not zeroed during hiding; the behavior layer provides a separate gate for the sound.

The first camera use may require a macOS camera permission. If access is denied, check the app that
runs the command under System Settings → Privacy & Security → Camera.
`--device 1` selects another camera; `--mirror` flips the image horizontally (off by default).
The image is not recorded; inference uses a local model. Only neural activity,
performance, behavior, and tracking features are kept on disk. The camera preview is on the dashboard.

The camera still drives the neural simulation without `--track`. The tracking channel does not change the neural input.
With `--behavior` off, the escape/hide rule does not run. No mode synthesizes sound in Python.

To see OSC packets without Max, in a **separate terminal**:

```sh
source .mcns/bin/activate
python scripts/osc_monitor.py
```

This receiver and Max should not use the same UDP port at the same time. Close the receiver, then open Max.
Do not send several simulations to the same target port at once.
A different target: `--host 127.0.0.1 --port 9001`. Ctrl-C stops it.

## Recreating the install

Full dependencies verified on Python 3.9 / Apple Silicon are in `requirements.lock.txt`.
Direct dependencies are in `requirements.txt`. `opencv-python` and
`opencv-contrib-python` are not installed together; this environment uses only the contrib package.

```sh
python3 -m venv .mcns
.mcns/bin/python -m pip install -r requirements.lock.txt
.mcns/bin/python scripts/download_models.py
.mcns/bin/python -m mcns prepare
```

The three Feather files named in the [project summary](MaleCNS_Sonification_Project_Summary.md) must be under `data/`. The prepared circuit
has been built under `build/visual-v1/`. `prepare` does not overwrite a populated output folder.
When changing the selection, copy the config and use a new output name:

```sh
python -m mcns prepare --config configs/default.json --graph build/visual-v2
python -m mcns run --graph build/visual-v2 --source bar
```

## Visual circuit and explicit assumptions

The default circuit is selected from cells in the right optic lobe with `status=Traced` and `superclass=ol_intrinsic`.
The column center is `(18,19)` and the radius is 4. The column region
is defined by `max(abs(dq), abs(dr), abs(dq-dr)) <= 4`.
All types with assigned coordinates in this region are taken, plus at most 24 cells from each T4/T5
subtype that receives the most synapses from here. Ties keep the smaller bodyId first.
All anatomical connections among the selected cells are kept; there is no thresholding or learning.

The current data has 61 columns, 1,107 neurons, 183 input cells, 16,700 connections, and 23 populations.
Connections that leave the scope are cut; their counts and synapse totals are in the manifest.
This cut changes the dynamics; results cannot be read as the behavior of the whole fly.

Grayscale image brightness is injected into L1, L2, and L3 cells. Photoreceptors are skipped;
this is not a physiological retina model. No extra ON/OFF, motion-detection,
or avoidance/capture rule is added for L1 and L2. Constant brightness also produces activity.
Motion selectivity is not biologically validated.

Column coordinates are mapped to the plane with `x=q-r/2`, `y=sqrt(3)*r/2` and scaled into the screen range
of the selected region. The orientation of this transform and the camera field of view are a design
assumption; they are not calibrated to the fly's eye geometry. The image is reduced to 128×128 gray
and bilinearly sampled onto the input cells.

From the neurotransmitter **consensus_nt** field, acetylcholine is taken as +1, and GABA, glutamate, and histamine as −1.
Other or uncertain labels produce a zero-effect output. This is a coarse assumption;
receptor-dependent signs and neuromodulation are not modeled. Individual prediction confidence,
gaps, and disagreements with consensus are reported separately. Low-confidence cells should not be
assumed to have been dropped silently.

`neurons.feather`: neuron identity, population, annotation and NT fields, input flag.
`edges.feather`: body_pre/body_post, matrix indices, and raw synapse count.
`weights.npz`: sparse matrix, **row = target, column = source**, NT-signed synapse count.
`manifest.json`: selection, missing data, severed connections, and source and output SHA-256 values.
The full connection table is scanned in parts; it is not loaded into memory as one piece.

## Dynamics and timing

Dimensionless LIF: rest/reset = 0, threshold = 1.

```text
dv/dt = (-v + I_image + g) / tau_m
dg/dt = -g / tau_s
when a delayed spike arrives: g_target += synapse_count × NT_sign × synapse_gain
I_image = 0.15 + 2.0 × brightness  (input cells only)
```

Defaults: `dt=1 ms`, `tau_m=20 ms`, `tau_s=5 ms`, refractory period 2 ms,
delay 2 ms, synapse gain 0.04. Within a step, analytic integration is used for a constant external drive and an exponential synaptic current.
In the refractory state, voltage is held at reset;
synaptic current keeps decaying and is not zeroed after a spike.
Delay and refractory duration are rounded to the nearest step count; the effective values are written to `run.json`.
This is not a one-to-one port of the Shiu model, and it is not a physiologically fitted model of MaleCNS.

The camera keeps a single newest frame. The model is not reset on every frame.
The image-update target is 30 Hz and OSC is 20 Hz; the rates realized after step rounding are in `run.json`.
Tracking runs on a separate thread and uses the newest frame. A camera
frame older than one second stops the run with an error. If computation lag exceeds 250 ms, simulation time
is slowed and the lost wall-clock time is reported; old frames are not queued.

## OSC contract for Max — version 1

OSC 1.0 UDP, default `127.0.0.1:9000`. Addresses and argument order:

- `/mcns/schema`: `version:int` (=1).
- `/mcns/population`: `index:int name:string neuron_count:int`.
- `/mcns/rates`: `sequence:int simulation_seconds:float rate0:float rate1:float ...`.
- `/mcns/activity`: `sequence:int simulation_seconds:float value0:float value1:float ...`.
- `/mcns/health`: `sequence:int simulation_seconds:float wall_seconds:float frame_age_ms:float rss_mb:float clock_slip_seconds:float overwritten_camera_frames:int`.
- `/mcns/state`: the text `completed`, `stopped`, `interrupted`, or `error`; sent on shutdown.

`rate`: spike count in the last OSC window / neuron count / window duration, in Hz per neuron.
`activity`: `clip(rate / 100, 0, 1)`; the 100 Hz scale changes with `normalization_hz` in the config.
Raw `rates` are not clipped. Population order is alphabetical. It is given in each run's `run.json`
and in `/mcns/population` messages repeated once per second.
Repeating the metadata lets a Max receiver that opens late learn the mapping.

Example: `/mcns/activity 42 2.15 0.0 0.03 ...`; the first two numbers are not channel activity.
On a normal shutdown, one final zero-activity packet is sent. UDP does not guarantee delivery.
A watchdog on the Max side that fades the sound after packets stop, for example after 500 ms, is recommended.
The population count can change when the graph or config changes; do not assume a fixed set of 23 channels.

If `--track` is on, extra measurement messages:

- `/mcns/tracking/hand`: `frame:int side:string present:int x:float y:float vx:float vy:float openness:float handedness_score:float age_ms:float`.
- `/mcns/tracking/face`: `frame:int present:int x:float y:float vx:float vy:float width:float age_ms:float`.

`x` and `y` are image coordinates (left and top are 0); `vx` and `vy` are image units per second.
Hand openness is the mean 2D distance of the fingertips from the wrist, divided by palm length.
It is not a calibrated grasp measure. Face width is a fraction of image width,
not a metric depth. `side` is the model's Left/Right label; check it together with the mirror setting
during setup. If two labels for the same side arrive, the higher-scoring one is kept.
When tracking is lost, `present=0` and the features become zero; on reappearance, velocity starts
from zero. A tracking result older than one second is also invalid. This channel is a separate observation
stream. For sound driven by neural activity, use `/mcns/activity`.

## Recording and tests

Each run produces a separate `runs/<timestamp>/` folder:

- `run.json`: full config, identity of the graph used, population order, and effective timing.
- `activity.csv`: raw population rates, memory, and timing measurements in each OSC window.
- `tracking.jsonl`: motion features of processed frames when tracking is on; contains no images.
- `behavior.jsonl`: state, motion, gain, and flight parameters in each OSC window when behavior is on.
- `scene.jsonl`: object and person boxes, temporary IDs, and measurement age; contains no images.
- `widget.jsonl`: browser flight state during OSC windows while the widget or map is open, and the connection A/B flag to apply on the next window.
- `summary.json`: completion or error status, spike totals, silent-cell fraction, and performance.

```sh
python -m unittest discover -s tests -v
node tests/test_widget.js
python -m mcns run --source black --duration 5 --fast
python -m mcns run --source white --duration 5 --fast
python -m mcns run --source static --duration 5 --fast
python -m mcns run --source bar --duration 600
```

`--fast` is used only for controlled stimuli and does not count as a real-time test.
Memory RSS samples cover the whole Python process. `frame_age_ms` measures age from the moment OpenCV
delivers the frame until the OSC publish. It is not end-to-end latency through the sensor, Max, and the sound card.
Hearing the Max patch is the user's check; browser synthesis can be heard inside the widget.

## Sources

25 September steering study: [circuit coverage, experimental physiology, and test results](STEERING_AUDIT.md).
A 14,206-cell research circuit and a hybrid model were added. Direction-selectivity tests
failed, so they were not switched in as the live widget's default model.

- [MaleCNS data and license (CC-BY)](https://male-cns.janelia.org/download/).
- [Definition of optic-column coordinates](https://github.com/reiserlab/male-drosophila-visual-system-connectome-code/blob/main/docs/coordinate-systems.md).
- [Reference code for the Shiu model](https://github.com/philshiu/Drosophila_brain_model/blob/main/model.py).
- [MediaPipe hand tracking](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/python) and [face tracking](https://developers.google.com/edge/mediapipe/solutions/vision/face_landmarker/python).

### Binocular circuit and detection sources

- [LC4/DN escape-direction study](https://www.nature.com/articles/s41586-022-05562-8).
- [LPLC2 looming selectivity](https://www.nature.com/articles/nature24626).
- [Eye geometry and visual overlap](https://www.nature.com/articles/s41586-025-09276-5).
- [DN functions: comparative connectomics](https://www.nature.com/articles/s41586-025-08925-z).
- [MediaPipe object detection](https://developers.google.com/edge/mediapipe/solutions/vision/object_detector).
