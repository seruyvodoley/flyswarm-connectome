from flybrain import FlyBrain
from flybrain.reservoir import Trace, Readout

from collections import deque, Counter
from pathlib import Path

import pygame
import numpy as np
import math
import time


# ============================================================
# CONFIG
# ============================================================

N = 8

TRAIN_SEEDS = [
    64,
    65,
    66,
    67,
]

EVAL_SEED = 164

TRAIN_DURATION = 18.0
TRAIN_TAIL = 3.2

EVAL_DURATION = 45.0

TRAIN_FIRE_PROB = 0.08

FIRE_THRESHOLD = 0.50

ARENA_W = 1000
ARENA_H = 700
HUD_W = 340

WINDOW_W = ARENA_W + HUD_W
WINDOW_H = ARENA_H

WARMUP_STEPS = 25
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

TANK_RADIUS = 15.0

MAX_HP = 3

RELOAD_TIME = 1.20

PROJECTILE_SPEED = 280.0
PROJECTILE_LIFETIME = 3.0

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)

MODEL_PATH = (
    RESULTS
    / "flyswarm_03_fire_readout.npz"
)

DATASET_PATH = (
    RESULTS
    / "flyswarm_03_fire_dataset.npz"
)


# ============================================================
# BASIC MATH
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

    d = math.hypot(
        px - cx,
        py - cy
    )

    if d <= radius:
        return t

    return None


# ============================================================
# LOAD ONE BATCH OF 8 BRAINS
# ============================================================

print(
    "Loading 8 MaleCNS brains..."
)

brain = FlyBrain(
    device="cpu",
    batch=N,
    seed=TRAIN_SEEDS[0]
)

print(
    f"neurons per fly       : "
    f"{brain.n:,}"
)

print(
    f"total active neurons  : "
    f"{brain.n * N:,}"
)

