from flybrain import FlyBrain
from collections import deque, Counter
from pathlib import Path
import pygame
import numpy as np
import math
import csv
import time


# ============================================================
# CONFIG
# ============================================================

N = 8
TEAM_SIZE = 4
SEED = 64

SIM_DURATION = 45.0

ARENA_W = 1000
ARENA_H = 700
HUD_W = 320

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

# ---------------- combat ----------------

TANK_RADIUS = 15.0

MAX_HP = 3

RELOAD_TIME = 1.4
FIRE_RANGE = 500.0
FIRE_ERROR_DEG = 4.0

PROJECTILE_SPEED = 280.0
PROJECTILE_RADIUS = 3
PROJECTILE_LIFETIME = 3.0

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def wrap_angle(a):

    while a > 180:
        a -= 360

    while a < -180:
        a += 360

    return a


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def bearing(dx, dy):

    return math.degrees(
        math.atan2(dx, dy)
    )


def distance(ax, ay, bx, by):

    return math.hypot(
        bx - ax,
        by - ay
    )


def segment_circle_t(
    x1, y1,
    x2, y2,
    cx, cy,
    radius
):
    """
    Return hit position t in [0,1] along segment,
    or None if no intersection.
    """

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
        1.0
    )

    px = x1 + vx * t
    py = y1 + vy * t

    d = math.hypot(
        px - cx,
        py - cy
    )

    if d <= radius:
        return t

    return None


# ============================================================
# BRAIN
# ============================================================

print(
    "Loading 8 MaleCNS brains..."
)

brain = FlyBrain(
    device="cpu",
    batch=N,
    seed=SEED
)

print(
    f"neurons per fly = "
    f"{brain.n:,}"
)

print(
    f"simulated neurons = "
    f"{brain.n * N:,}"
)

print(
    f"dt = {brain.dt:.3f} s"
)


# sensory

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


# motor outputs

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


print(
    f"LC9 L/R    = "
    f"{len(lc9_l)} / {len(lc9_r)}"
)

print(
    f"LC10a L/R  = "
    f"{len(lc10_l)} / {len(lc10_r)}"
)


# ============================================================
# WARMUP
# ============================================================

print("Warming up swarm...")

for _ in range(
    WARMUP_STEPS
):
    brain.step()


# ============================================================
# WORLD
# ============================================================

teams = np.array([
    0, 0, 0, 0,
    1, 1, 1, 1
])

names = [
    "A1", "A2", "A3", "A4",
    "B1", "B2", "B3", "B4"
]


xs = np.array([
    180., 390., 610., 820.,
    180., 390., 610., 820.
])

ys = np.array([
    100., 120., 120., 100.,
    600., 580., 580., 600.
])

body_yaw = np.array([
    0., 0., 0., 0.,
    180., 180., 180., 180.
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

targets = np.full(
    N,
    -1,
    dtype=int
)

last_shot_time = np.full(
    N,
    -999.0
)


# stats

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


# ============================================================
# PROJECTILES
# ============================================================

projectiles = []


# ============================================================
# RATE HISTORIES
# ============================================================

def make_histories():

    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW
        )
        for _ in range(N)
    ]


p9_l_hist = make_histories()
p9_r_hist = make_histories()

a02_l_hist = make_histories()
a02_r_hist = make_histories()


def rate(history, i):

    return (
        sum(history[i])
        / (
            len(history[i])
            * brain.dt
        )
    )


# ============================================================
# PERCEPTION
# ============================================================

def choose_target(i):

    if not alive[i]:
        return -1

    best = -1
    best_distance = float("inf")

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

        if d < best_distance:

            best = j
            best_distance = d

    return best


# ============================================================
# COLLISION PHYSICS
# ============================================================

