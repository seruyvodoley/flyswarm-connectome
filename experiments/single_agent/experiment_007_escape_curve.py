from flybrain import FlyBrain
from pathlib import Path
from statistics import mean, stdev
import csv

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

SEEDS = [64, 65, 66, 67, 68]

AMOUNTS = [
    0.05,
    0.10,
    0.20,
    0.30,
    0.40,
    0.50,
    0.60,
    0.80,
    1.00,
]

WARMUP = 25
BASELINE = 100
STIM = 100

OUTPUTS = [
    "DNp01",
    "DNp02",
    "DNp04",
    "DNp11",
]

records = []


def firing_rate(sequence, cells, dt):
    cells = set(cells)

    if not cells:
        return 0.0

    spikes = 0

    for fired in sequence:
        spikes += len(
            cells.intersection(set(fired))
        )

    return (
        spikes
        / len(cells)
        / (len(sequence) * dt)
    )


for seed in SEEDS:

    print()
    print("=" * 60)
    print(f"SEED {seed}")
    print("=" * 60)

    brain = FlyBrain(
        device="cpu",
        seed=seed
    )

    lc4_l = brain.cells(
        ["LC4"],
        side="L"
    )

    lc4_r = brain.cells(
        ["LC4"],
        side="R"
    )

    lplc2_l = brain.cells(
        ["LPLC2"],
        side="L"
    )

    lplc2_r = brain.cells(
        ["LPLC2"],
        side="R"
    )

    outputs = {
        name: brain.cells([name])
        for name in OUTPUTS
    }

    for amount in AMOUNTS:

        brain.reset(seed)

        # Stabilize
        for _ in range(WARMUP):
            brain.step()

        baseline = []

        for _ in range(BASELINE):
            baseline.append(
                brain.step()
            )

        inject = [
            (lc4_l, amount),
            (lc4_r, amount),
            (lplc2_l, amount),
            (lplc2_r, amount),
        ]

        stimulated = []

        for _ in range(STIM):
            stimulated.append(
                brain.step(
                    inject=inject
                )
            )

        print(
            f"amount={amount:.2f}",
            end=" | "
        )

        for output_name in OUTPUTS:

            cells = outputs[
                output_name
            ]

            base = firing_rate(
                baseline,
                cells,
                brain.dt
            )

            stim = firing_rate(
                stimulated,
                cells,
                brain.dt
            )

            delta = stim - base

            records.append({
                "seed": seed,
                "amount": amount,
                "output": output_name,
                "n_cells": len(cells),
                "baseline_hz": base,
                "stim_hz": stim,
                "delta_hz": delta,
            })

            print(
                f"{output_name} "
                f"{delta:+5.1f}",
                end=" | "
            )

        print()


# ============================================================
# SAVE RAW
# ============================================================

raw_path = (
    RESULTS
    / "experiment_007_escape_curve_raw.csv"
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
# AGGREGATE
# ============================================================

print()
print()
print("=" * 82)
print("EXPERIMENT 007 — ESCAPE RESPONSE CURVE")
print("=" * 82)

print(
    f"{'input':>6} | "
    f"{'DNp01':>14} | "
    f"{'DNp02':>14} | "
    f"{'DNp04':>14} | "
    f"{'DNp11':>14}"
)

print("-" * 82)


summary_rows = []


for amount in AMOUNTS:

    line = {
        "amount": amount
    }

    text = f"{amount:6.2f} | "

    for output in OUTPUTS:

        values = [
            r["delta_hz"]
            for r in records
            if (
                r["amount"] == amount
                and
                r["output"] == output
            )
        ]

        avg = mean(values)
        sd = stdev(values)

        line[
            f"{output}_mean_delta"
        ] = avg

        line[
            f"{output}_sd"
        ] = sd

        text += (
            f"{avg:+6.2f}"
            f"±{sd:4.2f} | "
        )

    summary_rows.append(line)

    print(text)


summary_path = (
    RESULTS
    / "experiment_007_escape_curve_summary.csv"
)

with open(
    summary_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=summary_rows[0].keys()
    )

    writer.writeheader()
    writer.writerows(
        summary_rows
    )


print()
print(
    f"Raw:     {raw_path}"
)

print(
    f"Summary: {summary_path}"
)
