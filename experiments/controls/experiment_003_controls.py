from flybrain import FlyBrain
from pathlib import Path
from collections import deque
from statistics import mean, stdev
import csv
import json
import math
import random
import time


# ============================================================
# EXPERIMENT CONFIG
# ============================================================

MASTER_SEED = 20260916

N_TRIALS = 12
SIM_DURATION = 10.0

FOV_DEG = 120.0
HALF_FOV = FOV_DEG / 2.0

SENSOR_DEADZONE = 2.0

STIMULUS = 0.8

RATE_WINDOW = 10

# Same limits as FlyTank 0.1
TURN_GAIN = 10.0
MAX_TURN_RATE = 80.0

# Direct sign controller gets the SAME coarse sensory information:
# left / centered / right.
DIRECT_TURN_RATE = 40.0

# Privileged engineering baseline.
# It sees exact angular error.
ORACLE_KP = 2.5

WARMUP_STEPS = 25

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def make_trajectory_params(trial):
    """
    Deterministic but different target trajectory for every trial.
    """

    rng = random.Random(MASTER_SEED + trial)

    return {
        "a1": rng.uniform(18.0, 28.0),
        "a2": rng.uniform(6.0, 11.0),
        "a3": rng.uniform(2.0, 6.0),

        "w1": rng.uniform(0.35, 0.70),
        "w2": rng.uniform(0.90, 1.50),
        "w3": rng.uniform(1.70, 2.60),

        "p1": rng.uniform(0, 2 * math.pi),
        "p2": rng.uniform(0, 2 * math.pi),
        "p3": rng.uniform(0, 2 * math.pi),
    }


def target_angle(t, p):

    return (
        p["a1"] * math.sin(p["w1"] * t + p["p1"])
        + p["a2"] * math.sin(p["w2"] * t + p["p2"])
        + p["a3"] * math.sin(p["w3"] * t + p["p3"])
    )


TRAJECTORIES = {
    trial: make_trajectory_params(trial)
    for trial in range(1, N_TRIALS + 1)
}


# ============================================================
# METRICS
# ============================================================

def calculate_metrics(errors, turn_rates):

    abs_errors = [abs(x) for x in errors]

    mse = sum(x * x for x in errors) / len(errors)
    rmse = math.sqrt(mse)

    within_5 = (
        sum(x <= 5.0 for x in abs_errors)
        / len(abs_errors)
        * 100.0
    )

    within_10 = (
        sum(x <= 10.0 for x in abs_errors)
        / len(abs_errors)
        * 100.0
    )

    lost = (
        sum(x > HALF_FOV for x in abs_errors)
        / len(abs_errors)
        * 100.0
    )

    mean_turn = (
        sum(abs(x) for x in turn_rates)
        / len(turn_rates)
    )

    return {
        "mean_abs_error_deg": mean(abs_errors),
        "rmse_deg": rmse,
        "within_5_pct": within_5,
        "within_10_pct": within_10,
        "lost_target_pct": lost,
        "mean_abs_turn_rate_deg_s": mean_turn,
    }


# ============================================================
# SIMPLE CONTROLLERS
# ============================================================

def run_simple_controller(controller, trial):

    params = TRAJECTORIES[trial]

    dt = 0.020

    camera_yaw = 0.0

    errors = []
    turn_rates = []
    rows = []

    n_steps = int(SIM_DURATION / dt)

    for step in range(n_steps):

        t = step * dt

        target = target_angle(t, params)

        pre_error = target - camera_yaw

        visible = abs(pre_error) <= HALF_FOV

        turn_rate = 0.0

        # ----------------------------------------------------
        # PASSIVE
        # ----------------------------------------------------

        if controller == "passive":

            turn_rate = 0.0

        # ----------------------------------------------------
        # DIRECT SIGN CONTROLLER
        # ----------------------------------------------------
        #
        # Gets only:
        # target left / target right / centered.
        #
        # Same coarse sensory abstraction as our LC10a encoder.
        # ----------------------------------------------------

        elif controller == "direct_sign":

            if visible:

                if pre_error < -SENSOR_DEADZONE:
                    turn_rate = -DIRECT_TURN_RATE

                elif pre_error > SENSOR_DEADZONE:
                    turn_rate = DIRECT_TURN_RATE

        # ----------------------------------------------------
        # ORACLE P CONTROLLER
        # ----------------------------------------------------
        #
        # IMPORTANT:
        # This controller sees the exact angular error.
        # It is NOT sensory-equivalent to MaleCNS.
        #
        # It is an engineering upper-reference.
        # ----------------------------------------------------

        elif controller == "oracle_p":

            if visible:

                turn_rate = clamp(
                    ORACLE_KP * pre_error,
                    -MAX_TURN_RATE,
                    MAX_TURN_RATE
                )

        else:
            raise ValueError(controller)

        camera_yaw += turn_rate * dt

        post_error = target - camera_yaw

        errors.append(post_error)
        turn_rates.append(turn_rate)

        rows.append({
            "trial": trial,
            "controller": controller,
            "step": step,
            "sim_time_s": t,
            "target_deg": target,
            "camera_deg": camera_yaw,
            "error_deg": post_error,
            "turn_rate_deg_s": turn_rate,
            "visible": int(visible),
            "dna02_left_hz": "",
            "dna02_right_hz": "",
            "steering_hz": "",
        })

    metrics = calculate_metrics(
        errors,
        turn_rates
    )

    return metrics, rows


