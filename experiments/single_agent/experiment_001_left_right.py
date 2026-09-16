from flybrain import FlyBrain
from pathlib import Path
import csv
import time

OUT = Path("results")
OUT.mkdir(exist_ok=True)

WARMUP_STEPS = 25
STIM_STEPS = 50
STIMULUS = 0.8


def run_condition(name, stimulus_side=None):
    print(f"\n=== {name} ===")

    brain = FlyBrain(device="cpu")

    lc10_left = brain.cells(["LC10a"], side="L")
    lc10_right = brain.cells(["LC10a"], side="R")

    dna_left = brain.cells(["DNa02"], side="L")
    dna_right = brain.cells(["DNa02"], side="R")

    print(f"LC10a L: {len(lc10_left)}")
    print(f"LC10a R: {len(lc10_right)}")
    print(f"DNa02 L: {len(dna_left)}")
    print(f"DNa02 R: {len(dna_right)}")

    dna_left_set = set(dna_left)
    dna_right_set = set(dna_right)

    # Даём мозгу немного пожить без стимула
    for _ in range(WARMUP_STEPS):
        brain.step()

    left_spikes = 0
    right_spikes = 0

    t0 = time.perf_counter()

    for _ in range(STIM_STEPS):

        if stimulus_side == "L":
            fired = brain.step(
                inject=[(lc10_left, STIMULUS)]
            )

        elif stimulus_side == "R":
            fired = brain.step(
                inject=[(lc10_right, STIMULUS)]
            )

        else:
            fired = brain.step()

        fired = set(fired)

        left_spikes += len(
            fired.intersection(dna_left_set)
        )

        right_spikes += len(
            fired.intersection(dna_right_set)
        )

    wall_time = time.perf_counter() - t0

    sim_time = STIM_STEPS * brain.dt

    left_rate = (
        left_spikes / (len(dna_left) * sim_time)
        if len(dna_left)
        else 0
    )

    right_rate = (
        right_spikes / (len(dna_right) * sim_time)
        if len(dna_right)
        else 0
    )

    steering_signal = left_rate - right_rate

    result = {
        "condition": name,
        "stimulus_side": stimulus_side or "none",
        "sim_time_s": sim_time,
        "wall_time_s": wall_time,
        "left_spikes": left_spikes,
        "right_spikes": right_spikes,
        "left_rate_hz": left_rate,
        "right_rate_hz": right_rate,
        "steering_signal": steering_signal,
    }

    print(
        f"DNa02 LEFT : {left_spikes} spikes "
        f"({left_rate:.2f} Hz)"
    )

    print(
        f"DNa02 RIGHT: {right_spikes} spikes "
        f"({right_rate:.2f} Hz)"
    )

    print(
        f"L-R steering signal: "
        f"{steering_signal:+.2f} Hz"
    )

    return result


results = [
    run_condition("baseline", None),
    run_condition("target_left", "L"),
    run_condition("target_right", "R"),
]


csv_path = OUT / "experiment_001_left_right.csv"

with open(csv_path, "w", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=results[0].keys()
    )
    writer.writeheader()
    writer.writerows(results)


print("\n==============================")
print("EXPERIMENT 001 COMPLETE")
print("==============================")

for r in results:
    print(
        f"{r['condition']:12} | "
        f"L={r['left_rate_hz']:7.2f} Hz | "
        f"R={r['right_rate_hz']:7.2f} Hz | "
        f"L-R={r['steering_signal']:+7.2f} Hz"
    )

print(f"\nSaved to: {csv_path}")
