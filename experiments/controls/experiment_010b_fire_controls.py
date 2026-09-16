from flybrain import FlyBrain
from flybrain.reservoir import Trace, Readout

from collections import deque
from pathlib import Path
from statistics import mean, stdev

import csv
import json
import math
import numpy as np


# ============================================================
# CONFIG
# ============================================================

N = 8

SEEDS = list(
    range(
        164,
        174
    )
)

MODES = [
    "auto",
    "learned",
    "random",
]

SIM_DURATION = 45.0

WARMUP_STEPS = 25
RATE_WINDOW = 10

STIMULUS = 0.8

ARENA_W = 1000
ARENA_H = 700

DETECTION_RANGE = 650.0

BODY_FOV = 150.0
TURRET_FOV = 120.0

BODY_DEADZONE = 4.0
TURRET_DEADZONE = 1.5

P9_DEADZONE = 2.0

SPEED_GAIN = 1.0
MAX_SPEED = 18.0

BODY_TURN_GAIN = 5.0
MAX_BODY_TURN = 60.0

TURRET_GAIN = 10.0
MAX_TURRET_TURN = 80.0

TANK_RADIUS = 15.0

MAX_HP = 3

RELOAD_TIME = 1.20

PROJECTILE_SPEED = 280.0
PROJECTILE_LIFETIME = 3.0

# privileged baseline only
AUTO_FIRE_RANGE = 500.0
AUTO_FIRE_ERROR = 4.0

RESULTS = Path("results")

MODEL_PATH = (
    RESULTS
    / "flyswarm_03_fire_readout.npz"
)

CONFIG_PATH = (
    RESULTS
    / "experiment_010a_fire_threshold.json"
)

CSV_PATH = (
    RESULTS
    / "experiment_010b_fire_controls.csv"
)


# ============================================================
# LOAD LEARNED POLICY
# ============================================================

with open(
    CONFIG_PATH
) as f:
    calibration = json.load(f)

FIRE_THRESHOLD = float(
    calibration[
        "deploy_threshold"
    ]
)

RANDOM_FIRE_PROB = float(
    calibration[
        "oof_fire_rate"
    ]
)

readout = Readout.load(
    MODEL_PATH
)


print("=" * 82)
print("EXPERIMENT 010b — FIRE CONTROLS")
print("=" * 82)

print(
    f"learned threshold : "
    f"{FIRE_THRESHOLD:.3f}"
)

print(
    f"random propensity : "
    f"{RANDOM_FIRE_PROB:.3f}"
)

print(
    f"paired seeds      : "
    f"{SEEDS}"
)


# ============================================================
# HELPERS
# ============================================================

def clamp(x, lo, hi):

    return max(
        lo,
        min(hi, x)
    )


def wrap_angle(a):

    while a > 180:
        a -= 360

    while a < -180:
        a += 360

    return a


def bearing(dx, dy):

    return math.degrees(
        math.atan2(
            dx,
            dy
        )
    )


def segment_circle_t(
    x1,
    y1,
    x2,
    y2,
    cx,
    cy,
    radius
):

    vx = x2 - x1
    vy = y2 - y1

    wx = cx - x1
    wy = cy - y1

    vv = (
        vx * vx
        + vy * vy
    )

    if vv <= 1e-12:
        return None

    t = (
        wx * vx
        + wy * vy
    ) / vv

    t = clamp(
        t,
        0.0,
        1.0
    )

    px = (
        x1
        + vx * t
    )

    py = (
        y1
        + vy * t
    )

    if (
        math.hypot(
            px - cx,
            py - cy
        )
        <= radius
    ):
        return t

    return None


# ============================================================
# BRAIN
# ============================================================

print()
print("Loading batch MaleCNS...")

brain = FlyBrain(
    device="cpu",
    batch=N,
    seed=SEEDS[0]
)


lc9_l = brain.cells(
    ["LC9"],
    side="L"
)

lc9_r = brain.cells(
    ["LC9"],
    side="R"
)

lc10_l = brain.cells(
    ["LC10a"],
    side="L"
)

lc10_r = brain.cells(
    ["LC10a"],
    side="R"
)


p9_l = set(
    brain.cells(
        ["DNp09"],
        side="L"
    )
)

p9_r = set(
    brain.cells(
        ["DNp09"],
        side="R"
    )
)

a02_l = set(
    brain.cells(
        ["DNa02"],
        side="L"
    )
)

