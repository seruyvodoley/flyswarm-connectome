from flybrain import FlyBrain

from collections import deque, Counter
from pathlib import Path
from statistics import mean, stdev

import csv
import math
import numpy as np


# ============================================================
# EXPERIMENT CONFIG
# ============================================================

N = 8

CALIBRATION_SEEDS = [
    180,
    181,
]

TEST_SEEDS = [
    184,
    185,
    186,
    187,
    188,
    189,
]

CONDITIONS = [
    "no_audio",
    "audio",
]

SIM_DURATION = 45.0

ARENA_W = 1000
ARENA_H = 700

WARMUP_STEPS = 25
REST_STEPS = 100

RATE_WINDOW = 10

STIMULUS = 0.8

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


# ============================================================
# COMBAT
# ============================================================

TANK_RADIUS = 15.0

MAX_HP = 3

RELOAD_TIME = 1.40

FIRE_RANGE = 500.0
FIRE_ERROR_DEG = 4.0

PROJECTILE_SPEED = 280.0
PROJECTILE_LIFETIME = 3.0


# ============================================================
# AUDIO
# ============================================================

EAR_CAP = 0.8

# Sound attenuation:
#
# d=0      -> 1.00
# d=250    -> 0.50
# d=500    -> 0.20
# d=750    -> 0.10

AUDIO_DISTANCE_SCALE = 250.0


# Exact wing-MN set used by current upstream flytalk.py

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


RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

RAW_PATH = (
    RESULTS
    / "flyswarm_04_audio_raw.csv"
)

