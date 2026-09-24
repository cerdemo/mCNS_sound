"""Stream the full connection table; retain an explicit, reproducible subgraph."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.ipc as ipc
from scipy import sparse

FILES = {
    "annotations": "body-annotations-male-cns-v1.0-minconf-0.5.feather",
    "neurotransmitters": "body-neurotransmitters-male-cns-v1.0.feather",
    "connections": "connectome-weights-male-cns-v1.0-minconf-0.5.feather",
}
# Explicit hypotheses, not receptor-resolved physiology. Unmodelled NTs are silent.
SIGNS = {"acetylcholine": 1, "gaba": -1, "glutamate": -1,
         "histamine": -1}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def batches(path):
    with pa.memory_map(str(path), "r") as source:
        reader = ipc.open_file(source)
        if reader.schema.names != ["body_pre", "body_post", "weight"]:
            raise ValueError("Unexpected connection schema; inspect before continuing")
        for i in range(reader.num_record_batches):
            batch = reader.get_batch(i)
            yield tuple(batch.column(c).to_numpy() for c in range(3))


def prepare(data_dir, output, config):
    data_dir, output = Path(data_dir), Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Output is not empty; choose a new --graph directory")
    paths = {key: data_dir / name for key, name in FILES.items()}
    a = pd.read_feather(paths["annotations"])
    nt = pd.read_feather(paths["neurotransmitters"])
    if a.bodyId.isna().any() or a.bodyId.duplicated().any():
        raise ValueError("Invalid annotation IDs")
    if nt.body.isna().any() or nt.body.duplicated().any():
        raise ValueError("Invalid neurotransmitter IDs")
    s = config["selection"]
    eligible = a[(a.status == "Traced") & (a.somaSide == s["side"])
                 & (a.superclass == "ol_intrinsic")].copy()
    h = eligible.dropna(subset=["assignedOlHex1", "assignedOlHex2"])
    dq = h.assignedOlHex1 - s["center"][0]
    dr = h.assignedOlHex2 - s["center"][1]
    distance = np.maximum.reduce([abs(dq), abs(dr), abs(dq - dr)])
    core = h[distance <= s["radius"]].copy()
    core_ids = core.bodyId.to_numpy()
    target_types = [f"T{number}{letter}" for number in (4, 5) for letter in "abcd"]
    candidates = eligible[eligible.type.isin(target_types)]
    candidate_index = pd.Index(candidates.bodyId)
    scores = np.zeros(len(candidates), dtype=np.int64)
    rows_total = 0
    print("Scanning connections to select T4/T5 targets…", flush=True)
    for pre, post, weight in batches(paths["connections"]):
        if (weight <= 0).any():
            raise ValueError("Non-positive anatomical connection weight")
        rows_total += len(pre)
        mask = np.isin(pre, core_ids)
        indices = candidate_index.get_indexer(post[mask])
        valid = indices >= 0
        np.add.at(scores, indices[valid], weight[mask][valid])
    candidates = candidates.assign(input_synapses=scores)
    downstream = (candidates[candidates.input_synapses > 0]
                  .sort_values(["input_synapses", "bodyId"], ascending=[False, True])
                  .groupby("type", sort=True).head(s["downstream_per_type"]))
    neurons = pd.concat([core, downstream]).sort_values("bodyId").reset_index(drop=True)
    neurons = neurons.merge(nt, left_on="bodyId", right_on="body", how="left",
                            validate="one_to_one", indicator="nt_join")
    neurons["nt_sign"] = neurons.consensus_nt.map(SIGNS).fillna(0).astype(np.int8)
    neurons["is_input"] = neurons.type.isin(s["input_types"])
    if len(neurons) == 0 or not neurons.is_input.any():
        raise ValueError("Selection has no input neurons")
    neurons["population"] = neurons.type.astype(str) + "_" + s["side"]
    neurons["index"] = np.arange(len(neurons))
    index = pd.Index(neurons.bodyId)
    kept, incoming, outgoing = [], 0, 0
    incoming_weight, outgoing_weight, internal_weight = 0, 0, 0
    print(f"Extracting subgraph for {len(neurons)} neurons…", flush=True)
    for pre, post, weight in batches(paths["connections"]):
        src, dst = index.get_indexer(pre), index.get_indexer(post)
        internal = (src >= 0) & (dst >= 0)
        inc, out = (src < 0) & (dst >= 0), (src >= 0) & (dst < 0)
        incoming += int(inc.sum()); outgoing += int(out.sum())
        incoming_weight += int(weight[inc].sum())
        outgoing_weight += int(weight[out].sum())
        internal_weight += int(weight[internal].sum())
        if internal.any():
            kept.append(pd.DataFrame({"source": src[internal], "target": dst[internal],
                                      "weight": weight[internal]}))
    if not kept:
        raise ValueError("Selected graph has no internal connections")
    edges = pd.concat(kept, ignore_index=True)
    duplicates = int(edges.duplicated(["source", "target"]).sum())
    edges = edges.groupby(["source", "target"], as_index=False).weight.sum()
    edges["body_pre"] = neurons.bodyId.to_numpy()[edges.source]
    edges["body_post"] = neurons.bodyId.to_numpy()[edges.target]
    signs = neurons.nt_sign.to_numpy()[edges.source]
    matrix = sparse.coo_matrix((edges.weight.to_numpy(dtype=np.float32) * signs,
                               (edges.target, edges.source)),
                              shape=(len(neurons), len(neurons))).tocsr()
    matrix.eliminate_zeros()
    output.mkdir(parents=True, exist_ok=True)
    neurons.to_feather(output / "neurons.feather")
    edges.to_feather(output / "edges.feather")
    sparse.save_npz(output / "weights.npz", matrix)
    report = {
        "dataset": "male-cns:v1.0", "selection": s, "nt_sign_hypothesis": SIGNS,
        "unmodelled_nt_sign": 0, "annotation_rows": len(a), "nt_rows": len(nt),
        "connection_rows_scanned": rows_total, "neurons": len(neurons),
        "input_neurons": int(neurons.is_input.sum()), "anatomical_edges": len(edges),
        "effective_edges": int(matrix.nnz), "duplicate_pairs_aggregated": duplicates,
        "cut_incoming_edges": incoming, "cut_outgoing_edges": outgoing,
        "cut_incoming_synapses": incoming_weight, "cut_outgoing_synapses": outgoing_weight,
        "internal_synapses": internal_weight,
        "missing_nt_rows": int((neurons.nt_join == "left_only").sum()),
        "unmodelled_nt_neurons": int((neurons.nt_sign == 0).sum()),
        "body_prediction_confidence_below_0_5": int((neurons.predicted_nt_confidence < .5).sum()),
        "missing_body_prediction_confidence": int(neurons.predicted_nt_confidence.isna().sum()),
        "consensus_body_disagreements": int((neurons.consensus_nt != neurons.predicted_nt).sum()),
        "populations": {str(k): int(v) for k, v in neurons.population.value_counts().items()},
        "nt_counts": {str(k): int(v) for k, v in neurons.consensus_nt.value_counts(dropna=False).items()},
        "all_annotation_missing": {str(k): int(v) for k, v in a.isna().sum().items()},
        "sources": {k: {"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
                    for k, p in paths.items()},
        "artifacts": {name: sha256(output / name) for name in
                      ["neurons.feather", "edges.feather", "weights.npz"]},
        "limitations": ["Truncated right/left optic-lobe circuit, not a whole CNS model.",
                        "L1/L2/L3 luminance injection bypasses photoreceptors.",
                        "Hex-to-camera projection is uncalibrated and arbitrary in orientation.",
                        "NT signs use consensus labels; receptor effects and modulators omitted."],
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ["neurons", "input_neurons", "anatomical_edges",
                                            "effective_edges", "unmodelled_nt_neurons"]}, indent=2))
    return report