a02_r = set(
    brain.cells(
        ["DNa02"],
        side="R"
    )
)


descending = brain.cells(
    ["descending_neuron"]
)

trace = Trace(
    brain,
    idx=descending,
    tau=0.10,
    aggregate="batch"
)


teams = np.array([
    0, 0, 0, 0,
    1, 1, 1, 1
])


# ============================================================
# WORLD
# ============================================================

def create_world():

    xs = np.array([
        180., 390., 610., 820.,
        180., 390., 610., 820.,
    ])

    ys = np.array([
        100., 120., 120., 100.,
        600., 580., 580., 600.,
    ])

    body = np.array([
        0., 0., 0., 0.,
        180., 180., 180., 180.,
    ])

    turret = np.zeros(
        N,
        dtype=float
    )

    alive = np.ones(
        N,
        dtype=bool
    )

    hp = np.full(
        N,
        MAX_HP,
        dtype=int
    )

    last_shot = np.full(
        N,
        -999.0
    )

    return (
        xs,
        ys,
        body,
        turret,
        alive,
        hp,
        last_shot,
    )


def make_history():

    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW
        )
        for _ in range(N)
    ]


def rate(history, i):

    return (
        sum(history[i])
        /
        (
            len(history[i])
            * brain.dt
        )
    )


def choose_target(
    i,
    xs,
    ys,
    body,
    alive
):

    if not alive[i]:
        return -1

    best = -1
    best_d = float("inf")

    for j in range(N):

        if (
            not alive[j]
            or teams[j] == teams[i]
        ):
            continue

        dx = xs[j] - xs[i]
        dy = ys[j] - ys[i]

        d = math.hypot(
            dx,
            dy
        )

        if d > DETECTION_RANGE:
            continue

        error = wrap_angle(
            bearing(dx, dy)
            - body[i]
        )

        if (
            abs(error)
            > BODY_FOV / 2
        ):
            continue

        if d < best_d:

            best = j
            best_d = d

    return best


def resolve_collisions(
    xs,
    ys,
    alive
):

    minimum = (
        2 * TANK_RADIUS
    )

    for i in range(N):

        if not alive[i]:
            continue

        for j in range(
            i + 1,
            N
        ):

            if not alive[j]:
                continue

            dx = xs[j] - xs[i]
            dy = ys[j] - ys[i]

            d = math.hypot(
                dx,
                dy
            )

            if d >= minimum:
                continue

            if d < 1e-6:
                dx = 1.0
                dy = 0.0
                d = 1.0

            overlap = (
                minimum - d
            )

            nx = dx / d
            ny = dy / d

            push = overlap / 2

            xs[i] -= nx * push
            ys[i] -= ny * push

            xs[j] += nx * push
            ys[j] += ny * push


    for i in range(N):

        xs[i] = clamp(
            xs[i],
            TANK_RADIUS,
            ARENA_W - TANK_RADIUS
        )

        ys[i] = clamp(
            ys[i],
            TANK_RADIUS,
            ARENA_H - TANK_RADIUS
        )


# ============================================================
# ONE BATTLE
# ============================================================