# ============================================================
# MALE CNS CONTROLLER
# ============================================================

def run_brain_controller(controller, trial):

    params = TRAJECTORIES[trial]

    brain = FlyBrain(device="cpu")

    lc10_left = brain.cells(
        ["LC10a"],
        side="L"
    )

    lc10_right = brain.cells(
        ["LC10a"],
        side="R"
    )

    dna_left = brain.cells(
        ["DNa02"],
        side="L"
    )

    dna_right = brain.cells(
        ["DNa02"],
        side="R"
    )

    dna_left_set = set(dna_left)
    dna_right_set = set(dna_right)

    # Network stabilization
    for _ in range(WARMUP_STEPS):
        brain.step()

    left_history = deque(
        maxlen=RATE_WINDOW
    )

    right_history = deque(
        maxlen=RATE_WINDOW
    )

    camera_yaw = 0.0

    errors = []
    turn_rates = []

    rows = []

    n_steps = int(
        SIM_DURATION / brain.dt
    )

    for step in range(n_steps):

        t = step * brain.dt

        target = target_angle(
            t,
            params
        )

        pre_error = (
            target - camera_yaw
        )

        visible = (
            abs(pre_error)
            <= HALF_FOV
        )

        inject = []

        # ----------------------------------------------------
        # SENSOR ENCODER
        # ----------------------------------------------------

        if visible:

            if pre_error < -SENSOR_DEADZONE:

                inject.append(
                    (lc10_left, STIMULUS)
                )

            elif pre_error > SENSOR_DEADZONE:

                inject.append(
                    (lc10_right, STIMULUS)
                )

        # ----------------------------------------------------
        # FULL 166,700-NEURON CNS
        # ----------------------------------------------------

        fired = brain.step(
            inject=inject
        )

        fired = set(fired)

        l_spikes = len(
            fired.intersection(
                dna_left_set
            )
        )

        r_spikes = len(
            fired.intersection(
                dna_right_set
            )
        )

        left_history.append(
            l_spikes
        )

        right_history.append(
            r_spikes
        )

        window_seconds = (
            len(left_history)
            * brain.dt
        )

        left_rate = (
            sum(left_history)
            / window_seconds
        )

        right_rate = (
            sum(right_history)
            / window_seconds
        )

        steering = (
            left_rate
            - right_rate
        )

        if abs(steering) < 1.0:
            steering = 0.0

        # ----------------------------------------------------
        # MOTOR DECODER
        # ----------------------------------------------------

        normal_turn_rate = clamp(
            -steering
            * TURN_GAIN,
            -MAX_TURN_RATE,
            MAX_TURN_RATE
        )

        if controller == "malecns":

            turn_rate = (
                normal_turn_rate
            )

        elif controller == "reversed_cns":

            # Deliberately wrong motor mapping
            turn_rate = (
                -normal_turn_rate
            )

        else:
            raise ValueError(
                controller
            )

        camera_yaw += (
            turn_rate
            * brain.dt
        )

        post_error = (
            target - camera_yaw
        )

        errors.append(
            post_error
        )

        turn_rates.append(
            turn_rate
        )

        rows.append({
            "trial": trial,
            "controller": controller,
            "step": step,
            "sim_time_s": t,
            "target_deg": target,
            "camera_deg": camera_yaw,
            "error_deg": post_error,
            "turn_rate_deg_s": turn_rate,
            "visible": int(visible),
            "dna02_left_hz": left_rate,
            "dna02_right_hz": right_rate,
            "steering_hz": steering,
        })

    metrics = calculate_metrics(
        errors,
        turn_rates
    )

    return metrics, rows


# ============================================================
# EXPERIMENT
# ============================================================

controllers = [
    "passive",
    "direct_sign",
    "oracle_p",
    "malecns",
    "reversed_cns",
]

summaries = []
all_steps = []

wall_start = time.perf_counter()


