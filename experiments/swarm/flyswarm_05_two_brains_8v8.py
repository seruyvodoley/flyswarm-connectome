from flybrain import FlyBrain

from collections import Counter, deque
from pathlib import Path
from statistics import mean, stdev

import csv
import math
import time
import numpy as np


# ============================================================
# FLYSWARM 0.5
# TWO SEPARATE BRAINS, EACH FlyBrain(batch=8)
# BLUE 8 vs RED 8
#
# Conditions:
#   no_audio   - no inter-agent auditory coupling
#   team_audio - hear only teammates
#   all_audio  - hear every other living fly
#
# Combat remains AUTO-FIRE in every condition so the only
# experimental manipulation is the auditory topology.
# ============================================================

N_TEAM = 8
N_TOTAL = 16

BLUE_OFFSET = 0
RED_OFFSET = 8

CALIBRATION_SEEDS = [200, 201]

TEST_SEEDS = [
    204,
    205,
    206,
    207,
    208,
    209,
]

CONDITIONS = [
    "no_audio",
    "team_audio",
    "all_audio",
]

SIM_DURATION = 45.0

ARENA_W = 1200.0
ARENA_H = 760.0

WARMUP_STEPS = 25
REST_STEPS = 100
RATE_WINDOW = 10

STIMULUS = 0.8

DETECTION_RANGE = 760.0

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

RELOAD_TIME = 1.40
FIRE_RANGE = 560.0
FIRE_ERROR_DEG = 4.0

PROJECTILE_SPEED = 280.0
PROJECTILE_LIFETIME = 3.0

EAR_CAP = 0.8
AUDIO_DISTANCE_SCALE = 250.0

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

RAW_PATH = RESULTS / "flyswarm_05_two_brains_8v8_raw.csv"
SUMMARY_PATH = RESULTS / "flyswarm_05_two_brains_8v8_summary.csv"


# Exact wing-MN set used by the upstream talking-flies experiment.
WING_MN = [
    "DLMn a, b",
    "DLMn c-f",
    "DVMn 1a-c",
    "DVMn 2a, b",
    "DVMn 3a, b",
    "MNwm35",
    "MNwm36",
    "b1 MN",
    "b2 MN",
    "b3 MN",
    "hg1 MN",
    "hg2 MN",
    "hg3 MN",
    "hg4 MN",
    "i1 MN",
    "i2 MN",
    "iii1 MN",
    "iii3 MN",
    "ps1 MN",
    "tp1 MN",
    "tp2 MN",
    "tpn MN",
]


# ============================================================
# MATH
# ============================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def wrap_angle(a):
    while a > 180.0:
        a -= 360.0

    while a < -180.0:
        a += 360.0

    return a


def bearing(dx, dy):
    # 0 deg = +Y
    return math.degrees(
        math.atan2(dx, dy)
    )


def distance(ax, ay, bx, by):
    return math.hypot(
        bx - ax,
        by - ay,
    )


def segment_circle_t(
    x1,
    y1,
    x2,
    y2,
    cx,
    cy,
    radius,
):
    vx = x2 - x1
    vy = y2 - y1

    wx = cx - x1
    wy = cy - y1

    vv = vx * vx + vy * vy

    if vv <= 1e-12:
        return None

    t = (
        wx * vx
        + wy * vy
    ) / vv

    t = clamp(
        t,
        0.0,
        1.0,
    )

    px = x1 + vx * t
    py = y1 + vy * t

    if (
        math.hypot(
            px - cx,
            py - cy,
        )
        <= radius
    ):
        return t

    return None


def attenuation(d):
    x = (
        d
        / AUDIO_DISTANCE_SCALE
    )

    return (
        1.0
        / (1.0 + x * x)
    )


# ============================================================
# BRAIN WRAPPER
# ============================================================

class TeamBrain:
    def __init__(
        self,
        name,
        initial_seed,
    ):
        self.name = name

        print(
            f"Loading {name} FlyBrain(batch=8)..."
        )

        self.brain = FlyBrain(
            device="cpu",
            batch=N_TEAM,
            seed=initial_seed,
        )

        self.dt = self.brain.dt

        # visual sensory populations
        self.lc9_l = self.brain.cells(
            ["LC9"],
            side="L",
        )

        self.lc9_r = self.brain.cells(
            ["LC9"],
            side="R",
        )

        self.lc10_l = self.brain.cells(
            ["LC10a"],
            side="L",
        )

        self.lc10_r = self.brain.cells(
            ["LC10a"],
            side="R",
        )

        # auditory sensory population
        ear_types = sorted({
            str(t)
            for t in np.unique(
                self.brain.cell_type
            )
            if (
                str(t).startswith("JO-A")
                or
                str(t).startswith("JO-B")
            )
        })

        self.ear = self.brain.cells(
            ear_types
        )

        # wing motor neurons
        self.wing = self.brain.cells(
            WING_MN
        )

        self.wing_mask = np.zeros(
            self.brain.n,
            dtype=bool,
        )

        self.wing_mask[
            self.wing
        ] = True

        # natural motor readouts
        self.p9_l = set(
            self.brain.cells(
                ["DNp09"],
                side="L",
            )
        )

        self.p9_r = set(
            self.brain.cells(
                ["DNp09"],
                side="R",
            )
        )

        self.a02_l = set(
            self.brain.cells(
                ["DNa02"],
                side="L",
            )
        )

        self.a02_r = set(
            self.brain.cells(
                ["DNa02"],
                side="R",
            )
        )

        # probes
        self.p01 = set(
            self.brain.cells(
                ["DNp01"]
            )
        )

        self.descending = self.brain.cells(
            ["descending_neuron"]
        )

        self.descending_mask = np.zeros(
            self.brain.n,
            dtype=bool,
        )

        self.descending_mask[
            self.descending
        ] = True

        if len(self.wing) == 0:
            raise RuntimeError(
                f"{name}: no WING_MN neurons found."
            )

        if len(self.ear) == 0:
            raise RuntimeError(
                f"{name}: no JO-A/JO-B neurons found."
            )

        print(
            f"  neurons/fly      : {self.brain.n:,}"
        )

        print(
            f"  wing MN          : {len(self.wing)}"
        )

        print(
            f"  JO-A/JO-B        : {len(self.ear)}"
        )

        print(
            f"  descending       : {len(self.descending)}"
        )

    def reset(
        self,
        seed,
    ):
        self.brain.reset(
            seed
        )

    def warmup(self):
        for _ in range(
            WARMUP_STEPS
        ):
            self.brain.step()

    def wing_counts(
        self,
        fired_by_fly,
    ):
        out = np.zeros(
            N_TEAM,
            dtype=np.float32,
        )

        for i, fired in enumerate(
            fired_by_fly
        ):
            out[i] = float(
                self.wing_mask[
                    fired
                ].sum()
            )

        return out

    def descending_counts(
        self,
        fired_by_fly,
    ):
        out = np.zeros(
            N_TEAM,
            dtype=np.float32,
        )

        for i, fired in enumerate(
            fired_by_fly
        ):
            out[i] = float(
                self.descending_mask[
                    fired
                ].sum()
            )

        return out