print(
    f"dt                    : "
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
# NATURAL MOTOR POPULATIONS
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


# ============================================================
# ALL DESCENDING NEURONS FOR LEARNING
# ============================================================

descending = brain.cells(
    ["descending_neuron"]
)

print(
    f"descending features   : "
    f"{len(descending)}"
)

fire_trace = Trace(
    brain,
    idx=descending,
    tau=0.10,
    aggregate="batch"
)


# ============================================================
# CONSTANT WORLD INFO
# ============================================================

teams = np.array([
    0, 0, 0, 0,
    1, 1, 1, 1
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
        -999.0
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
# HISTORIES
# ============================================================

def make_histories():

    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW
        )
        for _ in range(N)
    ]


def history_rate(
    histories,
    i
):

    return (
        sum(histories[i])
        / (
            len(histories[i])
            * brain.dt
        )
    )


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
    best_d = float("inf")

    for j in range(N):

        if (
            not alive[j]
            or teams[j] == teams[i]
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

        if d > DETECTION_RANGE:
            continue

        angle = bearing(
            dx,
            dy
        )

        error = wrap_angle(
            angle
            - body_yaw[i]
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


# ============================================================
# COLLISIONS
# ============================================================

def resolve_collisions(
    xs,
    ys,
    alive
):

    minimum = (
        TANK_RADIUS
        * 2.0
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

            push = overlap / 2

            xs[i] -= nx * push
            ys[i] -= ny * push

            xs[j] += nx * push
            ys[j] += ny * push


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
# ONE EPISODE
# ============================================================

def run_episode(
    seed,
    mode,
    readout=None,
    render=False,
    episode_id=0
):

    assert mode in (
        "training",
        "learned"
    )


    # --------------------------------------------------------
    # RESET BRAIN
    # --------------------------------------------------------

    brain.reset(seed)

    fire_trace.reset()


    for _ in range(
        WARMUP_STEPS
    ):
        brain.step()


    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

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


    # --------------------------------------------------------
    # MOTOR HISTORY
    # --------------------------------------------------------

    p9_l_hist = make_histories()
    p9_r_hist = make_histories()

    a02_l_hist = make_histories()
    a02_r_hist = make_histories()


    # --------------------------------------------------------
    # STATS
    # --------------------------------------------------------

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

    probabilities = np.zeros(
        N,
        dtype=float
    )


    # --------------------------------------------------------
    # TRAINING DATA
    # --------------------------------------------------------

    samples_X = []
    samples_y = []
    samples_group = []
    samples_owner = []


    # --------------------------------------------------------
    # RANDOM EXPLORATION
    # --------------------------------------------------------

    rng = np.random.default_rng(
        100000
        + seed
    )


    # --------------------------------------------------------
    # PROJECTILES
    # --------------------------------------------------------

    projectiles = []


    # --------------------------------------------------------
    # FOCUS
    # --------------------------------------------------------

    focus_sum = [
        0.0,
        0.0
    ]

    focus_steps = [
        0,
        0
    ]

    max_focus = [
        0,
        0
    ]


    # --------------------------------------------------------
    # DISPLAY
    # --------------------------------------------------------

    if render:

        pygame.init()

        screen = pygame.display.set_mode(
            (
                WINDOW_W,
                WINDOW_H
            )
        )

        pygame.display.set_caption(
            "FlySwarm 0.3 — Learned Fire"
        )

        font = pygame.font.SysFont(
            "Menlo",
            14
        )

        big_font = pygame.font.SysFont(
            "Menlo",
            23
        )

        clock = pygame.time.Clock()

    else:

        screen = None
        font = None
        big_font = None
        clock = None


    # --------------------------------------------------------
    # TIME
    # --------------------------------------------------------

    if mode == "training":

        main_duration = (
            TRAIN_DURATION
        )

        total_duration = (
            TRAIN_DURATION
            + TRAIN_TAIL
        )

    else:

        main_duration = (
            EVAL_DURATION
        )

        total_duration = (
            EVAL_DURATION
        )


    sim_t = 0.0

    wall_start = (
        time.perf_counter()
    )

    running = True


    # ========================================================
    # LOOP
    # ========================================================

    while (
        running
        and sim_t < total_duration
    ):

        if render:

            for event in (
                pygame.event.get()
            ):

                if (
                    event.type
                    == pygame.QUIT
                ):
                    running = False


        # ----------------------------------------------------
        # TERMINAL CONDITION ONLY DURING REAL BATTLE
        # ----------------------------------------------------

        if mode == "learned":

            blue_alive = int(
                sum(
                    alive[:4]
                )
            )

            red_alive = int(
                sum(
                    alive[4:]
                )
            )

            if (
                blue_alive == 0
                or red_alive == 0
            ):
                break


        # ====================================================
        # PERCEPTION
        # ====================================================

        body_errors = np.zeros(N)
        turret_errors = np.zeros(N)

        target_distances = np.full(
            N,
            np.nan
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

            d = math.hypot(
                dx,
                dy
            )

            target_distances[i] = d

            target_bearing = (
                bearing(
                    dx,
                    dy
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


        # ====================================================
        # FOCUS-FIRE METRIC
        # ====================================================

        if mode == "learned":

            for team in [0, 1]:

                c = Counter()

                for i in range(N):

                    if (
                        alive[i]
                        and
                        teams[i] == team
                        and
                        targets[i] >= 0
                    ):

                        c[
                            int(
                                targets[i]
                            )
                        ] += 1

                if c:

                    f = max(
                        c.values()
                    )

                    focus_sum[team] += f
                    focus_steps[team] += 1

                    max_focus[team] = max(
                        max_focus[team],
                        f
                    )


        # ====================================================
        # BUILD SENSOR VECTORS
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
                or targets[i] < 0
            ):
                continue


            # ---------------- pursuit ----------------

            e = body_errors[i]

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


            # ---------------- turret ----------------

            te = turret_errors[i]

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
        # STEP 8 FULL BRAINS
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
            ]
        )


        # activity:
        #
        # shape =
        # (1314 descending neurons, 8 flies)

        activity = fire_trace.observe(
            fired_by_fly
        )


        # ====================================================
        # MOTOR READOUTS
        # ====================================================

        speeds = np.zeros(N)

        body_turn_rates = np.zeros(N)

        turret_turn_rates = np.zeros(N)


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


            p9_l_rate = (
                history_rate(
                    p9_l_hist,
                    i
                )
            )

            p9_r_rate = (
                history_rate(
                    p9_r_hist,
                    i
                )
            )

            a02_l_rate = (
                history_rate(
                    a02_l_hist,
                    i
                )
            )

            a02_r_rate = (
                history_rate(
                    a02_r_hist,
                    i
                )
            )


            pursuit = max(
                0.0,

                p9_l_rate
                + p9_r_rate
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
                        p9_r_rate
                        - p9_l_rate
                    )
                    * BODY_TURN_GAIN,

                    -MAX_BODY_TURN,
                    MAX_BODY_TURN
                )
            )


            turret_signal = (
                a02_l_rate
                - a02_r_rate
            )

            if (
                abs(turret_signal)
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
        # MOVE TANKS
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
        # UPDATE PROJECTILES
        # ====================================================

        remaining = []


        for p in projectiles:

            old_x = p["x"]
            old_y = p["y"]

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

            p["age"] += (
                brain.dt
            )


            hit_target = None
            hit_t = float("inf")


            for j in range(N):

                if (
                    not alive[j]
                    or
                    teams[j]
                    == p["team"]
                ):
                    continue


                t_hit = (
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
                    t_hit is not None
                    and
                    t_hit < hit_t
                ):

                    hit_t = t_hit
                    hit_target = j


            # -----------------------------------------------
            # HIT
            # -----------------------------------------------

            if hit_target is not None:

                owner = p[
                    "owner"
                ]

                hits[owner] += 1


                # training label

                if mode == "training":

                    samples_X.append(
                        p["feature"]
                    )

                    samples_y.append(1)

                    samples_group.append(
                        episode_id
                    )

                    samples_owner.append(
                        owner
                    )


                # real combat damage only in evaluation

                else:

                    hp[
                        hit_target
                    ] -= 1

                    if (
                        hp[
                            hit_target
                        ]
                        <= 0
                    ):

                        hp[
                            hit_target
                        ] = 0

                        alive[
                            hit_target
                        ] = False

                        kills[
                            owner
                        ] += 1


                continue


            # -----------------------------------------------
            # MISS / EXPIRED
            # -----------------------------------------------

            p["x"] = new_x
            p["y"] = new_y


            expired = (
                p["age"]
                >= PROJECTILE_LIFETIME
                or
                new_x < 0
                or
                new_x > ARENA_W
                or
                new_y < 0
                or
                new_y > ARENA_H
            )


            if expired:

                if mode == "training":

                    samples_X.append(
                        p["feature"]
                    )

                    samples_y.append(0)

                    samples_group.append(
                        episode_id
                    )

                    samples_owner.append(
                        p["owner"]
                    )

                continue


            remaining.append(p)


        projectiles = remaining


        # ====================================================
        # FIRE DECISION
        # ====================================================

        probabilities[:] = 0.0


        for i in range(N):

            if (
                not alive[i]
                or
                targets[i] < 0
            ):
                continue


            reloaded = (
                sim_t
                - last_shot[i]
                >= RELOAD_TIME
            )


            if not reloaded:
                continue


            should_fire = False


            # ================================================
            # TRAINING:
            #
            # NO AIM-ERROR RULE.
            #
            # Random exploratory firing.
            # ================================================

            if mode == "training":

                if (
                    sim_t
                    < main_duration
                    and
                    rng.random()
                    < TRAIN_FIRE_PROB
                ):

                    should_fire = True


            # ================================================
            # LEARNED:
            #
            # Only 1314-D descending-neuron trace.
            # ================================================

            else:

                feature = (
                    activity[:, i]
                    .astype(
                        np.float32
                    )
                    .copy()
                )

                probability = float(
                    readout.predict(
                        feature
                    )
                )

                probabilities[i] = (
                    probability
                )


                if (
                    probability
                    >= FIRE_THRESHOLD
                ):

                    should_fire = True


            if not should_fire:
                continue


            # ------------------------------------------------
            # PROJECTILE DIRECTION IS ACTUAL TURRET DIRECTION
            # ------------------------------------------------

            turret_world = (
                wrap_angle(
                    body_yaw[i]
                    + turret_relative[i]
                )
            )


            rad = math.radians(
                turret_world
            )


            muzzle_x = (
                xs[i]
                + math.sin(rad)
                * (
                    TANK_RADIUS
                    + 8
                )
            )

            muzzle_y = (
                ys[i]
                + math.cos(rad)
                * (
                    TANK_RADIUS
                    + 8
                )
            )


            feature = (
                activity[:, i]
                .astype(
                    np.float32
                )
                .copy()
            )


            projectiles.append({
                "x":
                    muzzle_x,

                "y":
                    muzzle_y,

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

                "feature":
                    feature,
            })


            shots[i] += 1

            last_shot[i] = (
                sim_t
            )


        # ====================================================
        # RENDER EVALUATION
        # ====================================================

        if render:

            screen.fill(
                (18, 21, 25)
            )


            pygame.draw.rect(
                screen,
                (25, 30, 34),
                (
                    0,
                    0,
                    ARENA_W,
                    ARENA_H
                )
            )


            for gx in range(
                0,
                ARENA_W,
                50
            ):

                pygame.draw.line(
                    screen,
                    (35, 41, 45),
                    (
                        gx,
                        0
                    ),
                    (
                        gx,
                        ARENA_H
                    ),
                    1
                )


            for gy in range(
                0,
                ARENA_H,
                50
            ):

                pygame.draw.line(
                    screen,
                    (35, 41, 45),
                    (
                        0,
                        gy
                    ),
                    (
                        ARENA_W,
                        gy
                    ),
                    1
                )


            # -----------------------------------------------
            # PROJECTILES
            # -----------------------------------------------

            for p in projectiles:

                pygame.draw.circle(
                    screen,
                    (
                        255,
                        215,
                        70
                    ),
                    (
                        int(
                            p["x"]
                        ),
                        int(
                            ARENA_H
                            - p["y"]
                        )
                    ),
                    3
                )


            # -----------------------------------------------
            # TANKS
            # -----------------------------------------------

            for i in range(N):

                sx = int(
                    xs[i]
                )

                sy = int(
                    ARENA_H
                    - ys[i]
                )


                if (
                    teams[i]
                    == 0
                ):

                    colour = (
                        65,
                        145,
                        235
                    )

                else:

                    colour = (
                        230,
                        75,
                        70
                    )


                if not alive[i]:

                    pygame.draw.circle(
                        screen,
                        (
                            65,
                            65,
                            65
                        ),
                        (
                            sx,
                            sy
                        ),
                        13
                    )

                    continue


                pygame.draw.circle(
                    screen,
                    colour,
                    (
                        sx,
                        sy
                    ),
                    int(
                        TANK_RADIUS
                    )
                )


                turret_world = (
                    wrap_angle(
                        body_yaw[i]
                        + turret_relative[i]
                    )
                )

                tr = math.radians(
                    turret_world
                )


                bx = int(
                    sx
                    + math.sin(tr)
                    * 30
                )

                by = int(
                    sy
                    - math.cos(tr)
                    * 30
                )


                pygame.draw.line(
                    screen,
                    (
                        240,
                        240,
                        220
                    ),
                    (
                        sx,
                        sy
                    ),
                    (
                        bx,
                        by
                    ),
                    3
                )


                label = font.render(
                    names[i],
                    True,
                    (
                        240,
                        240,
                        240
                    )
                )

                screen.blit(
                    label,
                    (
                        sx - 10,
                        sy + 20
                    )
                )


            # -----------------------------------------------
            # HUD
            # -----------------------------------------------

            pygame.draw.rect(
                screen,
                (
                    12,
                    14,
                    18
                ),
                (
                    ARENA_W,
                    0,
                    HUD_W,
                    ARENA_H
                )
            )


            title = (
                big_font.render(
                    "FlySwarm 0.3",
                    True,
                    (
                        235,
                        235,
                        235
                    )
                )
            )

            screen.blit(
                title,
                (
                    ARENA_W + 18,
                    18
                )
            )


            elapsed = (
                time.perf_counter()
                - wall_start
            )

            sim_speed = (
                sim_t / elapsed
                if elapsed > 0
                else 0
            )


            blue_alive = int(
                sum(
                    alive[:4]
                )
            )

            red_alive = int(
                sum(
                    alive[4:]
                )
            )


            lines = [
                "",
                "LEARNED FIRING",
                "",
                f"time      {sim_t:6.2f}s",
                f"speed     {sim_speed:5.2f}x",
                "",
                f"BLUE      {blue_alive}/4",
                f"RED       {red_alive}/4",
                "",
            ]


            for i in range(N):

                target_name = (
                    names[
                        targets[i]
                    ]
                    if (
                        alive[i]
                        and
                        targets[i] >= 0
                    )
                    else "-"
                )


                lines.append(
                    f"{names[i]} "
                    f"HP{hp[i]} "
                    f"P={probabilities[i]:.2f} "
                    f"->{target_name}"
                )


            y = 58

            for line in lines:

                text = (
                    font.render(
                        line,
                        True,
                        (
                            205,
                            210,
                            215
                        )
                    )
                )

                screen.blit(
                    text,
                    (
                        ARENA_W + 18,
                        y
                    )
                )

                y += 21


            pygame.display.flip()

            clock.tick(1000)


        sim_t += (
            brain.dt
        )


    # ========================================================
    # CLOSE DISPLAY
    # ========================================================

    if render:
        pygame.quit()


    # ========================================================
    # SAFETY:
    # TRAINING TAIL SHOULD HAVE RESOLVED EVERYTHING.
    # LABEL ANY REMAINDER MISS.
    # ========================================================

    if mode == "training":

        for p in projectiles:

            samples_X.append(
                p["feature"]
            )

            samples_y.append(0)

            samples_group.append(
                episode_id
            )

            samples_owner.append(
                p["owner"]
            )


    wall_time = (
        time.perf_counter()
        - wall_start
    )


    return {
        "X":
            samples_X,

        "y":
            samples_y,

        "groups":
            samples_group,

        "owners":
            samples_owner,

        "shots":
            shots,

        "hits":
            hits,

        "kills":
            kills,

        "alive":
            alive,

        "hp":
            hp,

        "sim_time":
            sim_t,

        "wall_time":
            wall_time,

        "focus_sum":
            focus_sum,

        "focus_steps":
            focus_steps,

        "max_focus":
            max_focus,
    }


# ============================================================
# TRAINING DATA COLLECTION
# ============================================================

print()
print(
    "=============================================="
)

print(
    "PHASE 1 — EXPERIENCE COLLECTION"
)

print(
    "=============================================="
)


all_X = []
all_y = []
all_groups = []
all_owners = []


for episode_id, seed in enumerate(
    TRAIN_SEEDS
):

    print()
    print(
        f"Training episode "
        f"{episode_id + 1}/"
        f"{len(TRAIN_SEEDS)} "
        f"(seed={seed})"
    )


    result = run_episode(
        seed=seed,

        mode="training",

        episode_id=episode_id,

        render=False,
    )


    X = result["X"]
    y = result["y"]

    all_X.extend(X)
    all_y.extend(y)

    all_groups.extend(
        result["groups"]
    )

    all_owners.extend(
        result["owners"]
    )


    positives = sum(y)

    negatives = (
        len(y)
        - positives
    )


    print(
        f"resolved shots = "
        f"{len(y)}"
    )

    print(
        f"hits           = "
        f"{positives}"
    )

    print(
        f"misses         = "
        f"{negatives}"
    )


# ============================================================
# BUILD DATASET
# ============================================================

X = np.asarray(
    all_X,
    dtype=np.float32
)

y = np.asarray(
    all_y,
    dtype=np.int64
)

groups = np.asarray(
    all_groups,
    dtype=np.int64
)

owners = np.asarray(
    all_owners,
    dtype=np.int64
)


print()
print(
    "=============================================="
)

print(
    "TRAINING DATASET"
)

print(
    "=============================================="
)

print(
    f"samples          : "
    f"{len(X)}"
)

print(
    f"features         : "
    f"{X.shape[1]}"
)

print(
    f"hits             : "
    f"{int(y.sum())}"
)

print(
    f"misses           : "
    f"{int((y == 0).sum())}"
)

print(
    f"positive rate    : "
    f"{y.mean() * 100:.1f}%"
)


if (
    len(X) < 30
    or
    y.min() == y.max()
):

    raise RuntimeError(
        "Not enough HIT/MISS diversity "
        "to train fire readout."
    )


np.savez_compressed(
    DATASET_PATH,
    X=X,
    y=y,
    groups=groups,
    owners=owners,
)


# ============================================================
# TRAIN SHARED FIRE READOUT
# ============================================================

print()
print(
    "=============================================="
)

print(
    "PHASE 2 — TRAIN SHARED FIRE READOUT"
)

print(
    "=============================================="
)


readout = Readout.fit(
    X=X,
    y=y,
    kind="logistic",
    groups=groups,

    components=(
        5,
        20,
        60,
        120,
    ),

    lambdas=(
        1e-2,
        1e-1,
        1.0,
        10.0,
    ),

    verbose=True,
)


readout.save(
    MODEL_PATH
)


# ============================================================
# SIMPLE TRAINING-SET DIAGNOSTIC
# ============================================================

train_prob = (
    readout.predict(X)
)

train_pred = (
    train_prob
    >= FIRE_THRESHOLD
)


tp = int(
    np.sum(
        (train_pred == 1)
        &
        (y == 1)
    )
)

fp = int(
    np.sum(
        (train_pred == 1)
        &
        (y == 0)
    )
)

tn = int(
    np.sum(
        (train_pred == 0)
        &
        (y == 0)
    )
)

fn = int(
    np.sum(
        (train_pred == 0)
        &
        (y == 1)
    )
)


precision = (
    tp / (tp + fp)
    if tp + fp
    else 0.0
)

recall = (
    tp / (tp + fn)
    if tp + fn
    else 0.0
)


print()
print(
    f"CV AUC           : "
    f"{readout.cv_score:.3f}"
)

print(
    f"components       : "
    f"{readout.components}"
)

print(
    f"lambda           : "
    f"{readout.lam}"
)

print(
    f"train precision  : "
    f"{precision:.3f}"
)

print(
    f"train recall     : "
    f"{recall:.3f}"
)

print(
    f"model saved      : "
    f"{MODEL_PATH}"
)

print(
    f"dataset saved    : "
    f"{DATASET_PATH}"
)


# ============================================================
# EVALUATION
# ============================================================

print()
print(
    "=============================================="
)

print(
    "PHASE 3 — NEW BATTLE WITH LEARNED FIRING"
)

print(
    "=============================================="
)

print(
    f"evaluation seed = "
    f"{EVAL_SEED}"
)


evaluation = run_episode(
    seed=EVAL_SEED,

    mode="learned",

    readout=readout,

    render=True,

    episode_id=999,
)


# ============================================================
# FINAL RESULTS
# ============================================================

alive = evaluation[
    "alive"
]

hp = evaluation[
    "hp"
]

shots = evaluation[
    "shots"
]

hits = evaluation[
    "hits"
]

kills = evaluation[
    "kills"
]


blue_alive = int(
    sum(
        alive[:4]
    )
)

red_alive = int(
    sum(
        alive[4:]
    )
)


if (
    blue_alive > 0
    and red_alive == 0
):

    winner = "BLUE"

elif (
    red_alive > 0
    and blue_alive == 0
):

    winner = "RED"

else:

    winner = (
        "NO DECISIVE WINNER"
    )


print()
print(
    "=============================================="
)

print(
    "FLYSWARM 0.3 — LEARNED FIRE RESULTS"
)

print(
    "=============================================="
)

print(
    f"Simulated time   : "
    f"{evaluation['sim_time']:.2f}s"
)

print(
    f"Wall time        : "
    f"{evaluation['wall_time']:.2f}s"
)

print(
    f"Winner           : "
    f"{winner}"
)

print(
    f"BLUE survivors   : "
    f"{blue_alive}/4"
)

print(
    f"RED survivors    : "
    f"{red_alive}/4"
)

print()


total_shots = int(
    shots.sum()
)

total_hits = int(
    hits.sum()
)


overall_accuracy = (
    total_hits
    / total_shots
    * 100
    if total_shots
    else 0.0
)


print(
    f"Total shots      : "
    f"{total_shots}"
)

print(
    f"Total hits       : "
    f"{total_hits}"
)

print(
    f"Overall accuracy : "
    f"{overall_accuracy:.1f}%"
)

print()


for i in range(N):

    accuracy = (
        hits[i]
        / shots[i]
        * 100
        if shots[i]
        else 0.0
    )


    print(
        f"{names[i]} | "
        f"alive={bool(alive[i])!s:5} | "
        f"HP={hp[i]} | "
        f"shots={shots[i]:2d} | "
        f"hits={hits[i]:2d} | "
        f"acc={accuracy:5.1f}% | "
        f"kills={kills[i]}"
    )


print()
print(
    "Focus-fire behaviour:"
)


for team in [0, 1]:

    label = (
        "BLUE"
        if team == 0
        else "RED"
    )

    avg_focus = (
        evaluation[
            "focus_sum"
        ][team]
        /
        evaluation[
            "focus_steps"
        ][team]

        if evaluation[
            "focus_steps"
        ][team]

        else 0.0
    )


    print(
        f"{label}: "
        f"mean largest target group = "
        f"{avg_focus:.2f}, "
        f"max = "
        f"{evaluation['max_focus'][team]}"
    )


print()
print(
    "Experiment complete."
)