SUMMARY_PATH = (
    RESULTS
    / "flyswarm_04_audio_summary.csv"
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


def distance(
    ax,
    ay,
    bx,
    by
):

    return math.hypot(
        bx - ax,
        by - ay
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

    d = math.hypot(
        px - cx,
        py - cy
    )

    if d <= radius:
        return t

    return None


# ============================================================
# LOAD BATCH MALECNS
# ============================================================

print(
    "Loading 8 MaleCNS brains..."
)

brain = FlyBrain(
    device="cpu",
    batch=N,
    seed=CALIBRATION_SEEDS[0]
)

print(
    f"neurons per fly      : "
    f"{brain.n:,}"
)

print(
    f"simulated neurons    : "
    f"{brain.n * N:,}"
)

print(
    f"dt                   : "
    f"{brain.dt:.3f}s"
)


# ============================================================
# SENSORY POPULATIONS
# ============================================================

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


# ============================================================
# AUDITORY POPULATION
# ============================================================

ear_types = sorted({
    str(t)

    for t in np.unique(
        brain.cell_type
    )

    if (
        str(t).startswith("JO-A")
        or
        str(t).startswith("JO-B")
    )
})

ear = brain.cells(
    ear_types
)


# ============================================================
# WING MOTOR NEURONS
# ============================================================

wing = brain.cells(
    WING_MN
)

wing_mask = np.zeros(
    brain.n,
    dtype=bool
)

wing_mask[
    wing
] = True


# ============================================================
# MOTOR READOUTS
# ============================================================

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


# danger probe only;
# does NOT control the tank in this experiment

p01 = set(
    brain.cells(
        ["DNp01"]
    )
)


descending = brain.cells(
    ["descending_neuron"]
)

descending_mask = np.zeros(
    brain.n,
    dtype=bool
)

descending_mask[
    descending
] = True


print(
    f"wing motor neurons   : "
    f"{len(wing)}"
)

print(
    f"JO-A/JO-B ear cells  : "
    f"{len(ear)}"
)

print(
    f"descending neurons   : "
    f"{len(descending)}"
)

print(
    f"DNp09 L/R            : "
    f"{len(p9_l)} / {len(p9_r)}"
)

print(
    f"DNa02 L/R            : "
    f"{len(a02_l)} / {len(a02_r)}"
)


if len(wing) == 0:
    raise RuntimeError(
        "No WING_MN neurons found."
    )

if len(ear) == 0:
    raise RuntimeError(
        "No JO-A/JO-B auditory neurons found."
    )


# ============================================================
# TEAMS
# ============================================================

teams = np.array([
    0, 0, 0, 0,
    1, 1, 1, 1,
])

names = [
    "A1",
    "A2",
    "A3",
    "A4",

    "B1",
    "B2",
    "B3",
    "B4",
]


# ============================================================
# WORLD INITIALISATION
# ============================================================

def create_world():

    xs = np.array([
        180.,
        390.,
        610.,
        820.,

        180.,
        390.,
        610.,
        820.,
    ])

    ys = np.array([
        100.,
        120.,
        120.,
        100.,

        600.,
        580.,
        580.,
        600.,
    ])

    body_yaw = np.array([
        0.,
        0.,
        0.,
        0.,

        180.,
        180.,
        180.,
        180.,
    ])

    turret_relative = np.zeros(
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
        -999.0,
        dtype=float
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
# FIRING HISTORIES
# ============================================================

def make_histories():

    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW
        )

        for _ in range(N)
    ]


def population_rate(
    histories,
    i
):

    return (
        sum(
            histories[i]
        )
        /
        (
            len(
                histories[i]
            )
            * brain.dt
        )
    )


# ============================================================
# WING ACTIVITY
# ============================================================

def wing_counts(
    fired_by_fly
):

    out = np.zeros(
        N,
        dtype=np.float32
    )

    for i, fired in enumerate(
        fired_by_fly
    ):

        out[i] = float(
            wing_mask[
                fired
            ].sum()
        )

    return out


def descending_counts(
    fired_by_fly
):

    out = np.zeros(
        N,
        dtype=np.float32
    )

    for i, fired in enumerate(
        fired_by_fly
    ):

        out[i] = float(
            descending_mask[
                fired
            ].sum()
        )

    return out


# ============================================================
# TARGET SELECTION
# ============================================================

def choose_target(
    i,
    xs,
    ys,
    body_yaw,
    alive
):

    if not alive[i]:
        return -1

    best = -1
    best_distance = float(
        "inf"
    )

    for j in range(N):

        if (
            not alive[j]
            or
            teams[j] == teams[i]
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
            dy
        )

        if (
            d
            > DETECTION_RANGE
        ):
            continue

        world_bearing = bearing(
            dx,
            dy
        )

        error = wrap_angle(
            world_bearing
            - body_yaw[i]
        )

        if (
            abs(error)
            > BODY_FOV / 2
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
# COLLISIONS
# ============================================================

def resolve_collisions(
    xs,
    ys,
    alive
):

    minimum = (
        2.0
        * TANK_RADIUS
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
                dy
            )

            if d >= minimum:
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


    for i in range(N):

        xs[i] = clamp(
            xs[i],
            TANK_RADIUS,
            ARENA_W
            - TANK_RADIUS
        )

        ys[i] = clamp(
            ys[i],
            TANK_RADIUS,
            ARENA_H
            - TANK_RADIUS
        )


# ============================================================
# SOUND PROPAGATION
# ============================================================

def attenuation(
    d
):

    x = (
        d
        / AUDIO_DISTANCE_SCALE
    )

    return (
        1.0
        /
        (
            1.0
            + x * x
        )
    )


def raw_heard_signal(
    sender_sound,
    xs,
    ys,
    alive
):
    """
    Each receiver hears every OTHER living fly.

    No team filtering.

    No semantic information.

    Only loudness + distance attenuation.
    """

    heard = np.zeros(
        N,
        dtype=np.float32
    )


    for receiver in range(N):

        if not alive[receiver]:
            continue


        total = 0.0


        for sender in range(N):

            if sender == receiver:
                continue

            if not alive[sender]:
                continue

            d = distance(
                xs[receiver],
                ys[receiver],
                xs[sender],
                ys[sender]
            )

            total += (
                sender_sound[sender]
                * attenuation(d)
            )


        heard[receiver] = total


    return heard


# ============================================================
# TEAM SPREAD
# ============================================================

def mean_team_pair_distance(
    team,
    xs,
    ys,
    alive
):

    members = [
        i

        for i in range(N)

        if (
            teams[i] == team
            and
            alive[i]
        )
    ]


    values = []


    for a in range(
        len(members)
    ):

        for b in range(
            a + 1,
            len(members)
        ):

            i = members[a]
            j = members[b]

            values.append(
                distance(
                    xs[i],
                    ys[i],
                    xs[j],
                    ys[j]
                )
            )


    if not values:
        return float("nan")

    return float(
        np.mean(values)
    )


# ============================================================
# RESTING WING CALIBRATION
# ============================================================

print()
print(
    "=============================================="
)

print(
    "CALIBRATION 1 — RESTING WING ACTIVITY"
)

print(
    "=============================================="
)


rest_samples = []


for seed in CALIBRATION_SEEDS:

    brain.reset(
        seed
    )


    for _ in range(
        WARMUP_STEPS
    ):

        brain.step()


    for _ in range(
        REST_STEPS
    ):

        fired = (
            brain.step()
        )

        rest_samples.extend(
            wing_counts(
                fired
            ).tolist()
        )


REST_WING = float(
    np.mean(
        rest_samples
    )
)


print(
    f"rest wing activity : "
    f"{REST_WING:.4f} "
    f"spikes/fly/step"
)


# ============================================================
# CORE BATTLE
# ============================================================

def run_battle(
    seed,
    audio_enabled,
    ear_gain,
    collect_heard=False
):

    brain.reset(
        seed
    )


    for _ in range(
        WARMUP_STEPS
    ):
        brain.step()


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
        N,
        -1,
        dtype=int
    )


    previous_targets = np.full(
        N,
        -1,
        dtype=int
    )


    # --------------------------------------------------------
    # MOTOR RATE WINDOWS
    # --------------------------------------------------------

    p9_l_hist = make_histories()
    p9_r_hist = make_histories()

    a02_l_hist = make_histories()
    a02_r_hist = make_histories()


    # --------------------------------------------------------
    # AUDIO STATE
    # --------------------------------------------------------

    previous_sender_sound = (
        np.zeros(
            N,
            dtype=np.float32
        )
    )


    # --------------------------------------------------------
    # BATTLE STATE
    # --------------------------------------------------------

    projectiles = []

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


    target_switches = np.zeros(
        N,
        dtype=int
    )


    focus_sum = np.zeros(
        2,
        dtype=float
    )

    focus_steps = np.zeros(
        2,
        dtype=int
    )

    focus_max = np.zeros(
        2,
        dtype=int
    )


    ally_distance_sum = np.zeros(
        2,
        dtype=float
    )

    ally_distance_steps = np.zeros(
        2,
        dtype=int
    )


    heard_positive_steps = 0
    heard_total_steps = 0

    heard_amount_sum = 0.0
    heard_amount_max = 0.0

    raw_heard_values = []


    wing_sound_sum = 0.0
    wing_sound_n = 0


    descending_spikes = 0.0
    descending_samples = 0


    p01_spikes = 0.0
    p01_samples = 0


    sim_t = 0.0


    # ========================================================
    # LOOP
    # ========================================================

    while (
        sim_t
        < SIM_DURATION
    ):

        blue_alive = int(
            alive[:4].sum()
        )

        red_alive = int(
            alive[4:].sum()
        )


        if (
            blue_alive == 0
            or
            red_alive == 0
        ):
            break


        # ====================================================
        # TARGET PERCEPTION
        # ====================================================

        body_errors = np.zeros(
            N,
            dtype=float
        )

        turret_errors = np.zeros(
            N,
            dtype=float
        )


        for i in range(N):

            targets[i] = (
                choose_target(
                    i,
                    xs,
                    ys,
                    body_yaw,
                    alive
                )
            )


            if (
                previous_targets[i] >= 0
                and
                targets[i] >= 0
                and
                targets[i]
                != previous_targets[i]
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


            target_bearing = bearing(
                dx,
                dy
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


        # ====================================================
        # FOCUS FIRE
        # ====================================================

        for team in [
            0,
            1
        ]:

            counts = Counter()


            for i in range(N):

                if (
                    alive[i]
                    and
                    teams[i] == team
                    and
                    targets[i] >= 0
                ):

                    counts[
                        int(
                            targets[i]
                        )
                    ] += 1


            if counts:

                f = max(
                    counts.values()
                )

                focus_sum[
                    team
                ] += f

                focus_steps[
                    team
                ] += 1

                focus_max[
                    team
                ] = max(
                    focus_max[
                        team
                    ],
                    f
                )


        # ====================================================
        # TEAM DISPERSION
        # ====================================================

        for team in [
            0,
            1
        ]:

            d = (
                mean_team_pair_distance(
                    team,
                    xs,
                    ys,
                    alive
                )
            )


            if not math.isnan(
                d
            ):

                ally_distance_sum[
                    team
                ] += d

                ally_distance_steps[
                    team
                ] += 1


        # ====================================================
        # VISUAL INPUT
        # ====================================================

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
                or
                targets[i] < 0
            ):
                continue


            e = (
                body_errors[i]
            )


            if (
                e
                < -BODY_DEADZONE
            ):

                lc9_l_amount[i] = (
                    STIMULUS
                )

            elif (
                e
                > BODY_DEADZONE
            ):

                lc9_r_amount[i] = (
                    STIMULUS
                )

            else:

                lc9_l_amount[i] = (
                    STIMULUS
                )

                lc9_r_amount[i] = (
                    STIMULUS
                )


            te = (
                turret_errors[i]
            )


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


        # ====================================================
        # SOUND ARRIVING THIS STEP
        # ====================================================
        #
        # previous_sender_sound is from the PREVIOUS brain step.
        # This gives one-step transmission delay, matching
        # flytalk.py's causal ordering.
        # ====================================================

        raw_heard = (
            raw_heard_signal(
                previous_sender_sound,
                xs,
                ys,
                alive
            )
        )


        if collect_heard:

            raw_heard_values.extend(
                raw_heard[
                    alive
                ].tolist()
            )


        if audio_enabled:

            ear_amount = np.minimum(
                raw_heard
                * ear_gain,
                EAR_CAP
            ).astype(
                np.float32
            )

        else:

            ear_amount = np.zeros(
                N,
                dtype=np.float32
            )


        # dead receivers hear nothing

        ear_amount[
            ~alive
        ] = 0.0


        heard_positive_steps += int(
            np.count_nonzero(
                ear_amount
                > 0
            )
        )

        heard_total_steps += int(
            alive.sum()
        )

        heard_amount_sum += float(
            ear_amount.sum()
        )

        if len(
            ear_amount
        ):

            heard_amount_max = max(
                heard_amount_max,
                float(
                    ear_amount.max()
                )
            )


        # ====================================================
        # STEP ALL 8 BRAINS
        # ====================================================

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
                (
                    ear,
                    ear_amount
                ),
            ]
        )


        # ====================================================
        # NEW SONG GENERATED THIS STEP
        # ====================================================

        wings = (
            wing_counts(
                fired_by_fly
            )
        )


        sender_sound = np.maximum(
            wings
            - REST_WING,
            0.0
        )


        # dead flies do not produce external sound

        sender_sound[
            ~alive
        ] = 0.0


        previous_sender_sound = (
            sender_sound
        )


        wing_sound_sum += float(
            sender_sound.sum()
        )

        wing_sound_n += int(
            alive.sum()
        )


        # ====================================================
        # INTERNAL ACTIVITY PROBES
        # ====================================================

        dn_counts = (
            descending_counts(
                fired_by_fly
            )
        )


        descending_spikes += float(
            dn_counts[
                alive
            ].sum()
        )

        descending_samples += int(
            alive.sum()
        )


        for i in range(N):

            if not alive[i]:
                continue

            fired_set = set(
                fired_by_fly[i]
            )

            p01_spikes += len(
                fired_set.intersection(
                    p01
                )
            )

            p01_samples += (
                len(p01)
            )


        # ====================================================
        # NATURAL MOTOR OUTPUT
        # ====================================================

        speeds = np.zeros(
            N,
            dtype=float
        )

        body_turn_rates = np.zeros(
            N,
            dtype=float
        )

        turret_turn_rates = np.zeros(
            N,
            dtype=float
        )


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


            p9L = population_rate(
                p9_l_hist,
                i
            )

            p9R = population_rate(
                p9_r_hist,
                i
            )

            a02L = population_rate(
                a02_l_hist,
                i
            )

            a02R = population_rate(
                a02_r_hist,
                i
            )


            pursuit = max(
                0.0,
                p9L
                + p9R
                - P9_DEADZONE
            )


            speeds[i] = clamp(
                pursuit
                * SPEED_GAIN,

                0.0,
                MAX_SPEED
            )


            body_turn_rates[i] = (
                clamp(
                    (
                        p9R
                        - p9L
                    )
                    * BODY_TURN_GAIN,

                    -MAX_BODY_TURN,
                    MAX_BODY_TURN
                )
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


            turret_turn_rates[i] = (
                clamp(
                    -turret_signal
                    * TURRET_GAIN,

                    -MAX_TURRET_TURN,
                    MAX_TURRET_TURN
                )
            )


        # ====================================================
        # MOVEMENT
        # ====================================================

        for i in range(N):

            if not alive[i]:
                continue


            body_yaw[i] = (
                wrap_angle(
                    body_yaw[i]
                    + body_turn_rates[i]
                    * brain.dt
                )
            )


            turret_relative[i] = (
                wrap_angle(
                    turret_relative[i]
                    + turret_turn_rates[i]
                    * brain.dt
                )
            )


            rad = math.radians(
                body_yaw[i]
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


        # ====================================================
        # EXISTING PROJECTILES
        # ====================================================

        remaining = []


        for p in projectiles:

            old_x = p[
                "x"
            ]

            old_y = p[
                "y"
            ]


            new_x = (
                old_x
                + p["vx"]
                * brain.dt
            )

            new_y = (
                old_y
                + p["vy"]
                * brain.dt
            )


            p[
                "age"
            ] += brain.dt


            victim = None
            best_t = float(
                "inf"
            )


            for j in range(N):

                if (
                    not alive[j]
                    or
                    teams[j]
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

                        TANK_RADIUS
                    )
                )


                if (
                    hit_t is not None
                    and
                    hit_t < best_t
                ):

                    best_t = (
                        hit_t
                    )

                    victim = j


            if (
                victim
                is not None
            ):

                owner = p[
                    "owner"
                ]


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


            p[
                "x"
            ] = new_x

            p[
                "y"
            ] = new_y


            if (
                p["age"]
                < PROJECTILE_LIFETIME

                and
                0 <= new_x
                <= ARENA_W

                and
                0 <= new_y
                <= ARENA_H
            ):

                remaining.append(
                    p
                )


        projectiles = (
            remaining
        )


        # ====================================================
        # AUTO FIRE
        # ====================================================
        #
        # Same fixed firing policy in BOTH conditions.
        #
        # This experiment is about AUDIO only.
        # ====================================================

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


            j = targets[i]


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
                dy
            )


            target_bearing = bearing(
                dx,
                dy
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
                    + math.sin(
                        rad
                    )
                    * (
                        TANK_RADIUS
                        + 8
                    ),

                "y":
                    ys[i]
                    + math.cos(
                        rad
                    )
                    * (
                        TANK_RADIUS
                        + 8
                    ),

                "vx":
                    math.sin(
                        rad
                    )
                    * PROJECTILE_SPEED,

                "vy":
                    math.cos(
                        rad
                    )
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


            shots[
                i
            ] += 1


            last_shot[
                i
            ] = sim_t


        sim_t += (
            brain.dt
        )


    # ========================================================
    # RESULTS
    # ========================================================

    blue_alive = int(
        alive[
            :4
        ].sum()
    )

    red_alive = int(
        alive[
            4:
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


    focus_blue = (
        focus_sum[0]
        / focus_steps[0]

        if focus_steps[0]
        else 0.0
    )

    focus_red = (
        focus_sum[1]
        / focus_steps[1]

        if focus_steps[1]
        else 0.0
    )


    spread_blue = (
        ally_distance_sum[0]
        / ally_distance_steps[0]

        if ally_distance_steps[0]
        else float("nan")
    )


    spread_red = (
        ally_distance_sum[1]
        / ally_distance_steps[1]

        if ally_distance_steps[1]
        else float("nan")
    )


    mean_heard = (
        heard_amount_sum
        / heard_total_steps

        if heard_total_steps
        else 0.0
    )


    heard_pct = (
        heard_positive_steps
        / heard_total_steps
        * 100

        if heard_total_steps
        else 0.0
    )


    mean_song = (
        wing_sound_sum
        / wing_sound_n

        if wing_sound_n
        else 0.0
    )


    mean_desc = (
        descending_spikes
        / descending_samples
        / brain.dt

        if descending_samples
        else 0.0
    )


    mean_p01 = (
        p01_spikes
        / p01_samples
        / brain.dt

        if p01_samples
        else 0.0
    )


    return {
        "seed":
            seed,

        "condition":
            (
                "audio"
                if audio_enabled
                else "no_audio"
            ),

        "sim_time":
            sim_t,

        "shots":
            total_shots,

        "hits":
            total_hits,

        "accuracy":
            accuracy,

        "kills":
            total_kills,

        "survivors":
            blue_alive
            + red_alive,

        "blue_survivors":
            blue_alive,

        "red_survivors":
            red_alive,

        "focus_blue":
            focus_blue,

        "focus_red":
            focus_red,

        "focus_max_blue":
            int(
                focus_max[0]
            ),

        "focus_max_red":
            int(
                focus_max[1]
            ),

        "target_switches":
            int(
                target_switches.sum()
            ),

        "spread_blue":
            spread_blue,

        "spread_red":
            spread_red,

        "mean_heard":
            mean_heard,

        "max_heard":
            heard_amount_max,

        "heard_pct":
            heard_pct,

        "mean_song":
            mean_song,

        "descending_hz":
            mean_desc,

        "DNp01_hz":
            mean_p01,

        "_raw_heard":
            raw_heard_values,
    }


# ============================================================
# CALIBRATION 2 — CLOSED-LOOP SOUND SCALE
# ============================================================

print()
print(
    "=============================================="
)

print(
    "CALIBRATION 2 — ARENA SOUND LEVEL"
)

print(
    "=============================================="
)


all_raw_heard = []


for seed in CALIBRATION_SEEDS:

    print(
        f"calibration battle seed "
        f"{seed}"
    )


    result = run_battle(
        seed=seed,
        audio_enabled=False,
        ear_gain=0.0,
        collect_heard=True,
    )


    all_raw_heard.extend(
        result[
            "_raw_heard"
        ]
    )


positive_heard = np.asarray([
    x

    for x in all_raw_heard

    if x > 0
])


if len(
    positive_heard
) == 0:

    raise RuntimeError(
        "No positive fly-song signal "
        "was generated in calibration."
    )


HEARD_Q90 = float(
    np.quantile(
        positive_heard,
        0.90
    )
)


EAR_GAIN = (
    EAR_CAP
    / HEARD_Q90
)


print(
    f"raw heard q90      : "
    f"{HEARD_Q90:.4f}"
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
# PAIRED EXPERIMENT
# ============================================================

print()
print(
    "=============================================="
)

print(
    "FLYSWARM 0.4 — AUDIO EXPERIMENT"
)

print(
    "=============================================="
)


results = []


for seed in TEST_SEEDS:

    print()
    print(
        "=" * 90
    )

    print(
        f"SEED {seed}"
    )

    print(
        "=" * 90
    )


    for condition in CONDITIONS:

        audio_enabled = (
            condition
            == "audio"
        )


        r = run_battle(
            seed=seed,
            audio_enabled=audio_enabled,
            ear_gain=EAR_GAIN,
            collect_heard=False,
        )


        # do not save raw calibration arrays

        r.pop(
            "_raw_heard",
            None
        )


        results.append(
            r
        )


        print(
            f"{condition:9} | "
            f"t={r['sim_time']:5.1f}s | "
            f"shots={r['shots']:3d} | "
            f"acc={r['accuracy']*100:5.1f}% | "
            f"kills={r['kills']} | "
            f"surv={r['survivors']} | "
            f"focus="
            f"{(r['focus_blue'] + r['focus_red'])/2:.2f} | "
            f"switch={r['target_switches']:3d} | "
            f"DN={r['descending_hz']:6.1f}Hz"
        )


# ============================================================
# SAVE RAW
# ============================================================

with open(
    RAW_PATH,
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

def subset(
    condition
):

    return [
        r

        for r in results

        if (
            r["condition"]
            == condition
        )
    ]


def values(
    condition,
    key
):

    return [
        r[key]

        for r in subset(
            condition
        )
    ]


summary_rows = []


print()
print()
print(
    "=" * 116
)

print(
    "FLYSWARM 0.4 — AUDIO SUMMARY"
)

print(
    "=" * 116
)


print(
    f"{'condition':10} | "
    f"{'duration':>13} | "
    f"{'accuracy':>10} | "
    f"{'kills':>10} | "
    f"{'survivors':>11} | "
    f"{'focus':>10} | "
    f"{'switches':>11} | "
    f"{'spread':>11} | "
    f"{'DN Hz':>10}"
)

print(
    "-" * 116
)


for condition in CONDITIONS:

    duration = values(
        condition,
        "sim_time"
    )

    accuracy = values(
        condition,
        "accuracy"
    )

    kills_v = values(
        condition,
        "kills"
    )

    survivors = values(
        condition,
        "survivors"
    )

    focus = [
        (
            r["focus_blue"]
            + r["focus_red"]
        ) / 2.0

        for r in subset(
            condition
        )
    ]

    switches = values(
        condition,
        "target_switches"
    )

    spread = [
        (
            r["spread_blue"]
            + r["spread_red"]
        ) / 2.0

        for r in subset(
            condition
        )
    ]

    dn_hz = values(
        condition,
        "descending_hz"
    )


    print(
        f"{condition:10} | "
        f"{mean(duration):6.1f}"
        f"±{stdev(duration):4.1f} | "
        f"{mean(accuracy)*100:6.1f}"
        f"±{stdev(accuracy)*100:4.1f}% | "
        f"{mean(kills_v):5.2f}"
        f"±{stdev(kills_v):4.2f} | "
        f"{mean(survivors):5.2f}"
        f"±{stdev(survivors):4.2f} | "
        f"{mean(focus):5.2f}"
        f"±{stdev(focus):4.2f} | "
        f"{mean(switches):6.1f}"
        f"±{stdev(switches):4.1f} | "
        f"{mean(spread):6.1f}"
        f"±{stdev(spread):4.1f} | "
        f"{mean(dn_hz):6.1f}"
        f"±{stdev(dn_hz):4.1f}"
    )


    summary_rows.append({
        "condition":
            condition,

        "duration_mean":
            mean(duration),

        "accuracy_mean":
            mean(accuracy),

        "kills_mean":
            mean(kills_v),

        "survivors_mean":
            mean(survivors),

        "focus_mean":
            mean(focus),

        "switches_mean":
            mean(switches),

        "spread_mean":
            mean(spread),

        "descending_hz_mean":
            mean(dn_hz),
    })


# ============================================================
# PAIRED DIFFERENCES
# ============================================================

def get_result(
    seed,
    condition
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


metrics = {
    "duration":
        "sim_time",

    "accuracy_pp":
        "accuracy",

    "kills":
        "kills",

    "survivors":
        "survivors",

    "focus":
        None,

    "target_switches":
        "target_switches",

    "spread":
        None,

    "descending_hz":
        "descending_hz",

    "DNp01_hz":
        "DNp01_hz",
}


print()
print(
    "Paired AUDIO - NO_AUDIO:"
)


for label, key in metrics.items():

    diffs = []


    for seed in TEST_SEEDS:

        A = get_result(
            seed,
            "audio"
        )

        N0 = get_result(
            seed,
            "no_audio"
        )


        if label == "focus":

            a = (
                A["focus_blue"]
                + A["focus_red"]
            ) / 2

            n = (
                N0["focus_blue"]
                + N0["focus_red"]
            ) / 2


        elif label == "spread":

            a = (
                A["spread_blue"]
                + A["spread_red"]
            ) / 2

            n = (
                N0["spread_blue"]
                + N0["spread_red"]
            ) / 2


        else:

            a = A[key]
            n = N0[key]


        diff = (
            a - n
        )


        if (
            label
            == "accuracy_pp"
        ):

            diff *= 100


        diffs.append(
            diff
        )


    print(
        f"  {label:18}: "
        f"{mean(diffs):+8.3f}"
        f" ± {stdev(diffs):.3f}"
    )


# ============================================================
# AUDIO EXPOSURE
# ============================================================

audio_runs = subset(
    "audio"
)


print()
print(
    "Audio exposure:"
)

print(
    f"  mean JO input      : "
    f"{mean([r['mean_heard'] for r in audio_runs]):.4f}"
)

print(
    f"  max JO input       : "
    f"{max(r['max_heard'] for r in audio_runs):.4f}"
)

print(
    f"  hearing active     : "
    f"{mean([r['heard_pct'] for r in audio_runs]):.1f}%"
)

print(
    f"  mean song amplitude: "
    f"{mean([r['mean_song'] for r in audio_runs]):.4f}"
)


# ============================================================
# SAVE SUMMARY
# ============================================================

with open(
    SUMMARY_PATH,
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
    f"Raw:     {RAW_PATH}"
)

print(
    f"Summary: {SUMMARY_PATH}"
)