print(
    "============================================================"
)

print(
    "FLYSWARM 0.5 — TWO SEPARATE TEAM BRAINS"
)

print(
    "============================================================"
)


load_start = time.perf_counter()

blue = TeamBrain(
    "BLUE",
    CALIBRATION_SEEDS[0],
)

red = TeamBrain(
    "RED",
    CALIBRATION_SEEDS[0] + 1000,
)

if abs(
    blue.dt
    - red.dt
) > 1e-12:
    raise RuntimeError(
        "BLUE and RED brains have different dt."
    )

DT = blue.dt

print()
print(
    f"Total logical agents       : {N_TOTAL}"
)

print(
    f"Total simulated neurons    : "
    f"{blue.brain.n * N_TEAM + red.brain.n * N_TEAM:,}"
)

print(
    f"Brain load wall time       : "
    f"{time.perf_counter() - load_start:.2f}s"
)

print(
    f"dt                         : "
    f"{DT:.3f}s"
)


# ============================================================
# WORLD
# ============================================================

TEAMS = np.array(
    [0] * N_TEAM
    + [1] * N_TEAM,
    dtype=int,
)

NAMES = (
    [
        f"B{i + 1}"
        for i in range(N_TEAM)
    ]
    +
    [
        f"R{i + 1}"
        for i in range(N_TEAM)
    ]
)


def create_world():
    x_line = np.linspace(
        100.0,
        ARENA_W - 100.0,
        N_TEAM,
    )

    blue_y = np.array([
        100.0,
        125.0,
        100.0,
        125.0,
        100.0,
        125.0,
        100.0,
        125.0,
    ])

    red_y = np.array([
        ARENA_H - 100.0,
        ARENA_H - 125.0,
        ARENA_H - 100.0,
        ARENA_H - 125.0,
        ARENA_H - 100.0,
        ARENA_H - 125.0,
        ARENA_H - 100.0,
        ARENA_H - 125.0,
    ])

    xs = np.concatenate([
        x_line.copy(),
        x_line.copy(),
    ])

    ys = np.concatenate([
        blue_y,
        red_y,
    ])

    body_yaw = np.concatenate([
        np.zeros(
            N_TEAM,
            dtype=float,
        ),
        np.full(
            N_TEAM,
            180.0,
            dtype=float,
        ),
    ])

    turret_relative = np.zeros(
        N_TOTAL,
        dtype=float,
    )

    alive = np.ones(
        N_TOTAL,
        dtype=bool,
    )

    hp = np.full(
        N_TOTAL,
        MAX_HP,
        dtype=int,
    )

    last_shot = np.full(
        N_TOTAL,
        -999.0,
        dtype=float,
    )

    return (
        xs,
        ys,
        body_yaw,
        turret_relative,
        alive,
        hp,
        last_shot,
    )


# ============================================================
# MOTOR HISTORY
# ============================================================

def make_histories():
    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW,
        )
        for _ in range(
            N_TEAM
        )
    ]


def population_rate(
    histories,
    i,
):
    return (
        sum(
            histories[i]
        )
        /
        (
            len(histories[i])
            * DT
        )
    )


def new_motor_histories():
    return {
        "p9_l": make_histories(),
        "p9_r": make_histories(),
        "a02_l": make_histories(),
        "a02_r": make_histories(),
    }


# ============================================================
# TARGETING
# ============================================================

def choose_target(
    i,
    xs,
    ys,
    body_yaw,
    alive,
):
    if not alive[i]:
        return -1

    my_team = TEAMS[i]

    best = -1
    best_distance = float(
        "inf"
    )

    for j in range(
        N_TOTAL
    ):
        if (
            not alive[j]
            or
            TEAMS[j] == my_team
        ):
            continue

        dx = (
            xs[j]
            - xs[i]
        )

        dy = (
            ys[j]
            - ys[i]
        )

        d = math.hypot(
            dx,
            dy,
        )

        if (
            d
            > DETECTION_RANGE
        ):
            continue

        error = wrap_angle(
            bearing(
                dx,
                dy,
            )
            - body_yaw[i]
        )

        if (
            abs(error)
            > BODY_FOV / 2.0
        ):
            continue

        if (
            d
            < best_distance
        ):
            best = j
            best_distance = d

    return best


# ============================================================
# COLLISION PHYSICS
# ============================================================

