from flybrain import FlyBrain
from collections import deque
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

SIM_DURATION = 20.0

ARENA_W = 1000
ARENA_H = 700
HUD_W = 300

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

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


# ============================================================
# MATH
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
    # 0 deg = +Y
    return math.degrees(
        math.atan2(dx, dy)
    )


def distance(ax, ay, bx, by):
    return math.hypot(
        bx - ax,
        by - ay
    )


# ============================================================
# BRAIN
# ============================================================

print("Loading 8 MaleCNS brains in batch mode...")

brain = FlyBrain(
    device="cpu",
    batch=N,
    seed=SEED
)

print(
    f"neurons per fly = {brain.n:,}"
)

print(
    f"simulated neurons = "
    f"{brain.n * N:,}"
)

print(
    f"dt = {brain.dt:.3f} s"
)


# sensory populations

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


# motor populations

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
    f"LC9 L/R   = "
    f"{len(lc9_l)} / {len(lc9_r)}"
)

print(
    f"LC10a L/R = "
    f"{len(lc10_l)} / {len(lc10_r)}"
)


# ============================================================
# WARMUP
# ============================================================

print("Warming up swarm...")

for _ in range(WARMUP_STEPS):
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


# Team A starts at bottom, facing upward.
# Team B starts at top, facing downward.

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


# current perceived target per fly

targets = np.full(
    N,
    -1,
    dtype=int
)


# ============================================================
# RATE HISTORIES
# ============================================================

def histories():
    return [
        deque(
            [0] * RATE_WINDOW,
            maxlen=RATE_WINDOW
        )
        for _ in range(N)
    ]


p9_l_hist = histories()
p9_r_hist = histories()

a02_l_hist = histories()
a02_r_hist = histories()


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
    """
    Nearest visible enemy.

    The WORLD knows positions in order to render vision,
    but the brain receives only side/center feature-detector
    stimulation.
    """

    best = -1
    best_distance = float("inf")

    for j in range(N):

        if teams[j] == teams[i]:
            continue

        dx = xs[j] - xs[i]
        dy = ys[j] - ys[i]

        d = math.hypot(dx, dy)

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

        if abs(error) > BODY_FOV / 2:
            continue

        if d < best_distance:
            best = j
            best_distance = d

    return best


# ============================================================
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode(
    (WINDOW_W, WINDOW_H)
)

pygame.display.set_caption(
    "FlySwarm 0.1 — 8 MaleCNS tank agents"
)

font = pygame.font.SysFont(
    "Menlo",
    15
)

