from flybrain import FlyBrain
from pathlib import Path
from statistics import mean, stdev
import csv

OUT = Path("results")
OUT.mkdir(exist_ok=True)

N_TRIALS = 8

WARMUP_STEPS = 25
BASELINE_STEPS = 50
STIM_STEPS = 50

STIMULUS = 0.8


def measure(fired_sequence, neurons, sim_time):
    neurons = set(neurons)

    spikes = sum(
        len(set(fired).intersection(neurons))
        for fired in fired_sequence
    )

    return spikes / (len(neurons) * sim_time)


def run_trial(trial, side):

    brain = FlyBrain(device="cpu")

    lc10 = brain.cells(["LC10a"], side=side)

    dna_left = brain.cells(["DNa02"], side="L")
    dna_right = brain.cells(["DNa02"], side="R")

    # Стабилизация сети
    for _ in range(WARMUP_STEPS):
        brain.step()

    # -----------------
    # BASELINE
    # -----------------

    baseline_fired = []

    for _ in range(BASELINE_STEPS):
        baseline_fired.append(brain.step())

    baseline_time = BASELINE_STEPS * brain.dt

    baseline_left = measure(
        baseline_fired,
        dna_left,
        baseline_time
    )

    baseline_right = measure(
        baseline_fired,
        dna_right,
        baseline_time
    )

    # -----------------
    # STIMULUS
    # -----------------

    stim_fired = []

    for _ in range(STIM_STEPS):

        fired = brain.step(
            inject=[(lc10, STIMULUS)]
        )

        stim_fired.append(fired)

    stim_time = STIM_STEPS * brain.dt

    stim_left = measure(
        stim_fired,
        dna_left,
        stim_time
    )

    stim_right = measure(
        stim_fired,
        dna_right,
        stim_time
    )

    delta_left = stim_left - baseline_left
    delta_right = stim_right - baseline_right

    steering_delta = delta_left - delta_right

    print(
        f"trial={trial:02d} "
        f"side={side} | "
        f"ΔL={delta_left:+.2f} "
        f"ΔR={delta_right:+.2f} "
        f"steering={steering_delta:+.2f}"
    )

    return {
        "trial": trial,
        "side": side,

        "baseline_left_hz": baseline_left,
        "baseline_right_hz": baseline_right,

        "stim_left_hz": stim_left,
        "stim_right_hz": stim_right,

        "delta_left_hz": delta_left,
        "delta_right_hz": delta_right,

        "steering_delta_hz": steering_delta,
    }


results = []

for side in ["L", "R"]:

    print()
    print("====================")
    print(f"STIMULUS SIDE: {side}")
    print("====================")

    for trial in range(1, N_TRIALS + 1):
        results.append(
            run_trial(trial, side)
        )


csv_path = OUT / "experiment_001b_repeats.csv"

with open(csv_path, "w", newline="") as f:

    writer = csv.DictWriter(
        f,
        fieldnames=results[0].keys()
    )

    writer.writeheader()
    writer.writerows(results)


print()
print("==============================")
print("SUMMARY")
print("==============================")


for side in ["L", "R"]:

    subset = [
        r["steering_delta_hz"]
        for r in results
        if r["side"] == side
    ]

    avg = mean(subset)
    sd = stdev(subset)

    correct = sum(
        1
        for value in subset
        if (
            (side == "L" and value > 0)
            or
            (side == "R" and value < 0)
        )
    )

    print(
        f"{side}: "
        f"mean steering Δ = {avg:+.2f} Hz, "
        f"SD = {sd:.2f}, "
        f"correct sign = {correct}/{N_TRIALS}"
    )


print()
print(f"Saved to {csv_path}")