def resolve_collisions(
    xs,
    ys,
    alive,
):
    minimum = (
        TANK_RADIUS
        * 2.0
    )

    for i in range(
        N_TOTAL
    ):
        if not alive[i]:
            continue

        for j in range(
            i + 1,
            N_TOTAL,
        ):
            if not alive[j]:
                continue

            dx = (
                xs[j]
                - xs[i]
            )

            dy = (
                ys[j]
                - ys[i]
            )

            d = math.hypot(
                dx,
                dy,
            )

            if (
                d
                >= minimum
            ):
                continue

            if d < 1e-6:
                dx = 1.0
                dy = 0.0
                d = 1.0

            overlap = (
                minimum
                - d
            )

            nx = dx / d
            ny = dy / d

            push = (
                overlap
                / 2.0
            )

            xs[i] -= (
                nx * push
            )

            ys[i] -= (
                ny * push
            )

            xs[j] += (
                nx * push
            )

            ys[j] += (
                ny * push
            )

    for i in range(
        N_TOTAL
    ):
        xs[i] = clamp(
            xs[i],
            TANK_RADIUS,
            ARENA_W
            - TANK_RADIUS,
        )

        ys[i] = clamp(
            ys[i],
            TANK_RADIUS,
            ARENA_H
            - TANK_RADIUS,
        )


# ============================================================
# GROUP-BEHAVIOUR METRICS
# ============================================================

def target_metrics(
    team,
    targets,
    alive,
):
    attackers = [
        i
        for i in range(
            N_TOTAL
        )
        if (
            TEAMS[i] == team
            and alive[i]
            and targets[i] >= 0
        )
    ]

    if not attackers:
        return (
            0.0,
            0.0,
            0.0,
        )

    counts = Counter(
        int(
            targets[i]
        )
        for i in attackers
    )

    focus = float(
        max(
            counts.values()
        )
    )

    coverage = float(
        len(counts)
    )

    n = sum(
        counts.values()
    )

    if n <= 1:
        entropy_norm = 0.0

    else:
        probs = np.asarray(
            list(
                counts.values()
            ),
            dtype=float,
        )

        probs /= probs.sum()

        entropy = float(
            -np.sum(
                probs
                * np.log2(
                    probs
                )
            )
        )

        entropy_norm = (
            entropy
            / math.log2(n)
        )

    return (
        focus,
        coverage,
        entropy_norm,
    )


def mean_team_pair_distance(
    team,
    xs,
    ys,
    alive,
):
    members = [
        i
        for i in range(
            N_TOTAL
        )
        if (
            TEAMS[i] == team
            and alive[i]
        )
    ]

    values = []

    for a in range(
        len(members)
    ):
        for b in range(
            a + 1,
            len(members),
        ):
            i = members[a]
            j = members[b]

            values.append(
                distance(
                    xs[i],
                    ys[i],
                    xs[j],
                    ys[j],
                )
            )

    if not values:
        return float(
            "nan"
        )

    return float(
        np.mean(
            values
        )
    )


# ============================================================
# AUDIO PROPAGATION
# ============================================================

def raw_heard_signal(
    sender_sound,
    xs,
    ys,
    alive,
    mode,
):
    """
    sender_sound has 16 values:
      0..7  BLUE wing song
      8..15 RED wing song

    mode:
      team_audio -> same-team senders only
      all_audio  -> every other living sender
    """
    heard = np.zeros(
        N_TOTAL,
        dtype=np.float32,
    )

    if mode == "no_audio":
        return heard

    for receiver in range(
        N_TOTAL
    ):
        if not alive[receiver]:
            continue

        total = 0.0

        for sender in range(
            N_TOTAL
        ):
            if (
                sender == receiver
                or
                not alive[sender]
            ):
                continue

            if (
                mode == "team_audio"
                and
                TEAMS[sender]
                != TEAMS[receiver]
            ):
                continue

            d = distance(
                xs[receiver],
                ys[receiver],
                xs[sender],
                ys[sender],
            )

            total += (
                sender_sound[sender]
                * attenuation(d)
            )

        heard[receiver] = total

    return heard


# ============================================================
# VISUAL INPUT
# ============================================================

def visual_inputs_for_team(
    offset,
    targets,
    body_errors,
    turret_errors,
    alive,
):
    lc9_l_amount = np.zeros(
        N_TEAM,
        dtype=np.float32,
    )

    lc9_r_amount = np.zeros(
        N_TEAM,
        dtype=np.float32,
    )

    lc10_l_amount = np.zeros(
        N_TEAM,
        dtype=np.float32,
    )

    lc10_r_amount = np.zeros(
        N_TEAM,
        dtype=np.float32,
    )

    for local_i in range(
        N_TEAM
    ):
        i = (
            offset
            + local_i
        )

        if (
            not alive[i]
            or
            targets[i] < 0
        ):
            continue

        e = body_errors[i]

        if (
            e
            < -BODY_DEADZONE
        ):
            lc9_l_amount[
                local_i
            ] = STIMULUS

        elif (
            e
            > BODY_DEADZONE
        ):
            lc9_r_amount[
                local_i
            ] = STIMULUS

        else:
            lc9_l_amount[
                local_i
            ] = STIMULUS

            lc9_r_amount[
                local_i
            ] = STIMULUS

        te = turret_errors[i]

        if (
            abs(te)
            <= TURRET_FOV / 2.0
        ):
            if (
                te
                < -TURRET_DEADZONE
            ):
                lc10_l_amount[
                    local_i
                ] = STIMULUS

            elif (
                te
                > TURRET_DEADZONE
            ):
                lc10_r_amount[
                    local_i
                ] = STIMULUS

    return (
        lc9_l_amount,
        lc9_r_amount,
        lc10_l_amount,
        lc10_r_amount,
    )


# ============================================================
# NATURAL MOTOR DECODER
# ============================================================

