from flybrain import FlyBrain
from pathlib import Path
from statistics import mean, stdev
import csv

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

SEEDS = [64, 65, 66, 67, 68]

WARMUP = 25
BASELINE = 100
STIM = 100
AMOUNT = 0.8

CONDITIONS = {
    "LC9_L": [
        ("LC9", "L"),
    ],

    "LC9_R": [
        ("LC9", "R"),
    ],

    "LC9_BOTH": [
        ("LC9", "L"),
        ("LC9", "R"),
    ],

    "LC10a_L": [
        ("LC10a", "L"),
    ],

    "LC10a_R": [
        ("LC10a", "R"),
    ],

    "CHASE_L": [
        ("LC9", "L"),
        ("LC10a", "L"),
    ],

    "CHASE_R": [
        ("LC9", "R"),
        ("LC10a", "R"),
    ],

    "CHASE_BOTH": [
        ("LC9", "L"),
        ("LC9", "R"),
        ("LC10a", "L"),
        ("LC10a", "R"),
    ],
}

OUTPUTS = [
    "DNp09",
    "DNa01",
    "DNa02",
    "DNg100",
    "MDN",
    "DNp01",
]


def rate(sequence, cells, dt):

    cell_set = set(cells)

    if not cell_set:
        return 0.0

    spikes = 0

    for fired in sequence:
        spikes += len(
            cell_set.intersection(
                set(fired)
            )
        )

    return (
        spikes
        / len(cells)
        / (len(sequence) * dt)
    )


records = []


for seed in SEEDS:

    print()
    print("=" * 70)
    print(f"SEED {seed}")
    print("=" * 70)

    brain = FlyBrain(
        device="cpu",
        seed=seed
    )

    output_cells = {}

    for neuron_type in OUTPUTS:

        for side in ["L", "R"]:

            output_cells[
                (neuron_type, side)
            ] = brain.cells(
                [neuron_type],
                side=side
            )

    print(
        "LC9 L/R:",
        len(brain.cells(["LC9"], side="L")),
        "/",
        len(brain.cells(["LC9"], side="R"))
    )

    print(
        "DNp09 L/R:",
        len(brain.cells(["DNp09"], side="L")),
        "/",
        len(brain.cells(["DNp09"], side="R"))
    )

    for condition, specs in CONDITIONS.items():

        brain.reset(seed)

        inject = []

        for neuron_type, side in specs:

            cells = brain.cells(
                [neuron_type],
                side=side
            )

            inject.append(
                (cells, AMOUNT)
            )

        # warmup
        for _ in range(WARMUP):
            brain.step()

        # baseline
        baseline_sequence = []

        for _ in range(BASELINE):
            baseline_sequence.append(
                brain.step()
            )

        # stimulation
        stim_sequence = []

        for _ in range(STIM):
            stim_sequence.append(
                brain.step(
                    inject=inject
                )
            )

        for neuron_type in OUTPUTS:

            for side in ["L", "R"]:

                cells = output_cells[
                    (neuron_type, side)
                ]

                base = rate(
                    baseline_sequence,
                    cells,
                    brain.dt
                )

                stimulated = rate(
                    stim_sequence,
                    cells,
                    brain.dt
                )

                records.append({
                    "seed": seed,
                    "condition": condition,
                    "output": neuron_type,
                    "side": side,
                    "n": len(cells),
                    "baseline_hz": base,
                    "stim_hz": stimulated,
                    "delta_hz":
                        stimulated - base,
                })

        print(
            f"{condition:12} complete"
        )


# ============================================================
# SAVE RAW
# ============================================================

raw_path = (
    RESULTS
    / "experiment_006_chase_raw.csv"
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
# SUMMARY
# ============================================================

print()
print()
print("=" * 90)
print("EXPERIMENT 006 — CHASE PATHWAY")
print("=" * 90)


for condition in CONDITIONS:

    print()
    print(condition)
    print("-" * 90)

    for neuron_type in OUTPUTS:

        for side in ["L", "R"]:

            subset = [
                r["delta_hz"]
                for r in records
                if (
                    r["condition"] == condition
                    and r["output"] == neuron_type
                    and r["side"] == side
                )
            ]

            avg = mean(subset)

            sd = (
                stdev(subset)
                if len(subset) > 1
                else 0.0
            )

            positive = sum(
                x > 0
                for x in subset
            )

            # Don't spam near-zero channels
            if (
                abs(avg) >= 0.5
                or neuron_type in
                ("DNp09", "DNa02")
            ):

                print(
                    f"{neuron_type:8} "
                    f"{side} | "
                    f"Δ={avg:+7.2f} "
                    f"±{sd:5.2f} Hz | "
                    f"+ {positive}/{len(SEEDS)}"
                )


print()
print(
    f"Saved to {raw_path}"
)