def run_battle(
    seed,
    mode
):

    brain.reset(seed)
    trace.reset()

    for _ in range(
        WARMUP_STEPS
    ):
        brain.step()


    (
        xs,
        ys,
        body,
        turret,
        alive,
        hp,
        last_shot,
    ) = create_world()


    p9_l_hist = make_history()
    p9_r_hist = make_history()

    a02_l_hist = make_history()
    a02_r_hist = make_history()


    shots = np.zeros(
        N,
        dtype=int
    )

    hits = np.zeros(
        N,
        dtype=int
    )

    kills = np.zeros(
        N,
        dtype=int
    )


    projectiles = []

    rng = np.random.default_rng(
        900000 + seed
    )

    targets = np.full(
        N,
        -1,
        dtype=int
    )

    eligible = 0
    learned_score_sum = 0.0
    learned_score_n = 0

    sim_t = 0.0


    while sim_t < SIM_DURATION:

        blue_alive = int(
            alive[:4].sum()
        )

        red_alive = int(
            alive[4:].sum()
        )

        if (
            blue_alive == 0
            or red_alive == 0
        ):
            break


        body_error = np.zeros(N)
        turret_error = np.zeros(N)


        # ----------------------------------------------------
        # PERCEPTION
        # ----------------------------------------------------

        for i in range(N):

            targets[i] = choose_target(
                i,
                xs,
                ys,
                body,
                alive
            )

            j = targets[i]

            if j < 0:
                continue

            dx = xs[j] - xs[i]
            dy = ys[j] - ys[i]

            target_bearing = bearing(
                dx,
                dy
            )

            body_error[i] = (
                wrap_angle(
                    target_bearing
                    - body[i]
                )
            )

            turret_world = (
                wrap_angle(
                    body[i]
                    + turret[i]
                )
            )

            turret_error[i] = (
                wrap_angle(
                    target_bearing
                    - turret_world
                )
            )


        # ----------------------------------------------------
        # SENSOR INPUT
        # ----------------------------------------------------

        lc9_l_amount = np.zeros(
            N,
            dtype=np.float32
        )

        lc9_r_amount = np.zeros(
            N,
            dtype=np.float32
        )

        lc10_l_amount = np.zeros(
            N,
            dtype=np.float32
        )

        lc10_r_amount = np.zeros(
            N,
            dtype=np.float32
        )


        for i in range(N):

            if (
                not alive[i]
                or targets[i] < 0
            ):
                continue


            e = body_error[i]

            if e < -BODY_DEADZONE:

                lc9_l_amount[i] = STIMULUS

            elif e > BODY_DEADZONE:

                lc9_r_amount[i] = STIMULUS

            else:

                lc9_l_amount[i] = STIMULUS
                lc9_r_amount[i] = STIMULUS


            te = turret_error[i]

            if (
                abs(te)
                <= TURRET_FOV / 2
            ):

                if (
                    te
                    < -TURRET_DEADZONE
                ):
                    lc10_l_amount[i] = (
                        STIMULUS
                    )

                elif (
                    te
                    > TURRET_DEADZONE
                ):
                    lc10_r_amount[i] = (
                        STIMULUS
                    )


        # ----------------------------------------------------
        # BRAIN
        # ----------------------------------------------------

        fired_by_fly = brain.step(
            inject=[
                (
                    lc9_l,
                    lc9_l_amount
                ),
                (
                    lc9_r,
                    lc9_r_amount
                ),
                (
                    lc10_l,
                    lc10_l_amount
                ),
                (
                    lc10_r,
                    lc10_r_amount
                ),
            ]
        )

        activity = trace.observe(
            fired_by_fly
        )


        speeds = np.zeros(N)
        body_turn = np.zeros(N)
        turret_turn = np.zeros(N)


        # ----------------------------------------------------
        # NATURAL MOTOR OUTPUTS
        # ----------------------------------------------------

        for i in range(N):

            fired = set(
                fired_by_fly[i]
            )

            p9_l_hist[i].append(
                len(
                    fired.intersection(
                        p9_l
                    )
                )
            )

            p9_r_hist[i].append(
                len(
                    fired.intersection(
                        p9_r
                    )
                )
            )

            a02_l_hist[i].append(
                len(
                    fired.intersection(
                        a02_l
                    )
                )
            )

            a02_r_hist[i].append(
                len(
                    fired.intersection(
                        a02_r
                    )
                )
            )


            if not alive[i]:
                continue


            p9L = rate(
                p9_l_hist,
                i
            )

            p9R = rate(
                p9_r_hist,
                i
            )

            a02L = rate(
                a02_l_hist,
                i
            )

            a02R = rate(
                a02_r_hist,
                i
            )


            pursuit = max(
                0.0,
                p9L + p9R
                - P9_DEADZONE
            )


            speeds[i] = clamp(
                pursuit
                * SPEED_GAIN,

                0.0,
                MAX_SPEED
            )


            body_turn[i] = clamp(
                (
                    p9R - p9L
                )
                * BODY_TURN_GAIN,

                -MAX_BODY_TURN,
                MAX_BODY_TURN
            )


            turret_signal = (
                a02L - a02R
            )

            if (
                abs(turret_signal)
                < 1.0
            ):
                turret_signal = 0.0


            turret_turn[i] = clamp(
                -turret_signal
                * TURRET_GAIN,

                -MAX_TURRET_TURN,
                MAX_TURRET_TURN
            )


        # ----------------------------------------------------
        # MOVEMENT
        # ----------------------------------------------------

        for i in range(N):

            if not alive[i]:
                continue

            body[i] = wrap_angle(
                body[i]
                + body_turn[i]
                * brain.dt
            )

            turret[i] = wrap_angle(
                turret[i]
                + turret_turn[i]
                * brain.dt
            )

            rad = math.radians(
                body[i]
            )

            xs[i] += (
                math.sin(rad)
                * speeds[i]
                * brain.dt
            )

            ys[i] += (
                math.cos(rad)
                * speeds[i]
                * brain.dt
            )


        resolve_collisions(
            xs,
            ys,
            alive
        )


        # ----------------------------------------------------
        # PROJECTILES
        # ----------------------------------------------------

        remaining = []


        for p in projectiles:

            x1 = p["x"]
            y1 = p["y"]

            x2 = (
                x1
                + p["vx"]
                * brain.dt
            )

            y2 = (
                y1
                + p["vy"]
                * brain.dt
            )

            p["age"] += brain.dt


            victim = None
            victim_t = float("inf")


            for j in range(N):

                if (
                    not alive[j]
                    or
                    teams[j]
                    == p["team"]
                ):
                    continue


                hit_t = segment_circle_t(
                    x1,
                    y1,
                    x2,
                    y2,
                    xs[j],
                    ys[j],
                    TANK_RADIUS
                )


                if (
                    hit_t is not None
                    and
                    hit_t < victim_t
                ):

                    victim_t = hit_t
                    victim = j


            if victim is not None:

                owner = p["owner"]

                hits[owner] += 1

                hp[victim] -= 1


                if hp[victim] <= 0:

                    hp[victim] = 0
                    alive[victim] = False
                    kills[owner] += 1

                continue


            p["x"] = x2
            p["y"] = y2


            if (
                p["age"]
                < PROJECTILE_LIFETIME
                and
                0 <= x2 <= ARENA_W
                and
                0 <= y2 <= ARENA_H
            ):

                remaining.append(p)


        projectiles = remaining


        # ----------------------------------------------------
        # FIRE POLICY
        # ----------------------------------------------------

        for i in range(N):

            if (
                not alive[i]
                or
                targets[i] < 0
            ):
                continue


            if (
                sim_t
                - last_shot[i]
                < RELOAD_TIME
            ):
                continue


            eligible += 1

            j = targets[i]

            dx = xs[j] - xs[i]
            dy = ys[j] - ys[i]

            d = math.hypot(
                dx,
                dy
            )

            target_bearing = bearing(
                dx,
                dy
            )

            turret_world = wrap_angle(
                body[i]
                + turret[i]
            )

            aim_error = wrap_angle(
                target_bearing
                - turret_world
            )


            should_fire = False


            if mode == "auto":

                should_fire = (
                    d <= AUTO_FIRE_RANGE
                    and
                    abs(aim_error)
                    <= AUTO_FIRE_ERROR
                )


            elif mode == "learned":

                probability = float(
                    readout.predict(
                        activity[:, i]
                    )
                )

                learned_score_sum += (
                    probability
                )

                learned_score_n += 1

                should_fire = (
                    probability
                    >= FIRE_THRESHOLD
                )


            elif mode == "random":

                should_fire = (
                    rng.random()
                    < RANDOM_FIRE_PROB
                )


            if not should_fire:
                continue


            rad = math.radians(
                turret_world
            )

            projectiles.append({
                "x":
                    xs[i]
                    + math.sin(rad)
                    * (
                        TANK_RADIUS + 8
                    ),

                "y":
                    ys[i]
                    + math.cos(rad)
                    * (
                        TANK_RADIUS + 8
                    ),

                "vx":
                    math.sin(rad)
                    * PROJECTILE_SPEED,

                "vy":
                    math.cos(rad)
                    * PROJECTILE_SPEED,

                "team":
                    int(
                        teams[i]
                    ),

                "owner":
                    i,

                "age":
                    0.0,
            })


            shots[i] += 1
            last_shot[i] = sim_t


        sim_t += brain.dt


    blue_alive = int(
        alive[:4].sum()
    )

    red_alive = int(
        alive[4:].sum()
    )

    total_shots = int(
        shots.sum()
    )

    total_hits = int(
        hits.sum()
    )

    total_kills = int(
        kills.sum()
    )

    accuracy = (
        total_hits
        / total_shots
        if total_shots
        else 0.0
    )

    shots_per_kill = (
        total_shots
        / total_kills
        if total_kills
        else float("nan")
    )

    decisive = int(
        blue_alive == 0
        or red_alive == 0
    )

    return {
        "seed":
            seed,

        "mode":
            mode,

        "sim_time":
            sim_t,

        "shots":
            total_shots,

        "hits":
            total_hits,

        "kills":
            total_kills,

        "accuracy":
            accuracy,

        "shots_per_kill":
            shots_per_kill,

        "survivors":
            blue_alive
            + red_alive,

        "blue_survivors":
            blue_alive,

        "red_survivors":
            red_alive,

        "decisive":
            decisive,

        "eligible_fire_steps":
            eligible,

        "mean_learned_score":
            (
                learned_score_sum
                / learned_score_n
                if learned_score_n
                else float("nan")
            ),
    }


