# Steering study through the wiring — 25 September 2026

Natural flight is not yet validated. This work did not change how the live widget moves;
the default `bilateral-v1` model and the OSC stream are unchanged. The new experimental model was not
wired into the live runner. Missing neural responses were not covered up with extra random turns.

## Gaps found

The first selected circuit contained only about 10.6–15.8% of the incoming synaptic weight
onto DNa02 cells in the full dataset. The 29 cells of the DNg02 family were not in the selection.
Giving DNa02 a direct diagnostic current produced firing, which showed that the silence
did not come only from the output reader.

Reading DNa02 as a single general flight-direction channel is not enough.
The [DNg02 study](https://pubmed.ncbi.nlm.nih.gov/35090590/) supports wing-amplitude
control in flight, and the [comparative DN study](https://www.nature.com/articles/s41586-025-08925-z)
supports looking at distinct motor connections. Those findings do not validate
the parameters in the current simulation.

The expanded circuit prepared with `configs/flight-audit.json` contains 14,206 real cells and
609,432 anatomical connections; 606,414 of those connections are nonzero under the neurotransmitter sign
model used here. DNg02 cells on both sides and a wider upstream
selection were included. Incoming-weight coverage of DNa02 rose to about 43.6–44.6%.
This is still a cut subgraph. It is not the full CNS, and there are no new or mirrored neurons.

## Controlled experiments

- With the original LIF physiology, the expanded circuit gave a DNa02 response to a constant white
  input in the right eye. With oppositely moving gratings of equal mean brightness, DNa02
  and DNg02 stayed silent. The individual T4/T5 cells that were tested also stayed below the 1 Hz response threshold.
- Raising the global synaptic gain turned some DN responses on; high gain pushed some
  cells to the model's firing ceiling. Those settings were not applied to the live model.
- `mcns/hybrid.py` is a separate hypothesis: graded release for visual cells, LIF
  for central cells. Connection identities and signs are kept. Because visual
  target rows are normalized, the absolute effective weights are not the same as in the original LIF.
  There is no learning and no new connection.

In the hybrid model a DN response appeared, and it disappeared when the connections were turned off. Even so,
opposite directions of motion in the two eyes did not produce an opposing left–right DNg02 difference, and some central
cells sat at the model ceiling near 333.5 Hz. `eligible_for_runtime=false`.
The 300 Hz screen is a saturation check for this model, not a universal rate limit
for every biological cell. Passing the tests would not, by itself, mean biological validity.

The [Flyvis study](https://www.nature.com/articles/s41586-024-07939-3) is a methodological reference
for graded visual dynamics. Flyvis's trained parameters are not used here. The graded-versus-spiking
split by cell class, the time constants, the basal release, and the release-to-current transform
are uncalibrated assumptions. The result therefore cannot be presented as "the wiring produced natural flight."
The next scientific requirement is to check cell-type physiology and retinotopy, and to obtain visual direction selectivity first.

## How to rerun

From the project root, with the existing data files and the `.mcns` environment:

```sh
.mcns/bin/python -m mcns prepare --config configs/flight-audit.json --graph build/flight-audit-v1
.mcns/bin/python scripts/audit_steering.py --graph build/flight-audit-v1 --config configs/flight-audit.json --output build/flight-audit-v1/steering-audit.json
.mcns/bin/python scripts/probe_physiology.py
.mcns/bin/python scripts/validate_direction.py
.mcns/bin/python scripts/validate_hybrid.py
.mcns/bin/python -m unittest discover -s tests -v
node tests/test_widget.js
```

Numerical reports are under `build/flight-audit-v1/` as `steering-audit.json`,
`physiology-probes.json`, `direction-validation.json`, and `hybrid-validation.json`.
`build/` is generated output and stays outside Git. The experiment code
and config files are there so the results can be reproduced. The hybrid report includes config, code, and
graph identities, separate release and Hz measurements, and the screening criteria that failed.

Check: 26 Python tests and the JavaScript widget tests passed. They test that the software
runs. They do not stand in for the failed visual direction-selectivity experiment.
