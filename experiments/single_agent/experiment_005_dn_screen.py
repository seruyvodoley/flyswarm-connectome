from flybrain import FlyBrain
from pathlib import Path
from collections import defaultdict
from statistics import mean, stdev
import numpy as np
import csv

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

SEEDS = [64, 65, 66, 67, 68]

WARMUP_STEPS = 25
BASELINE_STEPS = 100
STIM_STEPS = 100

STIMULUS = 0.8

CONDITIONS = [
    ("LC10a_L", [
        ("LC10a", "L")
    ]),

    ("LC10a_R", [
        ("LC10a", "R")
    ]),

    ("LPLC1_BOTH", [
        ("LPLC1", "L"),
        ("LPLC1", "R")
    ]),

    ("LPLC2_BOTH", [
        ("LPLC2", "L"),
        ("LPLC2", "R")
    ]),

    ("LC4_BOTH", [
        ("LC4", "L"),
        ("LC4", "R")
    ]),

    ("LOOM_BOTH", [
        ("LC4", "L"),
        ("LC4", "R"),
        ("LPLC2", "L"),
        ("LPLC2", "R")
    ]),
]


def count_rates(brain, steps, slot, n_dns, inject=()):
    counts = np.zeros(n_dns, dtype=np.int64)

    for _ in range(steps):
        fired = brain.step(inject=inject)

        dn_slots = slot[fired]
        dn_slots = dn_slots[dn_slots >= 0]

        if len(dn_slots):
            np.add.at(
                counts,
                dn_slots,
                1
            )

    seconds = steps * brain.dt

    return counts / seconds


records = []

for seed in SEEDS:

    print()
    print("=" * 70)
    print(f"NOISE SEED {seed}")
    print("=" * 70)

    brain = FlyBrain(
        device="cpu",
        seed=seed
    )

    # --------------------------------------------------------
    # ALL DESCENDING NEURONS
    # --------------------------------------------------------

    dns = brain.cells(
        ["descending_neuron"]
    )

    print(
        f"Descending neurons: {len(dns)}"
    )

    # Map global neuron index -> slot inside dns[]
    slot = np.full(
        brain.n,
        -1,
        dtype=np.int64
    )

    slot[dns] = np.arange(
        len(dns)
    )

    # --------------------------------------------------------
    # GROUP DNs BY CELL TYPE + SIDE
    # --------------------------------------------------------

    groups = defaultdict(list)

    for local_idx, global_idx in enumerate(dns):

        cell_type = str(
            brain.cell_type[global_idx]
        )

        side = str(
            brain.side[global_idx]
        )

        if not cell_type:
            cell_type = "<untyped>"

        if not side:
            side = "-"

        groups[
            (cell_type, side)
        ].append(local_idx)

    # --------------------------------------------------------
    # CONDITIONS
    # --------------------------------------------------------

    for condition_name, sensory_spec in CONDITIONS:

        # Same initial state / noise sequence for every
        # condition within one seed: paired comparison.
        brain.reset(seed)

        sensory = []

        for neuron_type, side in sensory_spec:

            idx = brain.cells(
                [neuron_type],
                side=side
            )

            sensory.append(
                (idx, STIMULUS)
            )

        # warm-up
        for _ in range(WARMUP_STEPS):
            brain.step()

        # baseline
        baseline_rates = count_rates(
            brain,
            BASELINE_STEPS,
            slot,
            len(dns)
        )

        # stimulation
        stim_rates = count_rates(
            brain,
            STIM_STEPS,
            slot,
            len(dns),
            inject=sensory
        )

        print(
            f"{condition_name:12} complete"
        )

        for (cell_type, side), local_indices in groups.items():

            idx = np.asarray(
                local_indices,
                dtype=np.int64
            )

            baseline = float(
                baseline_rates[idx].mean()
            )

            stim = float(
                stim_rates[idx].mean()
            )

            delta = (
                stim - baseline
            )

            records.append({
                "seed": seed,
                "condition": condition_name,
                "cell_type": cell_type,
                "side": side,
                "n_cells": len(idx),
                "baseline_hz": baseline,
                "stim_hz": stim,
                "delta_hz": delta,
            })


# ============================================================
# SAVE RAW RESULTS
# ============================================================

raw_path = (
    RESULTS
    / "experiment_005_dn_screen_raw.csv"
)

with open(
    raw_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=records[0].keys()
    )

    writer.writeheader()
    writer.writerows(records)


# ============================================================
# AGGREGATE ACROSS SEEDS
# ============================================================

by_group = defaultdict(list)

for r in records:

    key = (
        r["condition"],
        r["cell_type"],
        r["side"],
        r["n_cells"]
    )

    by_group[key].append(
        r["delta_hz"]
    )


summary = []

for key, values in by_group.items():

    condition, cell_type, side, n_cells = key

    summary.append({
        "condition": condition,
        "cell_type": cell_type,
        "side": side,
        "n_cells": n_cells,

        "mean_delta_hz":
            mean(values),

        "sd_delta_hz":
            stdev(values)
            if len(values) > 1
            else 0.0,

        "positive_seeds":
            sum(v > 0 for v in values),

        "negative_seeds":
            sum(v < 0 for v in values),
    })


summary_path = (
    RESULTS
    / "experiment_005_dn_screen_summary.csv"
)

with open(
    summary_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=summary[0].keys()
    )

    writer.writeheader()
    writer.writerows(summary)


# ============================================================
# DISPLAY TOP RESPONDERS
# ============================================================

print()
print()
print("=" * 85)
print("EXPERIMENT 005 — DESCENDING NEURON SCREEN")
print("=" * 85)


for condition_name, _ in CONDITIONS:

    subset = [
        r for r in summary
        if r["condition"] == condition_name
    ]

    subset.sort(
        key=lambda r:
        abs(r["mean_delta_hz"]),
        reverse=True
    )

    print()
    print("=" * 85)
    print(condition_name)
    print("=" * 85)

    print(
        f"{'cell type':18} "
        f"{'side':5} "
        f"{'n':>4} "
        f"{'delta Hz':>11} "
        f"{'SD':>8} "
        f"{'+seed':>7} "
        f"{'-seed':>7}"
    )

    print("-" * 85)

    for r in subset[:15]:

        print(
            f"{r['cell_type'][:18]:18} "
            f"{r['side'][:5]:5} "
            f"{r['n_cells']:4d} "
            f"{r['mean_delta_hz']:+11.2f} "
            f"{r['sd_delta_hz']:8.2f} "
            f"{r['positive_seeds']:7d} "
            f"{r['negative_seeds']:7d}"
        )


# ============================================================
# KNOWN OUTPUTS
# ============================================================

print()
print()
print("=" * 85)
print("KNOWN MOTOR OUTPUTS")
print("=" * 85)

KNOWN = [
    "DNa02",
    "DNp01",
    "DNg100",
    "MDN"
]

for condition_name, _ in CONDITIONS:

    print()
    print(condition_name)

    for neuron_type in KNOWN:

        matches = [
            r for r in summary
            if (
                r["condition"] == condition_name
                and r["cell_type"] == neuron_type
            )
        ]

        if not matches:
            print(
                f"  {neuron_type:8}: not found"
            )
            continue

        for r in matches:

            print(
                f"  {neuron_type:8} "
                f"{r['side']:3} "
                f"Δ={r['mean_delta_hz']:+6.2f} "
                f"±{r['sd_delta_hz']:.2f} Hz "
                f"({r['positive_seeds']}/{len(SEEDS)} positive)"
            )


print()
print(
    f"Raw:     {raw_path}"
)

print(
    f"Summary: {summary_path}"
)