def resolve_tank_collisions():

    min_distance = (
        TANK_RADIUS * 2
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

            if d >= min_distance:
                continue

            if d < 1e-6:

                # deterministic fallback
                dx = 1.0
                dy = 0.0
                d = 1.0

            overlap = (
                min_distance
                - d
            )

            nx = dx / d
            ny = dy / d

            push = (
                overlap
                / 2.0
            )

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
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode(
    (
        WINDOW_W,
        WINDOW_H
    )
)

pygame.display.set_caption(
    "FlySwarm 0.2 — MaleCNS 4v4 Battle"
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


# ============================================================
# LOGGING
# ============================================================

rows = []

sim_t = 0.0
step = 0

running = True

wall_start = time.perf_counter()

focus_sum = [
    0.0,
    0.0
]

focus_steps = [
    0,
    0
]

max_focus_seen = [
    0,
    0
]


# ============================================================
# MAIN LOOP
# ============================================================

while (
    running
    and sim_t < SIM_DURATION
):

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False


    # stop if one team dead

    blue_alive = sum(
        alive[i]
        for i in range(4)
    )

    red_alive = sum(
        alive[i]
        for i in range(4, 8)
    )

    if (
        blue_alive == 0
        or red_alive == 0
    ):
        break


    # ========================================================
    # PERCEPTION
    # ========================================================

    body_errors = np.zeros(N)
    turret_errors = np.zeros(N)

    target_distances = np.full(
        N,
        np.nan
    )


    for i in range(N):

        targets[i] = (
            choose_target(i)
        )

        j = targets[i]

        if j < 0:
            continue

        dx = xs[j] - xs[i]
        dy = ys[j] - ys[i]

        d = math.hypot(
            dx,
            dy
        )

        target_distances[i] = d

        world_bearing = bearing(
            dx,
            dy
        )

        body_errors[i] = (
            wrap_angle(
                world_bearing
                - body_yaw[i]
            )
        )

        turret_world = wrap_angle(
            body_yaw[i]
            + turret_relative[i]
        )

        turret_errors[i] = (
            wrap_angle(
                world_bearing
                - turret_world
            )
        )


    # ========================================================
    # FOCUS FIRE METRIC
    # ========================================================

    for team in [0, 1]:

        c = Counter()

        for i in range(N):

            if (
                alive[i]
                and teams[i] == team
                and targets[i] >= 0
            ):

                c[
                    int(targets[i])
                ] += 1

        if c:

            current_focus = max(
                c.values()
            )

            focus_sum[team] += (
                current_focus
            )

            focus_steps[team] += 1

            max_focus_seen[team] = max(
                max_focus_seen[team],
                current_focus
            )


    # ========================================================
    # SENSOR VECTORS
    # ========================================================

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


        e = body_errors[i]

        if e < -BODY_DEADZONE:

            lc9_l_amount[i] = (
                STIMULUS
            )

        elif e > BODY_DEADZONE:

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


    # ========================================================
    # 8 BRAINS
    # ========================================================

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


    speeds = np.zeros(N)
    body_turn_rates = np.zeros(N)
    turret_turn_rates = np.zeros(N)

    p9_l_rates = np.zeros(N)
    p9_r_rates = np.zeros(N)

    a02_l_rates = np.zeros(N)
    a02_r_rates = np.zeros(N)


    # ========================================================
    # MOTOR OUTPUTS
    # ========================================================

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


        p9_l_rate = rate(
            p9_l_hist,
            i
        )

        p9_r_rate = rate(
            p9_r_hist,
            i
        )

        a02_l_rate = rate(
            a02_l_hist,
            i
        )

        a02_r_rate = rate(
            a02_r_hist,
            i
        )


        p9_l_rates[i] = (
            p9_l_rate
        )

        p9_r_rates[i] = (
            p9_r_rate
        )

        a02_l_rates[i] = (
            a02_l_rate
        )

        a02_r_rates[i] = (
            a02_r_rate
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


        body_turn_rates[i] = clamp(
            (
                p9_r_rate
                - p9_l_rate
            )
            * BODY_TURN_GAIN,

            -MAX_BODY_TURN,
            MAX_BODY_TURN
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


    # ========================================================
    # TANK PHYSICS
    # ========================================================

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


    resolve_tank_collisions()


    # ========================================================
    # UPDATE EXISTING PROJECTILES
    # ========================================================

    new_projectiles = []


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

        p["age"] += brain.dt


        best_hit = None
        best_t = float("inf")


        for j in range(N):

            if (
                not alive[j]
                or teams[j]
                == p["team"]
            ):
                continue


            hit_t = segment_circle_t(
                old_x,
                old_y,
                new_x,
                new_y,
                xs[j],
                ys[j],
                TANK_RADIUS
            )


            if (
                hit_t is not None
                and hit_t < best_t
            ):

                best_t = hit_t
                best_hit = j


        if best_hit is not None:

            victim = best_hit
            owner = p["owner"]

            hp[victim] -= 1

            hits[owner] += 1


            if hp[victim] <= 0:

                alive[victim] = False
                hp[victim] = 0

                kills[owner] += 1

                targets[victim] = -1


            # projectile disappears
            continue


        p["x"] = new_x
        p["y"] = new_y


        if (
            p["age"]
            < PROJECTILE_LIFETIME
            and
            0 <= new_x <= ARENA_W
            and
            0 <= new_y <= ARENA_H
        ):

            new_projectiles.append(
                p
            )


    projectiles = new_projectiles


    # ========================================================
    # AUTOMATIC FIRING
    # ========================================================
    #
    # Brain aims.
    # Firing decision itself is still rule-based.
    # ========================================================

    for i in range(N):

        if not alive[i]:
            continue

        j = targets[i]

        if (
            j < 0
            or not alive[j]
        ):
            continue


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
            body_yaw[i]
            + turret_relative[i]
        )

        aim_error = wrap_angle(
            target_bearing
            - turret_world
        )


        if (
            d <= FIRE_RANGE
            and
            abs(aim_error)
            <= FIRE_ERROR_DEG
            and
            sim_t
            - last_shot_time[i]
            >= RELOAD_TIME
        ):

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


            projectiles.append({
                "x": muzzle_x,
                "y": muzzle_y,

                "vx":
                    math.sin(rad)
                    * PROJECTILE_SPEED,

                "vy":
                    math.cos(rad)
                    * PROJECTILE_SPEED,

                "team":
                    int(teams[i]),

                "owner":
                    i,

                "age":
                    0.0,
            })


            shots[i] += 1

            last_shot_time[i] = (
                sim_t
            )


    # ========================================================
    # LOG
    # ========================================================

    for i in range(N):

        rows.append({
            "step": step,
            "time": sim_t,

            "fly": i,
            "name": names[i],
            "team": int(teams[i]),

            "alive":
                int(alive[i]),

            "hp":
                int(hp[i]),

            "x":
                xs[i],

            "y":
                ys[i],

            "body_yaw":
                body_yaw[i],

            "turret_relative":
                turret_relative[i],

            "target":
                int(targets[i]),

            "speed":
                speeds[i],

            "shots":
                int(shots[i]),

            "hits":
                int(hits[i]),

            "kills":
                int(kills[i]),

            "DNp09_L":
                p9_l_rates[i],

            "DNp09_R":
                p9_r_rates[i],

            "DNa02_L":
                a02_l_rates[i],

            "DNa02_R":
                a02_r_rates[i],
        })


    # ========================================================
    # DRAW
    # ========================================================

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
            (gx, 0),
            (gx, ARENA_H),
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
            (0, gy),
            (ARENA_W, gy),
            1
        )


    # --------------------------------------------------------
    # TARGET LINES
    # --------------------------------------------------------

    for i in range(N):

        if (
            not alive[i]
            or targets[i] < 0
        ):
            continue


        j = targets[i]

        if not alive[j]:
            continue


        pygame.draw.line(
            screen,
            (55, 60, 65),
            (
                int(xs[i]),
                int(
                    ARENA_H
                    - ys[i]
                )
            ),
            (
                int(xs[j]),
                int(
                    ARENA_H
                    - ys[j]
                )
            ),
            1
        )


    # --------------------------------------------------------
    # PROJECTILES
    # --------------------------------------------------------

    for p in projectiles:

        pygame.draw.circle(
            screen,
            (255, 215, 80),
            (
                int(p["x"]),
                int(
                    ARENA_H
                    - p["y"]
                )
            ),
            PROJECTILE_RADIUS
        )


    # --------------------------------------------------------
    # TANKS
    # --------------------------------------------------------

    for i in range(N):

        sx = int(xs[i])

        sy = int(
            ARENA_H
            - ys[i]
        )


        if teams[i] == 0:

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
                (70, 70, 70),
                (sx, sy),
                13
            )

            pygame.draw.line(
                screen,
                (140, 140, 140),
                (
                    sx - 10,
                    sy - 10
                ),
                (
                    sx + 10,
                    sy + 10
                ),
                3
            )

            pygame.draw.line(
                screen,
                (140, 140, 140),
                (
                    sx + 10,
                    sy - 10
                ),
                (
                    sx - 10,
                    sy + 10
                ),
                3
            )

            continue


        # body

        pygame.draw.circle(
            screen,
            colour,
            (sx, sy),
            int(TANK_RADIUS)
        )


        body_rad = math.radians(
            body_yaw[i]
        )

        hx = int(
            sx
            + math.sin(body_rad)
            * 22
        )

        hy = int(
            sy
            - math.cos(body_rad)
            * 22
        )

        pygame.draw.line(
            screen,
            colour,
            (sx, sy),
            (hx, hy),
            7
        )


        # turret

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
            (240, 240, 220),
            (sx, sy),
            (bx, by),
            3
        )


        # HP dots

        for h in range(
            hp[i]
        ):

            pygame.draw.circle(
                screen,
                (110, 240, 120),
                (
                    sx
                    - 8
                    + h * 8,
                    sy + 21
                ),
                2
            )


        label = font.render(
            names[i],
            True,
            (240, 240, 240)
        )

        screen.blit(
            label,
            (
                sx - 10,
                sy + 25
            )
        )


    # ========================================================
    # HUD
    # ========================================================

    pygame.draw.rect(
        screen,
        (12, 14, 18),
        (
            ARENA_W,
            0,
            HUD_W,
            ARENA_H
        )
    )


    title = big_font.render(
        "FlySwarm 0.2",
        True,
        (235, 235, 235)
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


    blue_alive = sum(
        alive[:4]
    )

    red_alive = sum(
        alive[4:]
    )


    lines = [
        "",
        f"time       {sim_t:6.2f}s",
        f"sim speed  {sim_speed:5.2f}x",
        "",
        f"BLUE alive {blue_alive}/4",
        f"RED  alive {red_alive}/4",
        "",
        "BLUE",
    ]


    for i in range(4):

        target_name = (
            names[targets[i]]
            if (
                targets[i] >= 0
                and alive[i]
            )
            else "-"
        )

        lines.append(
            f"{names[i]} "
            f"HP={hp[i]} "
            f"K={kills[i]} "
            f"->{target_name}"
        )


    lines += [
        "",
        "RED",
    ]


    for i in range(
        4,
        8
    ):

        target_name = (
            names[targets[i]]
            if (
                targets[i] >= 0
                and alive[i]
            )
            else "-"
        )

        lines.append(
            f"{names[i]} "
            f"HP={hp[i]} "
            f"K={kills[i]} "
            f"->{target_name}"
        )


    y = 60

    for line in lines:

        text = font.render(
            line,
            True,
            (205, 210, 215)
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

    sim_t += brain.dt
    step += 1


# ============================================================
# END
# ============================================================

pygame.quit()

wall_time = (
    time.perf_counter()
    - wall_start
)


# ============================================================
# SAVE
# ============================================================

csv_path = (
    RESULTS
    / "flyswarm_02_battle.csv"
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
# RESULTS
# ============================================================

blue_alive = int(
    sum(alive[:4])
)

red_alive = int(
    sum(alive[4:])
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
    winner = "NO DECISIVE WINNER"


print()
print(
    "=============================================="
)

print(
    "FLYSWARM 0.2 — BATTLE RESULTS"
)

print(
    "=============================================="
)

print(
    f"Simulated time    : "
    f"{sim_t:.2f} s"
)

print(
    f"Wall time         : "
    f"{wall_time:.2f} s"
)

print(
    f"Simulation speed  : "
    f"{sim_t / wall_time:.2f}x"
)

print()

print(
    f"Winner            : "
    f"{winner}"
)

print(
    f"BLUE survivors    : "
    f"{blue_alive}/4"
)

print(
    f"RED survivors     : "
    f"{red_alive}/4"
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
print("Focus-fire behaviour:")


for team in [0, 1]:

    label = (
        "BLUE"
        if team == 0
        else "RED"
    )

    avg_focus = (
        focus_sum[team]
        / focus_steps[team]
        if focus_steps[team]
        else 0.0
    )

    print(
        f"{label}: "
        f"mean largest target group = "
        f"{avg_focus:.2f}, "
        f"max = "
        f"{max_focus_seen[team]}"
    )


print()
print(
    f"Saved to {csv_path}"
)