for controller in controllers:

    print()
    print("======================================")
    print(f"CONTROLLER: {controller}")
    print("======================================")

    for trial in range(
        1,
        N_TRIALS + 1
    ):

        trial_start = (
            time.perf_counter()
        )

        if controller in (
            "malecns",
            "reversed_cns"
        ):

            metrics, rows = (
                run_brain_controller(
                    controller,
                    trial
                )
            )

        else:

            metrics, rows = (
                run_simple_controller(
                    controller,
                    trial
                )
            )

        elapsed = (
            time.perf_counter()
            - trial_start
        )

        summary = {
            "trial": trial,
            "controller": controller,
            **metrics,
            "wall_time_s": elapsed,
        }

        summaries.append(
            summary
        )

        all_steps.extend(
            rows
        )

        print(
            f"trial {trial:02d} | "
            f"MAE={metrics['mean_abs_error_deg']:6.2f}° | "
            f"RMSE={metrics['rmse_deg']:6.2f}° | "
            f"±5°={metrics['within_5_pct']:5.1f}% | "
            f"lost={metrics['lost_target_pct']:5.1f}%"
        )


# ============================================================
# SAVE RAW DATA
# ============================================================

summary_path = (
    RESULTS
    / "experiment_003_summary.csv"
)

with open(
    summary_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=summaries[0].keys()
    )

    writer.writeheader()
    writer.writerows(
        summaries
    )


steps_path = (
    RESULTS
    / "experiment_003_steps.csv"
)

with open(
    steps_path,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=all_steps[0].keys()
    )

    writer.writeheader()
    writer.writerows(
        all_steps
    )


# ============================================================
# SAVE CONFIG / TRAJECTORY PARAMETERS
# ============================================================

config = {
    "master_seed": MASTER_SEED,
    "n_trials": N_TRIALS,
    "sim_duration_s": SIM_DURATION,

    "fov_deg": FOV_DEG,

    "sensor_deadzone_deg":
        SENSOR_DEADZONE,

    "stimulus": STIMULUS,

    "rate_window_steps":
        RATE_WINDOW,

    "turn_gain":
        TURN_GAIN,

    "max_turn_rate_deg_s":
        MAX_TURN_RATE,

    "direct_turn_rate_deg_s":
        DIRECT_TURN_RATE,

    "oracle_kp":
        ORACLE_KP,

    "trajectories":
        TRAJECTORIES,
}

config_path = (
    RESULTS
    / "experiment_003_config.json"
)

with open(
    config_path,
    "w"
) as f:

    json.dump(
        config,
        f,
        indent=2
    )


# ============================================================
# FINAL SUMMARY
# ============================================================

print()
print()
print("==========================================")
print("EXPERIMENT 003 — FINAL SUMMARY")
print("==========================================")


controller_results = {}


for controller in controllers:

    subset = [
        x
        for x in summaries
        if x["controller"]
        == controller
    ]

    maes = [
        x["mean_abs_error_deg"]
        for x in subset
    ]

    rmses = [
        x["rmse_deg"]
        for x in subset
    ]

    within5 = [
        x["within_5_pct"]
        for x in subset
    ]

    lost = [
        x["lost_target_pct"]
        for x in subset
    ]

    controller_results[
        controller
    ] = {
        "mae": mean(maes),
        "mae_sd": stdev(maes),
        "rmse": mean(rmses),
        "within5": mean(within5),
        "lost": mean(lost),
    }


print()

for controller in controllers:

    r = controller_results[
        controller
    ]

    print(
        f"{controller:13} | "
        f"MAE={r['mae']:6.2f} ± {r['mae_sd']:5.2f}° | "
        f"RMSE={r['rmse']:6.2f}° | "
        f"±5°={r['within5']:5.1f}% | "
        f"lost={r['lost']:5.1f}%"
    )


# ============================================================
# PAIRED CNS vs PASSIVE COMPARISON
# ============================================================

passive_by_trial = {
    x["trial"]:
        x["mean_abs_error_deg"]
    for x in summaries
    if x["controller"]
    == "passive"
}

cns_by_trial = {
    x["trial"]:
        x["mean_abs_error_deg"]
    for x in summaries
    if x["controller"]
    == "malecns"
}

paired_improvements = []

for trial in range(
    1,
    N_TRIALS + 1
):

    passive = (
        passive_by_trial[trial]
    )

    cns = (
        cns_by_trial[trial]
    )

    improvement = (
        (passive - cns)
        / passive
        * 100.0
    )

    paired_improvements.append(
        improvement
    )


print()
print(
    "MaleCNS paired improvement "
    "vs passive:"
)

print(
    f"{mean(paired_improvements):+.1f}% "
    f"± {stdev(paired_improvements):.1f}%"
)


total_wall = (
    time.perf_counter()
    - wall_start
)

print()
print(
    f"Total wall time: "
    f"{total_wall:.2f} s"
)

print()
print(
    f"Summary: {summary_path}"
)

print(
    f"Steps:   {steps_path}"
)

print(
    f"Config:  {config_path}"
)