big_font = pygame.font.SysFont(
    "Menlo",
    24
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

target_seen_steps = np.zeros(
    N,
    dtype=int
)

body_error_sum = np.zeros(
    N,
    dtype=float
)

turret_error_sum = np.zeros(
    N,
    dtype=float
)


# ============================================================
# LOOP
# ============================================================

while running and sim_t < SIM_DURATION:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False


    # ========================================================
    # PERCEPTION FOR ALL 8 FLIES
    # ========================================================

    body_errors = np.zeros(N)
    turret_errors = np.zeros(N)
    target_distances = np.full(
        N,
        np.nan
    )

    for i in range(N):

        targets[i] = choose_target(i)

        j = targets[i]

        if j < 0:
            continue

        dx = xs[j] - xs[i]
        dy = ys[j] - ys[i]

        target_distances[i] = (
            math.hypot(dx, dy)
        )

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

        target_seen_steps[i] += 1

        body_error_sum[i] += abs(
            body_errors[i]
        )

        turret_error_sum[i] += abs(
            turret_errors[i]
        )


    # ========================================================
    # BATCH SENSOR VECTORS
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

        if targets[i] < 0:
            continue

        # ---------------- BODY / PURSUIT ----------------

        e = body_errors[i]

        if e < -BODY_DEADZONE:

            lc9_l_amount[i] = STIMULUS

        elif e > BODY_DEADZONE:

            lc9_r_amount[i] = STIMULUS

        else:

            # target approximately straight ahead
            lc9_l_amount[i] = STIMULUS
            lc9_r_amount[i] = STIMULUS


        # ---------------- TURRET ----------------

        te = turret_errors[i]

        if abs(te) <= TURRET_FOV / 2:

            if te < -TURRET_DEADZONE:

                lc10_l_amount[i] = STIMULUS

            elif te > TURRET_DEADZONE:

                lc10_r_amount[i] = STIMULUS


    # ========================================================
    # ONE STEP = EIGHT FULL BRAINS
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


    # ========================================================
    # READ EACH BRAIN
    # ========================================================

    speeds = np.zeros(N)
    body_turn_rates = np.zeros(N)
    turret_turn_rates = np.zeros(N)

    p9_l_rates = np.zeros(N)
    p9_r_rates = np.zeros(N)

    a02_l_rates = np.zeros(N)
    a02_r_rates = np.zeros(N)


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


        p9_l_rates[i] = p9_l_rate
        p9_r_rates[i] = p9_r_rate

        a02_l_rates[i] = a02_l_rate
        a02_r_rates[i] = a02_r_rate


        # -----------------------------------------------
        # CHASSIS
        # -----------------------------------------------

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


        turn_signal = (
            p9_r_rate
            - p9_l_rate
        )

        body_turn_rates[i] = clamp(
            turn_signal
            * BODY_TURN_GAIN,
            -MAX_BODY_TURN,
            MAX_BODY_TURN
        )


        # -----------------------------------------------
        # TURRET
        # -----------------------------------------------

        turret_signal = (
            a02_l_rate
            - a02_r_rate
        )

        if abs(turret_signal) < 1.0:
            turret_signal = 0.0

        turret_turn_rates[i] = clamp(
            -turret_signal
            * TURRET_GAIN,
            -MAX_TURRET_TURN,
            MAX_TURRET_TURN
        )


    # ========================================================
    # PHYSICS
    # ========================================================

    for i in range(N):

        body_yaw[i] = wrap_angle(
            body_yaw[i]
            + body_turn_rates[i]
            * brain.dt
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

        # Arena boundary only.
        # No hidden steering assistance.

        xs[i] = clamp(
            xs[i],
            20,
            ARENA_W - 20
        )

        ys[i] = clamp(
            ys[i],
            20,
            ARENA_H - 20
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

            "x": xs[i],
            "y": ys[i],

            "body_yaw":
                body_yaw[i],

            "turret_relative":
                turret_relative[i],

            "target":
                int(targets[i]),

            "target_distance":
                (
                    target_distances[i]
                    if targets[i] >= 0
                    else ""
                ),

            "body_error":
                (
                    body_errors[i]
                    if targets[i] >= 0
                    else ""
                ),

            "turret_error":
                (
                    turret_errors[i]
                    if targets[i] >= 0
                    else ""
                ),

            "speed":
                speeds[i],

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

    # arena background

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


    # grid

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


    # current target links

    for i in range(N):

        j = targets[i]

        if j < 0:
            continue

        sx = int(xs[i])
        sy = int(
            ARENA_H - ys[i]
        )

        tx = int(xs[j])
        ty = int(
            ARENA_H - ys[j]
        )

        pygame.draw.line(
            screen,
            (60, 65, 70),
            (sx, sy),
            (tx, ty),
            1
        )


    # tanks

    for i in range(N):

        sx = int(xs[i])
        sy = int(
            ARENA_H - ys[i]
        )

        if teams[i] == 0:

            colour = (
                70,
                145,
                230
            )

        else:

            colour = (
                225,
                80,
                75
            )


        # body heading

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

        pygame.draw.circle(
            screen,
            colour,
            (sx, sy),
            12
        )

        pygame.draw.line(
            screen,
            colour,
            (sx, sy),
            (hx, hy),
            7
        )


        # turret

        turret_world = wrap_angle(
            body_yaw[i]
            + turret_relative[i]
        )

        tr = math.radians(
            turret_world
        )

        bx = int(
            sx
            + math.sin(tr)
            * 28
        )

        by = int(
            sy
            - math.cos(tr)
            * 28
        )

        pygame.draw.line(
            screen,
            (235, 235, 220),
            (sx, sy),
            (bx, by),
            3
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
                sy + 15
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
        "FlySwarm 0.1",
        True,
        (235, 235, 235)
    )

    screen.blit(
        title,
        (
            ARENA_W + 20,
            20
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


    lines = [
        "",
        f"time       {sim_t:6.2f}s",
        f"sim speed  {sim_speed:6.2f}x",
        "",
        "8 independent",
        "MaleCNS brains",
        "",
        "BLUE",
    ]


    for i in range(4):

        target_name = (
            names[targets[i]]
            if targets[i] >= 0
            else "-"
        )

        lines.append(
            f"{names[i]} -> {target_name:2} "
            f"v={speeds[i]:4.1f}"
        )


    lines += [
        "",
        "RED",
    ]


    for i in range(4, 8):

        target_name = (
            names[targets[i]]
            if targets[i] >= 0
            else "-"
        )

        lines.append(
            f"{names[i]} -> {target_name:2} "
            f"v={speeds[i]:4.1f}"
        )


    y = 65

    for line in lines:

        text = font.render(
            line,
            True,
            (205, 210, 215)
        )

        screen.blit(
            text,
            (
                ARENA_W + 20,
                y
            )
        )

        y += 23


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
    / "flyswarm_01_batch.csv"
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
# METRICS
# ============================================================

print()
print(
    "============================================"
)

print(
    "FLYSWARM 0.1 — RESULTS"
)

print(
    "============================================"
)

print(
    f"Simulated time       : {sim_t:.2f} s"
)

print(
    f"Wall time            : {wall_time:.2f} s"
)

print(
    f"Simulation speed     : "
    f"{sim_t / wall_time:.2f}x realtime"
)

print(
    f"Brains               : {N}"
)

print(
    f"Neurons simulated    : "
    f"{brain.n * N:,}"
)

print()


for i in range(N):

    seen = target_seen_steps[i]

    seen_pct = (
        seen / step * 100
        if step
        else 0
    )

    if seen:

        mean_body = (
            body_error_sum[i]
            / seen
        )

        mean_turret = (
            turret_error_sum[i]
            / seen
        )

    else:

        mean_body = float("nan")
        mean_turret = float("nan")


    print(
        f"{names[i]} | "
        f"target seen={seen_pct:5.1f}% | "
        f"body MAE={mean_body:5.1f}° | "
        f"turret MAE={mean_turret:5.1f}°"
    )


# nearest enemy distances at end

print()
print("Final nearest-enemy distances:")

for i in range(N):

    enemy_distances = [

        distance(
            xs[i],
            ys[i],
            xs[j],
            ys[j]
        )

        for j in range(N)

        if teams[j] != teams[i]
    ]

    print(
        f"{names[i]}: "
        f"{min(enemy_distances):.1f}"
    )


print()
print(
    f"Saved to {csv_path}"
)
