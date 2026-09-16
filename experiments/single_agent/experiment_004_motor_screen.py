from flybrain import FlyBrain
from pathlib import Path
import csv

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

WARMUP_STEPS = 25
BASELINE_STEPS = 50
STIM_STEPS = 50
STIMULUS = 0.8


# ============================================================
# CONDITIONS
# ============================================================

CONDITIONS = [
    ("LC10a_L",        [("LC10a", "L")]),
    ("LC10a_R",        [("LC10a", "R")]),

    ("LPLC1_L",        [("LPLC1", "L")]),
    ("LPLC1_R",        [("LPLC1", "R")]),

    ("LPLC2_L",        [("LPLC2", "L")]),
    ("LPLC2_R",        [("LPLC2", "R")]),

    ("LC4_L",          [("LC4", "L")]),
    ("LC4_R",          [("LC4", "R")]),

    ("LPLC1_BOTH",     [("LPLC1", "L"), ("LPLC1", "R")]),
    ("LPLC2_BOTH",     [("LPLC2", "L"), ("LPLC2", "R")]),
    ("LC4_BOTH",       [("LC4", "L"), ("LC4", "R")]),

    (
        "LOOM_BOTH",
        [
            ("LC4", "L"),
            ("LC4", "R"),
            ("LPLC2", "L"),
            ("LPLC2", "R"),
        ]
    ),
]


OUTPUT_TYPES = [
    "DNa02",
    "DNp01",
    "DNg100",
    "MDN",
]


# ============================================================
# HELPERS
# ============================================================

def rate_for_sequence(sequence, neuron_indices, dt):
    neuron_set = set(neuron_indices)

    if not neuron_set:
        return 0.0

    spikes = 0

    for fired in sequence:
        spikes += len(
            neuron_set.intersection(
                set(fired)
            )
        )

    seconds = len(sequence) * dt

    return (
        spikes
        / len(neuron_set)
        / seconds
    )


def get_outputs(brain):

    outputs = {}

    for neuron_type in OUTPUT_TYPES:

        outputs[(neuron_type, "L")] = brain.cells(
            [neuron_type],
            side="L"
        )

        outputs[(neuron_type, "R")] = brain.cells(
            [neuron_type],
            side="R"
        )

        outputs[(neuron_type, "ALL")] = brain.cells(
            [neuron_type]
        )

    return outputs


# ============================================================
# RUN CONDITION
# ============================================================

def run_condition(name, sensory_spec):

    print()
    print("=" * 65)
    print(name)
    print("=" * 65)

    brain = FlyBrain(device="cpu")

    outputs = get_outputs(brain)

    # Build sensory injection populations
    sensory = []

    for neuron_type, side in sensory_spec:

        cells = brain.cells(
            [neuron_type],
            side=side
        )

        print(
            f"input {neuron_type:7} "
            f"side={side} "
            f"n={len(cells)}"
        )

        sensory.append(
            (cells, STIMULUS)
        )

    # --------------------------------------------------------
    # WARMUP
    # --------------------------------------------------------

    for _ in range(WARMUP_STEPS):
        brain.step()

    # --------------------------------------------------------
    # BASELINE
    # --------------------------------------------------------

    baseline = []

    for _ in range(BASELINE_STEPS):
        baseline.append(
            brain.step()
        )

    # --------------------------------------------------------
    # STIMULUS
    # --------------------------------------------------------

    stimulus = []

    for _ in range(STIM_STEPS):
        stimulus.append(
            brain.step(
                inject=sensory
            )
        )

    # --------------------------------------------------------
    # MEASURE
    # --------------------------------------------------------

    row = {
        "condition": name
    }

    for neuron_type in OUTPUT_TYPES:

        for side in ["L", "R", "ALL"]:

            indices = outputs[
                (neuron_type, side)
            ]

            baseline_rate = rate_for_sequence(
                baseline,
                indices,
                brain.dt
            )

            stim_rate = rate_for_sequence(
                stimulus,
                indices,
                brain.dt
            )

            delta = (
                stim_rate
                - baseline_rate
            )

            prefix = (
                f"{neuron_type}_{side}"
            )

            row[
                prefix + "_n"
            ] = len(indices)

            row[
                prefix + "_baseline_hz"
            ] = baseline_rate

            row[
                prefix + "_stim_hz"
            ] = stim_rate

            row[
                prefix + "_delta_hz"
            ] = delta

    # Useful steering measure
    row["DNa02_steering_delta"] = (
        row["DNa02_L_delta_hz"]
        - row["DNa02_R_delta_hz"]
    )

    # --------------------------------------------------------
    # HUMAN-READABLE OUTPUT
    # --------------------------------------------------------

    print()
    print("OUTPUT DELTAS")

    print(
        f"DNa02 steering : "
        f"{row['DNa02_steering_delta']:+7.2f} Hz"
    )

    print(
        f"DNp01 escape   : "
        f"{row['DNp01_ALL_delta_hz']:+7.2f} Hz"
    )

    print(
        f"DNg100 forward : "
        f"{row['DNg100_ALL_delta_hz']:+7.2f} Hz"
    )

    print(
        f"MDN backward   : "
        f"{row['MDN_ALL_delta_hz']:+7.2f} Hz"
    )

    print()
    print(
        f"DNg100 n={row['DNg100_ALL_n']} | "
        f"baseline={row['DNg100_ALL_baseline_hz']:.2f} | "
        f"stim={row['DNg100_ALL_stim_hz']:.2f}"
    )

    print(
        f"MDN    n={row['MDN_ALL_n']} | "
        f"baseline={row['MDN_ALL_baseline_hz']:.2f} | "
        f"stim={row['MDN_ALL_stim_hz']:.2f}"
    )

    return row


# ============================================================
# EXPERIMENT
# ============================================================

rows = []

for name, spec in CONDITIONS:

    rows.append(
        run_condition(
            name,
            spec
        )
    )


# ============================================================
# SAVE
# ============================================================

csv_path = (
    RESULTS
    / "experiment_004_motor_screen.csv"
)

with open(
    csv_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(rows)


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print()
print("=" * 80)
print("EXPERIMENT 004 — MOTOR SCREEN SUMMARY")
print("=" * 80)

print(
    f"{'condition':14} | "
    f"{'steer':>8} | "
    f"{'escape':>8} | "
    f"{'forward':>8} | "
    f"{'backward':>8}"
)

print("-" * 80)

for row in rows:

    print(
        f"{row['condition']:14} | "
        f"{row['DNa02_steering_delta']:+8.2f} | "
        f"{row['DNp01_ALL_delta_hz']:+8.2f} | "
        f"{row['DNg100_ALL_delta_hz']:+8.2f} | "
        f"{row['MDN_ALL_delta_hz']:+8.2f}"
    )

print()
print(
    f"Saved to {csv_path}"
)