# ============================================================
# RUN PAIRED EXPERIMENT
# ============================================================

results = []


for seed in SEEDS:

    print()
    print("=" * 82)
    print(f"SEED {seed}")
    print("=" * 82)

    for mode in MODES:

        result = run_battle(
            seed,
            mode
        )

        results.append(
            result
        )

        print(
            f"{mode:8} | "
            f"t={result['sim_time']:5.1f}s | "
            f"shots={result['shots']:3d} | "
            f"hits={result['hits']:3d} | "
            f"acc={result['accuracy']*100:5.1f}% | "
            f"kills={result['kills']} | "
            f"survivors={result['survivors']}"
        )


# ============================================================
# SAVE RAW
# ============================================================

with open(
    CSV_PATH,
    "w",
    newline=""
) as f:

    writer = csv.DictWriter(
        f,
        fieldnames=results[0].keys()
    )

    writer.writeheader()
    writer.writerows(
        results
    )


# ============================================================
# SUMMARY
# ============================================================

print()
print()
print("=" * 110)
print("EXPERIMENT 010b — FIRE POLICY BENCHMARK")
print("=" * 110)

print(
    f"{'mode':10} | "
    f"{'pooled acc':>10} | "
    f"{'shots':>9} | "
    f"{'kills/battle':>13} | "
    f"{'shots/kill':>11} | "
    f"{'duration':>13} | "
    f"{'survivors':>13}"
)

