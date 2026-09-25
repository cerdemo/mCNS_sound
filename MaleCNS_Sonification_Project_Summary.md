# Interactive sound installation based on MaleCNS

## Idea

We want to sonify the activity that movements seen by the camera produce in a neural model running on the fly's biological wiring map (the connectome). When a visitor hears the sound and changes their movement, a new visual input is formed, so a closed interaction loop is set up between the person and the system.

**Flow:** camera → visual input passed to neurons → continuous neural simulation → sonification of the activity → the visitor's next movement.

The aim is not to teach ready-made responses to particular gestures. We want to start from the biological connections and listen to the response the chosen neural dynamics give to the surroundings. The first version does not plan model training or learning that changes the connections. Even with fixed connections, the network's internal state can change over time; a closed loop by itself is not learning.

## The three files we will download

The files are on the [MaleCNS download page](https://male-cns.janelia.org/download/); they are not part of the navis repository.

| File | What we will use it for |
| --- | --- |
| `body-annotations-male-cns-v1.0-minconf-0.5.feather` | Cell types, classes, and side labels. |
| `body-neurotransmitters-male-cns-v1.0.feather` | Neurotransmitter predictions, as assumptions for the model. |
| `connectome-weights-male-cns-v1.0-minconf-0.5.feather` | Which segment connects to which, and at what weight. |

These files are anatomical starting data; they do not make a ready-to-run simulator. Mapping the camera onto visual cells may need extra annotation or another source.

## After the files are downloaded

### 1. Read the data and prepare the connection network

We will open the files in Python with `pandas` and `pyarrow`. First we will check the real column names and identity fields, then join the annotation, neurotransmitter, and connection tables on neuron and segment identities.

Because the connection table covers every segment, we will choose the neurons that enter the simulation by explicit criteria. We will report missing annotations and uncertain neurotransmitter predictions. Connections will be stored in a sparse structure that uses memory efficiently.

**Output:** a version-pinned neuron list, a connection list, and a data-check summary.

### 2. Choose the visual input

We will look at which visual cells exist and how they can be related to image locations. When needed we will query with `neuprint-python` and inspect morphology with `navis`. A local neuPrintExplorer install is not required to start.

Our preference is to give camera brightness and contrast to suitable sensory inputs, and to let the motion response arise inside the network as far as possible. Which cell receives which signal is not settled yet, and that is the project's first critical research step.

**Output:** identities of the input cells, and a definition of the transform from image to neural input.

### 3. Add neural dynamics to the connections

The first candidate is a leaky integrate-and-fire (LIF) approach like the one in the work of Shiu and colleagues. In that model a neuron accumulates inputs, its activity decays over time, and it emits a spike when a threshold is crossed.

We need parameters for time constants, thresholds, delays, and the conversion of connection weights into a physiological effect. Neurotransmitter predictions alone do not fix the sign or the size of a synaptic effect; we will record the assumptions we use. Adapting Shiu's FlyWire model to MaleCNS is additional work.

We can first check the data and simulation pipeline on a small circuit. Because cut connections change the dynamics, we will not read that test as the behavior of the whole nervous system.

**Output:** a simulation that responds to a defined input and whose activity can be recorded.

### 4. Move from controlled stimuli to the camera

We will first use repeatable stimuli such as a still image and a moving bar. After checking that activity changes with the input, we will connect the same pipeline to the live camera.

The network state will not be reset on every frame. Camera frame rate and the numerical integration step will be kept separate; we will avoid a backlog of old frames and measure real-time performance.

**Output:** a stream of neural activity that responds continuously to visual input.

### 5. Make the activity audible in Max/MSP

We will send selected populations' spike counts, or their activity in short time windows, to Max over OSC. A first patch can use that activity to make short sounds or drive resonators.

The sonification mapping will be our design choice. The first design planned to listen to the response that arises in the network without adding extra rules for "surprise," "unease," or "habituation." Following an additional request in the 24 September meeting, an optional flight / escape / hide layer was added, separate from the neural model (see below). The user will take over the sound design on the Max/MSP side.

**Output:** sound driven by neural activity that changes with the visitor's movement.

## Success criterion for the first prototype

A prototype in which a change in the camera changes neural activity, that change is heard, and the system runs without interruption for at least 10 minutes. We will measure latency, memory use, and whether the network settles into silence or into continuous overactivity. Then we will look at the interaction in which the visitor changes their movement in response to the sound.

To start, we need the computer's operating system, RAM, and GPU, and which machine Max will run on. The simulation engine and the network scope will be fixed from measurements on that hardware.

## What was settled in the meeting — 24 September 2026

- Machine: macOS 14.6.1, Apple M1 Pro, 32 GB RAM, 16-core integrated GPU. Max/MSP will run on the same Mac.
- The three Feather files are in `data/`. The `.mcns` virtual environment was created with Python 3.9.17.
- Two gestural situations will dominate the interaction: the visitor trying to escape the "fly," and the visitor trying to catch the "fly."
- The "fly" will be a presence felt only through sound. No visual target is planned on screen; a spatial sound position is not defined yet.
- Hand and/or head tracking with MediaPipe or a similar tool will be considered for the camera; the tool choice is not final yet.

**Design proposal, not yet decided:** treat these two situations at first as movement scenarios rather than as gesture labels that trigger ready-made sounds. Measurements such as hand and head position, speed, and hand openness can help study the interaction. Whether they set the neural input directly, or are used only as measurements beside camera brightness and contrast, is an open design choice. If direct feature injection is chosen, it should be recorded as a modeling assumption separate from biological visual input.

**Measurement limit:** until a tracked spatial target is defined for the "fly," hand or head motion cannot be measured as "approaching the fly" or "moving away from the fly." Motion relative to the camera, and hand position relative to the person's own body, can be measured. Intent to avoid or to catch cannot be read from those with certainty.

## Implementation decisions — 24 September 2026

- Scope is camera → simulation → OSC. The Max patch belongs to the user.
- A first circuit was extracted from the right optic lobe: 61 columns and their selected T4/T5 targets, 1,107 neurons, 16,700 connections. Source identities, SHA-256 values, NT uncertainties, and severed connections are recorded in the manifest.
- Camera brightness is passed to L1, L2, and L3 inputs through an approximate column mapping. Photoreceptors are skipped; this is not a calibrated retina model.
- The neural model is a dimensionless, continuous-state LIF prototype. NT signs and dynamic parameters are recorded as explicit assumptions.
- The local UI shows the live camera, hand and face marks, the gray neural input, soma and column maps, and population activity. The maps show the selected circuit; the soma map is not a neuropil or ROI map.
- At the user's later request, a `--behavior` option was added: flight when calm; escape and hiding when the hand or face moves; return after calm. This is authored scene behavior. It is not a claim that the neural model produces fear. Motion measurement drives this layer; camera brightness drives the neural model.
- Raw neural activity and the behavior/flight sound control are sent on separate OSC addresses. Sound is not synthesized here. The detailed contract and the start commands are in `README.md`.

## Sources

- [MaleCNS data download and Python access](https://male-cns.janelia.org/download/)
- [navis: neuPrint tutorial](https://navis-org.github.io/navis/generated/gallery/4_remote/tutorial_remote_00_neuprint/)
- [neuPrintExplorer: data query interface](https://github.com/connectome-neuprint/neuPrintExplorer)
- [Shiu et al., 2024: a computational model of the fly brain](https://www.nature.com/articles/s41586-024-07763-9)
- [Code for the Shiu model](https://github.com/philshiu/Drosophila_brain_model)

*Status (24 September 2026): data preparation, camera, MediaPipe hand and face tracking, the LIF simulation, the live UI, and OSC output are implemented. 17 automated tests passed; detection and the four scene states were observed on a real camera. Completion and error results of long runs are in `runs/*/summary.json`. The full environment is pinned in `requirements.lock.txt`; MediaPipe 0.10.21 is in use. Biological motion selectivity and whole-CNS behavior are not validated.*

## Browser widget implementation — 24 September 2026

`python -m mcns serve` starts a persistent local server. Camera, simulation, and OSC stay in Python;
start/stop, the fly on the scene, and Web Audio synthesis are in the browser. Column activity outside the input of the real visual
subcircuit was mapped to heading, speed, and timbre. The connection A/B control
really removes the synaptic matrix from the circuit; exploration and fear rules are designed separately.
Edges and hand/face centers are 2D landing candidates; they are not semantic object or 3D surface detection.
`/mcns/widget/flight` carries the browser fly's motion to OSC. The older OSC addresses are kept.
Camera images are not saved to disk. Details and how to run it are in README.md.

## Binocular revision driven by the DN readout — 24 September 2026

The previous general rule, human motion → flee/hide, was removed from the default widget.
`configs/bilateral.json` and `build/bilateral-v1`: 8,440 real cells / 278,080 anatomical connections,
columns of both eyes + LC4/LPLC2 + selected DNs + two upstream layers. A pair of local retinal images
is produced from the browser pose. EfficientDet-Lite0 supplies boxes and temporary
IDs for multiple people and objects. The fly is carried by the box it touches; the object label is not neural input.

In the controlled test, DN activity depended on the connections, but looming selectivity failed:
receding produced a stronger response than approaching. This version is an experimental circuit that uses real wiring;
it does not claim to have reproduced natural biological escape. Physiology and retinotopy
calibration remain open scientific requirements. Test report: `build/bilateral-v1/validation.json`.

## Steering-circuit study — 25 September 2026

DNa02 input coverage was found to be low, and the DNg02 family was absent from the selected circuit.
For the study, a real 14,206-cell subgraph, a connection-coverage audit,
equal-brightness direction tests, and a separate graded-visual / LIF hybrid model were added.
The hybrid model produced a connection-dependent motor response, but it did not pass direction-selectivity or saturation
checks and was not put into the live model. Natural flight has not been obtained.
26 Python tests and the widget tests passed. Findings, scientific limits, and the commands to
rerun are in [STEERING_AUDIT.md](STEERING_AUDIT.md).