def decode_team(
    pack,
    fired_by_fly,
    histories,
    alive_local,
):
    speeds = np.zeros(
        N_TEAM,
        dtype=float,
    )

    body_turn = np.zeros(
        N_TEAM,
        dtype=float,
    )

    turret_turn = np.zeros(
        N_TEAM,
        dtype=float,
    )

    p01_spike_count = 0

    for local_i in range(
        N_TEAM
    ):
        fired = set(
            fired_by_fly[
                local_i
            ]
        )

        histories[
            "p9_l"
        ][local_i].append(
            len(
                fired.intersection(
                    pack.p9_l
                )
            )
        )

        histories[
            "p9_r"
        ][local_i].append(
            len(
                fired.intersection(
                    pack.p9_r
                )
            )
        )

        histories[
            "a02_l"
        ][local_i].append(
            len(
                fired.intersection(
                    pack.a02_l
                )
            )
        )

        histories[
            "a02_r"
        ][local_i].append(
            len(
                fired.intersection(
                    pack.a02_r
                )
            )
        )

        if not alive_local[
            local_i
        ]:
            continue

        p01_spike_count += len(
            fired.intersection(
                pack.p01
            )
        )

        p9L = population_rate(
            histories[
                "p9_l"
            ],
            local_i,
        )

        p9R = population_rate(
            histories[
                "p9_r"
            ],
            local_i,
        )

        a02L = population_rate(
            histories[
                "a02_l"
            ],
            local_i,
        )

        a02R = population_rate(
            histories[
                "a02_r"
            ],
            local_i,
        )

        pursuit = max(
            0.0,
            p9L
            + p9R
            - P9_DEADZONE,
        )

        speeds[
            local_i
        ] = clamp(
            pursuit
            * SPEED_GAIN,
            0.0,
            MAX_SPEED,
        )

        body_turn[
            local_i
        ] = clamp(
            (
                p9R
                - p9L
            )
            * BODY_TURN_GAIN,
            -MAX_BODY_TURN,
            MAX_BODY_TURN,
        )

        turret_signal = (
            a02L
            - a02R
        )

        if (
            abs(
                turret_signal
            )
            < 1.0
        ):
            turret_signal = 0.0

        turret_turn[
            local_i
        ] = clamp(
            -turret_signal
            * TURRET_GAIN,
            -MAX_TURRET_TURN,
            MAX_TURRET_TURN,
        )

    return (
        speeds,
        body_turn,
        turret_turn,
        p01_spike_count,
    )


# ============================================================
# RESTING WING CALIBRATION
# ============================================================

print()
print(
    "============================================================"
)

print(
    "CALIBRATION 1 — RESTING WING ACTIVITY"
)

print(
    "============================================================"
)


rest_blue = []
rest_red = []


for seed in CALIBRATION_SEEDS:
    blue.reset(
        seed
    )

    red.reset(
        seed + 1000
    )

    blue.warmup()
    red.warmup()

    for _ in range(
        REST_STEPS
    ):
        fired_blue = (
            blue.brain.step()
        )

        fired_red = (
            red.brain.step()
        )

        rest_blue.extend(
            blue.wing_counts(
                fired_blue
            ).tolist()
        )

        rest_red.extend(
            red.wing_counts(
                fired_red
            ).tolist()
        )


REST_WING_BLUE = float(
    np.mean(
        rest_blue
    )
)

REST_WING_RED = float(
    np.mean(
        rest_red
    )
)


print(
    f"BLUE rest wing     : "
    f"{REST_WING_BLUE:.4f}"
)

print(
    f"RED rest wing      : "
    f"{REST_WING_RED:.4f}"
)


# ============================================================
# BATTLE
# ============================================================