print("-" * 110)


for mode in MODES:

    subset = [
        r
        for r in results
        if r["mode"] == mode
    ]

    total_shots = sum(
        r["shots"]
        for r in subset
    )

    total_hits = sum(
        r["hits"]
        for r in subset
    )

    total_kills = sum(
        r["kills"]
        for r in subset
    )

    pooled_accuracy = (
        total_hits
        / total_shots
        if total_shots
        else 0
    )

    kills_per_battle = [
        r["kills"]
        for r in subset
    ]

    durations = [
        r["sim_time"]
        for r in subset
    ]

    survivors = [
        r["survivors"]
        for r in subset
    ]

    shots_per_kill = (
        total_shots
        / total_kills
        if total_kills
        else float("nan")
    )


    print(
        f"{mode:10} | "
        f"{pooled_accuracy*100:9.1f}% | "
        f"{total_shots:9d} | "
        f"{mean(kills_per_battle):6.2f}"
        f"±{stdev(kills_per_battle):4.2f} | "
        f"{shots_per_kill:11.2f} | "
        f"{mean(durations):6.1f}"
        f"±{stdev(durations):4.1f} | "
        f"{mean(survivors):6.2f}"
        f"±{stdev(survivors):4.2f}"
    )


# ============================================================
# PAIRED PER-SEED ACCURACY DIFFERENCES
# ============================================================

def result_for(
    seed,
    mode
):

    return next(
        r
        for r in results
        if (
            r["seed"] == seed
            and
            r["mode"] == mode
        )
    )


learned_vs_random = []
learned_vs_auto = []


for seed in SEEDS:

    L = result_for(
        seed,
        "learned"
    )

    R = result_for(
        seed,
        "random"
    )

    A = result_for(
        seed,
        "auto"
    )

    learned_vs_random.append(
        L["accuracy"]
        - R["accuracy"]
    )

    learned_vs_auto.append(
        L["accuracy"]
        - A["accuracy"]
    )


print()
print("Paired accuracy differences:")

print(
    "LEARNED - RANDOM : "
    f"{mean(learned_vs_random)*100:+.1f}"
    f" ± {stdev(learned_vs_random)*100:.1f} pp"
)

print(
    "LEARNED - AUTO   : "
    f"{mean(learned_vs_auto)*100:+.1f}"
    f" ± {stdev(learned_vs_auto)*100:.1f} pp"
)


print()
print(
    f"Saved to {CSV_PATH}"
)