def run_battle(
    seed,
    condition,
    ear_gain,
    collect_potential_audio=False,
):
    if condition not in CONDITIONS:
        raise ValueError(
            condition
        )

    blue.reset(
        seed
    )

    red.reset(
        seed + 1000
    )

    blue.warmup()
    red.warmup()

    (
        xs,
        ys,
        body_yaw,
        turret_relative,
        alive,
        hp,
        last_shot,
    ) = create_world()

    targets = np.full(
        N_TOTAL,
        -1,
        dtype=int,
    )

    previous_targets = np.full(
        N_TOTAL,
        -1,
        dtype=int,
    )

    hist_blue = (
        new_motor_histories()
    )

    hist_red = (
        new_motor_histories()
    )

    previous_sender_sound = np.zeros(
        N_TOTAL,
        dtype=np.float32,
    )

    projectiles = []

    shots = np.zeros(
        N_TOTAL,
        dtype=int,
    )

    hits = np.zeros(
        N_TOTAL,
        dtype=int,
    )

    kills = np.zeros(
        N_TOTAL,
        dtype=int,
    )

    target_switches = np.zeros(
        N_TOTAL,
        dtype=int,
    )

    focus_sum = np.zeros(
        2,
        dtype=float,
    )

    focus_steps = np.zeros(
        2,
        dtype=int,
    )

    focus_max = np.zeros(
        2,
        dtype=int,
    )

    coverage_sum = np.zeros(
        2,
        dtype=float,
    )

    entropy_sum = np.zeros(
        2,
        dtype=float,
    )

    spread_sum = np.zeros(
        2,
        dtype=float,
    )

    spread_steps = np.zeros(
        2,
        dtype=int,
    )

    heard_positive = 0
    heard_samples = 0
    heard_sum = 0.0
    heard_max = 0.0

    potential_raw = []

    song_sum = 0.0
    song_samples = 0

    dn_spikes = 0.0
    dn_fly_steps = 0

    p01_spikes = 0.0
    p01_neuron_steps = 0

    sim_t = 0.0

    wall_start = (
        time.perf_counter()
    )

    # ========================================================
    # LOOP
    # ========================================================

    while (
        sim_t
        < SIM_DURATION
    ):
        blue_alive = int(
            alive[
                :N_TEAM
            ].sum()
        )

        red_alive = int(
            alive[
                N_TEAM:
            ].sum()
        )

        if (
            blue_alive == 0
            or red_alive == 0
        ):
            break

        # ----------------------------------------------------
        # PERCEPTION
        # ----------------------------------------------------

        body_errors = np.zeros(
            N_TOTAL,
            dtype=float,
        )

        turret_errors = np.zeros(
            N_TOTAL,
            dtype=float,
        )

        for i in range(
            N_TOTAL
        ):
            targets[i] = (
                choose_target(
                    i,
                    xs,
                    ys,
                    body_yaw,
                    alive,
                )
            )

            if (
                previous_targets[i] >= 0
                and
                targets[i] >= 0
                and
                previous_targets[i]
                != targets[i]
            ):
                target_switches[i] += 1

            previous_targets[i] = (
                targets[i]
            )

            j = targets[i]

            if j < 0:
                continue

            dx = (
                xs[j]
                - xs[i]
            )

            dy = (
                ys[j]
                - ys[i]
            )

            target_bearing = (
                bearing(
                    dx,
                    dy,
                )
            )

            body_errors[i] = (
                wrap_angle(
                    target_bearing
                    - body_yaw[i]
                )
            )

            turret_world = (
                wrap_angle(
                    body_yaw[i]
                    + turret_relative[i]
                )
            )

            turret_errors[i] = (
                wrap_angle(
                    target_bearing
                    - turret_world
                )
            )

        # ----------------------------------------------------
        # COLLECTIVE METRICS
        # ----------------------------------------------------

        for team in [0, 1]:
            (
                focus,
                coverage,
                entropy_norm,
            ) = target_metrics(
                team,
                targets,
                alive,
            )

            if coverage > 0:
                focus_sum[
                    team
                ] += focus

                coverage_sum[
                    team
                ] += coverage

                entropy_sum[
                    team
                ] += entropy_norm

                focus_steps[
                    team
                ] += 1

                focus_max[
                    team
                ] = max(
                    focus_max[
                        team
                    ],
                    int(
                        focus
                    ),
                )

            spread = (
                mean_team_pair_distance(
                    team,
                    xs,
                    ys,
                    alive,
                )
            )

            if not math.isnan(
                spread
            ):
                spread_sum[
                    team
                ] += spread

                spread_steps[
                    team
                ] += 1

        # ----------------------------------------------------
        # VISUAL INPUTS
        # ----------------------------------------------------

        blue_visual = (
            visual_inputs_for_team(
                BLUE_OFFSET,
                targets,
                body_errors,
                turret_errors,
                alive,
            )
        )

        red_visual = (
            visual_inputs_for_team(
                RED_OFFSET,
                targets,
                body_errors,
                turret_errors,
                alive,
            )
        )

        # ----------------------------------------------------
        # AUDIO
        # ----------------------------------------------------
        #
        # Communication is causal:
        # current JO input comes from wing song generated
        # on the PREVIOUS brain step.
        # ----------------------------------------------------

        if collect_potential_audio:
            raw_for_calibration = (
                raw_heard_signal(
                    previous_sender_sound,
                    xs,
                    ys,
                    alive,
                    "all_audio",
                )
            )

            potential_raw.extend(
                raw_for_calibration[
                    alive
                ].tolist()
            )

        raw_heard = (
            raw_heard_signal(
                previous_sender_sound,
                xs,
                ys,
                alive,
                condition,
            )
        )

        if condition == "no_audio":
            ear_amount = np.zeros(
                N_TOTAL,
                dtype=np.float32,
            )

        else:
            ear_amount = np.minimum(
                raw_heard
                * ear_gain,
                EAR_CAP,
            ).astype(
                np.float32
            )

        ear_amount[
            ~alive
        ] = 0.0

        if condition != "no_audio":
            heard_positive += int(
                np.count_nonzero(
                    ear_amount[
                        alive
                    ] > 0
                )
            )

            heard_samples += int(
                alive.sum()
            )

            heard_sum += float(
                ear_amount[
                    alive
                ].sum()
            )

            if np.any(
                alive
            ):
                heard_max = max(
                    heard_max,
                    float(
                        ear_amount[
                            alive
                        ].max()
                    ),
                )

        # ----------------------------------------------------
        # STEP BLUE + RED BRAINS
        # ----------------------------------------------------

        fired_blue = blue.brain.step(
            inject=[
                (
                    blue.lc9_l,
                    blue_visual[0],
                ),
                (
                    blue.lc9_r,
                    blue_visual[1],
                ),
                (
                    blue.lc10_l,
                    blue_visual[2],
                ),
                (
                    blue.lc10_r,
                    blue_visual[3],
                ),
                (
                    blue.ear,
                    ear_amount[
                        :N_TEAM
                    ],
                ),
            ]
        )

        fired_red = red.brain.step(
            inject=[
                (
                    red.lc9_l,
                    red_visual[0],
                ),
                (
                    red.lc9_r,
                    red_visual[1],
                ),
                (
                    red.lc10_l,
                    red_visual[2],
                ),
                (
                    red.lc10_r,
                    red_visual[3],
                ),
                (
                    red.ear,
                    ear_amount[
                        N_TEAM:
                    ],
                ),
            ]
        )

        # ----------------------------------------------------
        # NEW WING SONG
        # ----------------------------------------------------

        blue_wing = (
            blue.wing_counts(
                fired_blue
            )
        )

        red_wing = (
            red.wing_counts(
                fired_red
            )
        )

        blue_sound = np.maximum(
            blue_wing
            - REST_WING_BLUE,
            0.0,
        )

        red_sound = np.maximum(
            red_wing
            - REST_WING_RED,
            0.0,
        )

        blue_sound[
            ~alive[:N_TEAM]
        ] = 0.0

        red_sound[
            ~alive[N_TEAM:]
        ] = 0.0

        previous_sender_sound = (
            np.concatenate([
                blue_sound,
                red_sound,
            ])
            .astype(
                np.float32
            )
        )

        song_sum += float(
            previous_sender_sound.sum()
        )

        song_samples += int(
            alive.sum()
        )

        # ----------------------------------------------------
        # INTERNAL PROBES
        # ----------------------------------------------------

        blue_dn = (
            blue.descending_counts(
                fired_blue
            )
        )

        red_dn = (
            red.descending_counts(
                fired_red
            )
        )

        dn_spikes += float(
            blue_dn[
                alive[:N_TEAM]
            ].sum()
        )

        dn_spikes += float(
            red_dn[
                alive[N_TEAM:]
            ].sum()
        )

        dn_fly_steps += int(
            alive.sum()
        )

        # ----------------------------------------------------
        # NATURAL MOTOR OUTPUTS
        # ----------------------------------------------------

        (
            blue_speed,
            blue_body_turn,
            blue_turret_turn,
            blue_p01_spikes,
        ) = decode_team(
            blue,
            fired_blue,
            hist_blue,
            alive[:N_TEAM],
        )

        (
            red_speed,
            red_body_turn,
            red_turret_turn,
            red_p01_spikes,
        ) = decode_team(
            red,
            fired_red,
            hist_red,
            alive[N_TEAM:],
        )

        p01_spikes += (
            blue_p01_spikes
            + red_p01_spikes
        )

        p01_neuron_steps += (
            int(
                alive[:N_TEAM].sum()
            )
            * max(
                1,
                len(
                    blue.p01
                )
            )
        )

        p01_neuron_steps += (
            int(
                alive[N_TEAM:].sum()
            )
            * max(
                1,
                len(
                    red.p01
                )
            )
        )

        speeds = np.concatenate([
            blue_speed,
            red_speed,
        ])

        body_turn = np.concatenate([
            blue_body_turn,
            red_body_turn,
        ])

        turret_turn = np.concatenate([
            blue_turret_turn,
            red_turret_turn,
        ])

        # ----------------------------------------------------
        # MOVEMENT
        # ----------------------------------------------------

        for i in range(
            N_TOTAL
        ):
            if not alive[i]:
                continue

            body_yaw[i] = (
                wrap_angle(
                    body_yaw[i]
                    + body_turn[i]
                    * DT
                )
            )

            turret_relative[i] = (
                wrap_angle(
                    turret_relative[i]
                    + turret_turn[i]
                    * DT
                )
            )

            rad = math.radians(
                body_yaw[i]
            )

            xs[i] += (
                math.sin(rad)
                * speeds[i]
                * DT
            )

            ys[i] += (
                math.cos(rad)
                * speeds[i]
                * DT
            )

        resolve_collisions(
            xs,
            ys,
            alive,
        )

        # ----------------------------------------------------
        # PROJECTILES
        # ----------------------------------------------------

        remaining = []

        for p in projectiles:
            old_x = p["x"]
            old_y = p["y"]

            new_x = (
                old_x
                + p["vx"]
                * DT
            )

            new_y = (
                old_y
                + p["vy"]
                * DT
            )

            p["age"] += DT

            victim = None
            best_t = float(
                "inf"
            )

            for j in range(
                N_TOTAL
            ):
                if (
                    not alive[j]
                    or
                    TEAMS[j]
                    == p["team"]
                ):
                    continue

                hit_t = (
                    segment_circle_t(
                        old_x,
                        old_y,
                        new_x,
                        new_y,
                        xs[j],
                        ys[j],
                        TANK_RADIUS,
                    )
                )

                if (
                    hit_t is not None
                    and
                    hit_t < best_t
                ):
                    best_t = hit_t
                    victim = j

            if victim is not None:
                owner = p["owner"]

                hits[
                    owner
                ] += 1

                hp[
                    victim
                ] -= 1

                if (
                    hp[
                        victim
                    ]
                    <= 0
                ):
                    hp[
                        victim
                    ] = 0

                    alive[
                        victim
                    ] = False

                    kills[
                        owner
                    ] += 1

                continue

            p["x"] = new_x
            p["y"] = new_y

            if (
                p["age"]
                < PROJECTILE_LIFETIME
                and
                0.0 <= new_x <= ARENA_W
                and
                0.0 <= new_y <= ARENA_H
            ):
                remaining.append(
                    p
                )

        projectiles = remaining

        # ----------------------------------------------------
        # AUTO FIRE
        # ----------------------------------------------------
        #
        # Identical in all three conditions.
        # ----------------------------------------------------

        for i in range(
            N_TOTAL
        ):
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

            j = targets[i]

            if not alive[j]:
                continue

            dx = (
                xs[j]
                - xs[i]
            )

            dy = (
                ys[j]
                - ys[i]
            )

            d = math.hypot(
                dx,
                dy,
            )

            target_bearing = (
                bearing(
                    dx,
                    dy,
                )
            )

            turret_world = (
                wrap_angle(
                    body_yaw[i]
                    + turret_relative[i]
                )
            )

            aim_error = (
                wrap_angle(
                    target_bearing
                    - turret_world
                )
            )

            if not (
                d <= FIRE_RANGE
                and
                abs(
                    aim_error
                )
                <= FIRE_ERROR_DEG
            ):
                continue

            rad = math.radians(
                turret_world
            )

            projectiles.append({
                "x":
                    xs[i]
                    + math.sin(rad)
                    * (
                        TANK_RADIUS
                        + 8.0
                    ),

                "y":
                    ys[i]
                    + math.cos(rad)
                    * (
                        TANK_RADIUS
                        + 8.0
                    ),

                "vx":
                    math.sin(rad)
                    * PROJECTILE_SPEED,

                "vy":
                    math.cos(rad)
                    * PROJECTILE_SPEED,

                "team":
                    int(
                        TEAMS[i]
                    ),

                "owner":
                    i,

                "age":
                    0.0,
            })

            shots[
                i
            ] += 1

            last_shot[
                i
            ] = sim_t

        sim_t += DT

    # ========================================================
    # BATTLE SUMMARY
    # ========================================================

    blue_survivors = int(
        alive[
            :N_TEAM
        ].sum()
    )

    red_survivors = int(
        alive[
            N_TEAM:
        ].sum()
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

    def team_mean(
        accumulator,
        team,
    ):
        if (
            focus_steps[
                team
            ] == 0
        ):
            return 0.0

        return (
            accumulator[
                team
            ]
            /
            focus_steps[
                team
            ]
        )

    mean_focus = float(
        np.mean([
            team_mean(
                focus_sum,
                0,
            ),
            team_mean(
                focus_sum,
                1,
            ),
        ])
    )

    mean_coverage = float(
        np.mean([
            team_mean(
                coverage_sum,
                0,
            ),
            team_mean(
                coverage_sum,
                1,
            ),
        ])
    )

    mean_entropy = float(
        np.mean([
            team_mean(
                entropy_sum,
                0,
            ),
            team_mean(
                entropy_sum,
                1,
            ),
        ])
    )

    spreads = []

    for team in [0, 1]:
        if (
            spread_steps[
                team
            ]
            > 0
        ):
            spreads.append(
                spread_sum[
                    team
                ]
                /
                spread_steps[
                    team
                ]
            )

    mean_spread = (
        float(
            np.mean(
                spreads
            )
        )
        if spreads
        else float(
            "nan"
        )
    )

    mean_heard = (
        heard_sum
        / heard_samples
        if heard_samples
        else 0.0
    )

    heard_pct = (
        heard_positive
        / heard_samples
        * 100.0
        if heard_samples
        else 0.0
    )

    mean_song = (
        song_sum
        / song_samples
        if song_samples
        else 0.0
    )

    mean_dn_hz = (
        dn_spikes
        / dn_fly_steps
        / DT
        if dn_fly_steps
        else 0.0
    )

    mean_p01_hz = (
        p01_spikes
        / p01_neuron_steps
        / DT
        if p01_neuron_steps
        else 0.0
    )

    wall_time = (
        time.perf_counter()
        - wall_start
    )

    return {
        "seed":
            seed,

        "condition":
            condition,

        "sim_time":
            sim_t,

        "wall_time":
            wall_time,

        "realtime_factor":
            (
                sim_t
                / wall_time
                if wall_time
                else 0.0
            ),

        "shots":
            total_shots,

        "hits":
            total_hits,

        "accuracy":
            accuracy,

        "kills":
            total_kills,

        "survivors":
            blue_survivors
            + red_survivors,

        "blue_survivors":
            blue_survivors,

        "red_survivors":
            red_survivors,

        "focus":
            mean_focus,

        "focus_max":
            int(
                max(
                    focus_max
                )
            ),

        "coverage":
            mean_coverage,

        "target_entropy":
            mean_entropy,

        "target_switches":
            int(
                target_switches.sum()
            ),

        "spread":
            mean_spread,

        "mean_heard":
            mean_heard,

        "max_heard":
            heard_max,

        "heard_pct":
            heard_pct,

        "mean_song":
            mean_song,

        "descending_hz":
            mean_dn_hz,

        "DNp01_hz":
            mean_p01_hz,

        "_potential_raw":
            potential_raw,
    }


# ============================================================
# CALIBRATION 2
# ============================================================

print()
print(
    "============================================================"
)

print(
    "CALIBRATION 2 — 8v8 ARENA AUDIO SCALE"
)

print(
    "============================================================"
)


potential_audio = []


for seed in CALIBRATION_SEEDS:
    print(
        f"calibration seed {seed}"
    )

    result = run_battle(
        seed=seed,
        condition="no_audio",
        ear_gain=0.0,
        collect_potential_audio=True,
    )

    potential_audio.extend(
        result[
            "_potential_raw"
        ]
    )


positive_audio = np.asarray([
    x
    for x in potential_audio
    if x > 0
])


if len(
    positive_audio
) == 0:
    raise RuntimeError(
        "No positive wing-song signal "
        "during calibration."
    )


RAW_Q90 = float(
    np.quantile(
        positive_audio,
        0.90,
    )
)


EAR_GAIN = (
    EAR_CAP
    / RAW_Q90
)


print(
    f"raw all-audio q90 : "
    f"{RAW_Q90:.4f}"
)

print(
    f"ear gain           : "
    f"{EAR_GAIN:.4f}"
)

print(
    f"q90 -> JO input    : "
    f"{EAR_CAP:.2f}"
)


# ============================================================
# MAIN PAIRED EXPERIMENT
# ============================================================

print()
print(
    "============================================================"
)

print(
    "FLYSWARM 0.5 — 2 BRAINS × 8 AGENTS"
)

print(
    "============================================================"
)


results = []


for seed in TEST_SEEDS:
    print()
    print(
        "=" * 116
    )

    print(
        f"SEED {seed}"
    )

    print(
        "=" * 116
    )

    for condition in CONDITIONS:
        result = run_battle(
            seed=seed,
            condition=condition,
            ear_gain=EAR_GAIN,
            collect_potential_audio=False,
        )

        result.pop(
            "_potential_raw",
            None,
        )

        results.append(
            result
        )

        print(
            f"{condition:10} | "
            f"sim={result['sim_time']:5.1f}s | "
            f"wall={result['wall_time']:6.1f}s | "
            f"xRT={result['realtime_factor']:.2f} | "
            f"acc={result['accuracy']*100:5.1f}% | "
            f"kills={result['kills']:2d} | "
            f"surv={result['survivors']:2d} | "
            f"focus={result['focus']:.2f} | "
            f"cover={result['coverage']:.2f} | "
            f"H={result['target_entropy']:.2f} | "
            f"switch={result['target_switches']:3d}"
        )


# ============================================================
# SAVE RAW
# ============================================================

with open(
    RAW_PATH,
    "w",
    newline="",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=results[0].keys(),
    )

    writer.writeheader()
    writer.writerows(
        results
    )


# ============================================================
# SUMMARY
# ============================================================

def subset(
    condition,
):
    return [
        r
        for r in results
        if (
            r["condition"]
            == condition
        )
    ]


def metric_values(
    condition,
    key,
):
    return [
        r[key]
        for r in subset(
            condition
        )
    ]


print()
print()
print(
    "=" * 132
)

print(
    "FLYSWARM 0.5 — SUMMARY"
)

print(
    "=" * 132
)


print(
    f"{'condition':10} | "
    f"{'xRT':>10} | "
    f"{'accuracy':>11} | "
    f"{'kills':>11} | "
    f"{'survivors':>11} | "
    f"{'focus':>10} | "
    f"{'coverage':>10} | "
    f"{'entropy':>10} | "
    f"{'switches':>11} | "
    f"{'DN Hz':>10}"
)

print(
    "-" * 132
)


summary_rows = []


for condition in CONDITIONS:
    xrt = metric_values(
        condition,
        "realtime_factor",
    )

    accuracy = metric_values(
        condition,
        "accuracy",
    )

    kills_v = metric_values(
        condition,
        "kills",
    )

    survivors = metric_values(
        condition,
        "survivors",
    )

    focus = metric_values(
        condition,
        "focus",
    )

    coverage = metric_values(
        condition,
        "coverage",
    )

    entropy = metric_values(
        condition,
        "target_entropy",
    )

    switches = metric_values(
        condition,
        "target_switches",
    )

    dn_hz = metric_values(
        condition,
        "descending_hz",
    )

    print(
        f"{condition:10} | "
        f"{mean(xrt):5.2f}"
        f"±{stdev(xrt):4.2f} | "
        f"{mean(accuracy)*100:6.1f}"
        f"±{stdev(accuracy)*100:4.1f}% | "
        f"{mean(kills_v):5.2f}"
        f"±{stdev(kills_v):4.2f} | "
        f"{mean(survivors):5.2f}"
        f"±{stdev(survivors):4.2f} | "
        f"{mean(focus):5.2f}"
        f"±{stdev(focus):4.2f} | "
        f"{mean(coverage):5.2f}"
        f"±{stdev(coverage):4.2f} | "
        f"{mean(entropy):5.2f}"
        f"±{stdev(entropy):4.2f} | "
        f"{mean(switches):6.1f}"
        f"±{stdev(switches):4.1f} | "
        f"{mean(dn_hz):6.1f}"
        f"±{stdev(dn_hz):4.1f}"
    )

    summary_rows.append({
        "condition":
            condition,

        "realtime_factor_mean":
            mean(xrt),

        "accuracy_mean":
            mean(accuracy),

        "kills_mean":
            mean(kills_v),

        "survivors_mean":
            mean(survivors),

        "focus_mean":
            mean(focus),

        "coverage_mean":
            mean(coverage),

        "target_entropy_mean":
            mean(entropy),

        "target_switches_mean":
            mean(switches),

        "descending_hz_mean":
            mean(dn_hz),

        "DNp01_hz_mean":
            mean(
                metric_values(
                    condition,
                    "DNp01_hz",
                )
            ),

        "heard_pct_mean":
            mean(
                metric_values(
                    condition,
                    "heard_pct",
                )
            ),
    })


# ============================================================
# PAIRED DIFFERENCES
# ============================================================

def get_result(
    seed,
    condition,
):
    return next(
        r
        for r in results
        if (
            r["seed"] == seed
            and
            r["condition"]
            == condition
        )
    )


def paired_report(
    condition,
):
    print()
    print(
        f"PAIRED {condition.upper()} - NO_AUDIO"
    )

    metric_map = {
        "accuracy_pp":
            "accuracy",

        "kills":
            "kills",

        "survivors":
            "survivors",

        "focus":
            "focus",

        "coverage":
            "coverage",

        "entropy":
            "target_entropy",

        "target_switches":
            "target_switches",

        "spread":
            "spread",

        "descending_hz":
            "descending_hz",

        "DNp01_hz":
            "DNp01_hz",
    }

    for label, key in metric_map.items():
        diffs = []

        for seed in TEST_SEEDS:
            A = get_result(
                seed,
                condition,
            )

            N0 = get_result(
                seed,
                "no_audio",
            )

            diff = (
                A[key]
                - N0[key]
            )

            if (
                label
                == "accuracy_pp"
            ):
                diff *= 100.0

            diffs.append(
                diff
            )

        print(
            f"  {label:18}: "
            f"{mean(diffs):+8.3f}"
            f" ± {stdev(diffs):.3f}"
        )


paired_report(
    "team_audio"
)

paired_report(
    "all_audio"
)


# ============================================================
# AUDIO EXPOSURE
# ============================================================

print()
print(
    "AUDIO EXPOSURE"
)

for condition in [
    "team_audio",
    "all_audio",
]:
    rows = subset(
        condition
    )

    print(
        f"  {condition:10}: "
        f"heard={mean([r['heard_pct'] for r in rows]):5.1f}% | "
        f"mean JO={mean([r['mean_heard'] for r in rows]):.4f} | "
        f"max JO={max(r['max_heard'] for r in rows):.4f} | "
        f"song={mean([r['mean_song'] for r in rows]):.4f}"
    )


# ============================================================
# SAVE SUMMARY
# ============================================================

with open(
    SUMMARY_PATH,
    "w",
    newline="",
) as f:
    writer = csv.DictWriter(
        f,
        fieldnames=summary_rows[0].keys(),
    )

    writer.writeheader()
    writer.writerows(
        summary_rows
    )


print()
print(
    f"Raw:     {RAW_PATH}"
)

print(
    f"Summary: {SUMMARY_PATH}"
)

print()
print(
    "Experiment complete."
)
