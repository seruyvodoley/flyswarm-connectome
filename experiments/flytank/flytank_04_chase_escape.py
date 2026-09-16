from flybrain import FlyBrain
from collections import deque, Counter
from pathlib import Path
import pygame
import math
import csv
import time


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1200
HEIGHT = 800

SIM_DURATION = 40.0
SEED = 64

CHASE_STIMULUS = 0.8

RATE_WINDOW = 10
LOOM_WINDOW = 5

WARMUP_STEPS = 25
BASELINE_STEPS = 100

BODY_FOV = 150.0
TURRET_FOV = 120.0

BODY_DEADZONE = 4.0
TURRET_DEADZONE = 1.5

# Object's effective visual radius in world units
TARGET_VISUAL_RADIUS = 20.0

# angular expansion rate -> LC4/LPLC2 current
#
# About:
#   0.4 deg/s -> 0.05
#   0.8 deg/s -> 0.10
#   1.7 deg/s -> 0.20
#   3.3 deg/s -> 0.40
#   6.7 deg/s -> 0.80
LOOM_GAIN = 0.12
LOOM_MIN_INPUT = 0.05
LOOM_MAX_INPUT = 1.0

# Pursuit motor decoder
P9_DEADZONE = 2.0
FORWARD_GAIN = 1.8
MAX_FORWARD_SPEED = 32.0

BODY_TURN_GAIN = 5.0
MAX_BODY_TURN = 60.0

# Escape motor decoder
#
# From Exp. 007:
# input~0.1 -> mean(DNp02,DNp04) ~12 Hz
# input~0.2 -> ~18 Hz
#
# So escape should first brake, then overcome pursuit.
REVERSE_GAIN = 1.65
MAX_REVERSE_SPEED = 28.0

# Turret decoder
TURRET_GAIN = 10.0
MAX_TURRET_TURN = 80.0

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def wrap_angle(angle):
    while angle > 180:
        angle -= 360
    while angle < -180:
        angle += 360
    return angle


def bearing(dx, dy):
    return math.degrees(
        math.atan2(dx, dy)
    )


def angular_size(distance):
    """
    Apparent angular diameter of target.
    """
    return math.degrees(
        2.0 * math.atan2(
            TARGET_VISUAL_RADIUS,
            max(distance, 0.001)
        )
    )


def target_position(t):
    """
    Moving opponent.
    Keeps moving generally away while weaving.
    """
    x = (
        120.0 * math.sin(0.22 * t)
        + 35.0 * math.sin(0.55 * t + 0.8)
    )

    y = (
        300.0
        + 14.0 * t
        + 25.0 * math.sin(0.18 * t + 0.5)
    )

    return x, y


def count_spikes(fired, neuron_set):
    return len(
        fired.intersection(neuron_set)
    )


# ============================================================
# BRAIN
# ============================================================

print("Loading MaleCNS...")

brain = FlyBrain(
    device="cpu",
    seed=SEED
)

print(
    f"dt = {brain.dt:.3f} s"
)

# Pursuit vision
lc9_l = brain.cells(["LC9"], side="L")
lc9_r = brain.cells(["LC9"], side="R")

# Turret tracking vision
lc10_l = brain.cells(["LC10a"], side="L")
lc10_r = brain.cells(["LC10a"], side="R")

# Looming
lc4_l = brain.cells(["LC4"], side="L")
lc4_r = brain.cells(["LC4"], side="R")

lplc2_l = brain.cells(["LPLC2"], side="L")
lplc2_r = brain.cells(["LPLC2"], side="R")

# Pursuit outputs
p9_l = brain.cells(["DNp09"], side="L")
p9_r = brain.cells(["DNp09"], side="R")

# Turret outputs
a02_l = brain.cells(["DNa02"], side="L")
a02_r = brain.cells(["DNa02"], side="R")

# Escape outputs
p01 = brain.cells(["DNp01"])
p02 = brain.cells(["DNp02"])
p04 = brain.cells(["DNp04"])
p11 = brain.cells(["DNp11"])


SETS = {
    "p9_l": set(p9_l),
    "p9_r": set(p9_r),

    "a02_l": set(a02_l),
    "a02_r": set(a02_r),

    "p01": set(p01),
    "p02": set(p02),
    "p04": set(p04),
    "p11": set(p11),
}


print(
    f"DNp09 L/R: {len(p9_l)} / {len(p9_r)}"
)

print(
    f"DNa02 L/R: {len(a02_l)} / {len(a02_r)}"
)

print(
    "Escape outputs:",
    f"DNp01={len(p01)}",
    f"DNp02={len(p02)}",
    f"DNp04={len(p04)}",
    f"DNp11={len(p11)}"
)


# ============================================================
# WARMUP + BASELINE
# ============================================================

print("Warming up...")

for _ in range(WARMUP_STEPS):
    brain.step()


baseline_sequences = []

for _ in range(BASELINE_STEPS):
    baseline_sequences.append(
        set(brain.step())
    )


def baseline_rate(name):
    cells = SETS[name]

    if not cells:
        return 0.0

    spikes = sum(
        count_spikes(fired, cells)
        for fired in baseline_sequences
    )

    return (
        spikes
        / len(cells)
        / (BASELINE_STEPS * brain.dt)
    )


BASELINES = {
    name: baseline_rate(name)
    for name in SETS
}


print()
print("Baseline rates:")

for name in [
    "p01",
    "p02",
    "p04",
    "p11"
]:
    print(
        f"  {name}: "
        f"{BASELINES[name]:.2f} Hz"
    )


# ============================================================
# HISTORIES
# ============================================================

def make_history(name):
    """
    Initialize rolling window with the real final
    baseline samples rather than zeros.
    """

    h = deque(
        maxlen=RATE_WINDOW
    )

    for fired in baseline_sequences[
        -RATE_WINDOW:
    ]:
        h.append(
            count_spikes(
                fired,
                SETS[name]
            )
        )

    return h


histories = {
    name: make_history(name)
    for name in SETS
}


def rate(name):
    h = histories[name]
    cells = SETS[name]

    if not cells:
        return 0.0

    return (
        sum(h)
        / len(cells)
        / (len(h) * brain.dt)
    )


# ============================================================
# WORLD
# ============================================================

tank_x = 0.0
tank_y = 0.0

body_yaw = 0.0
turret_relative_yaw = 0.0

target_x, target_y = target_position(0)

initial_distance = math.hypot(
    target_x - tank_x,
    target_y - tank_y
)

previous_angular_size = angular_size(
    initial_distance
)

loom_history = deque(
    [0.0] * LOOM_WINDOW,
    maxlen=LOOM_WINDOW
)


# ============================================================
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT)
)

pygame.display.set_caption(
    "FlyTank 0.4 — CHASE vs ESCAPE"
)

font = pygame.font.SysFont(
    "Menlo",
    16
)

big_font = pygame.font.SysFont(
    "Menlo",
    26
)

clock = pygame.time.Clock()


# ============================================================
# RUN
# ============================================================

rows = []

sim_t = 0.0
step = 0

running = True

wall_start = time.perf_counter()

mode_counter = Counter()
mode_transitions = 0
previous_mode = None


while running and sim_t < SIM_DURATION:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --------------------------------------------------------
    # WORLD GEOMETRY
    # --------------------------------------------------------

    target_x, target_y = target_position(
        sim_t
    )

    dx = target_x - tank_x
    dy = target_y - tank_y

    distance = math.hypot(
        dx,
        dy
    )

    target_bearing = bearing(
        dx,
        dy
    )

    body_error = wrap_angle(
        target_bearing
        - body_yaw
    )

    turret_world_yaw = wrap_angle(
        body_yaw
        + turret_relative_yaw
    )

    turret_error = wrap_angle(
        target_bearing
        - turret_world_yaw
    )

    body_visible = (
        abs(body_error)
        <= BODY_FOV / 2
    )

    turret_visible = (
        abs(turret_error)
        <= TURRET_FOV / 2
    )


    # ========================================================
    # LOOMING VISUAL SIGNAL
    # ========================================================

    current_angular_size = (
        angular_size(distance)
    )

    raw_loom_rate = (
        current_angular_size
        - previous_angular_size
    ) / brain.dt

    previous_angular_size = (
        current_angular_size
    )

    loom_history.append(
        raw_loom_rate
    )

    smooth_loom_rate = (
        sum(loom_history)
        / len(loom_history)
    )

    # Contraction does not excite looming detector
    positive_loom = max(
        0.0,
        smooth_loom_rate
    )

    loom_amount = clamp(
        positive_loom * LOOM_GAIN,
        0.0,
        LOOM_MAX_INPUT
    )

    if loom_amount < LOOM_MIN_INPUT:
        loom_amount = 0.0


    # ========================================================
    # SENSORY ENCODER
    # ========================================================

    inject = []

    # --------------------------------------------------------
    # LC9 — PURSUIT
    # --------------------------------------------------------

    if body_visible:

        if body_error < -BODY_DEADZONE:

            inject.append(
                (lc9_l, CHASE_STIMULUS)
            )

        elif body_error > BODY_DEADZONE:

            inject.append(
                (lc9_r, CHASE_STIMULUS)
            )

        else:

            inject.append(
                (lc9_l, CHASE_STIMULUS)
            )

            inject.append(
                (lc9_r, CHASE_STIMULUS)
            )


    # --------------------------------------------------------
    # LC10a — TURRET TRACKING
    # --------------------------------------------------------

    if turret_visible:

        if turret_error < -TURRET_DEADZONE:

            inject.append(
                (lc10_l, CHASE_STIMULUS)
            )

        elif turret_error > TURRET_DEADZONE:

            inject.append(
                (lc10_r, CHASE_STIMULUS)
            )


    # --------------------------------------------------------
    # LC4 + LPLC2 — LOOMING
    # --------------------------------------------------------

    if (
        body_visible
        and loom_amount > 0
    ):

        inject.extend([
            (lc4_l, loom_amount),
            (lc4_r, loom_amount),
            (lplc2_l, loom_amount),
            (lplc2_r, loom_amount),
        ])


    # ========================================================
    # FULL CNS STEP
    # ========================================================

    fired = set(
        brain.step(
            inject=inject
        )
    )


    for name in histories:
        histories[name].append(
            count_spikes(
                fired,
                SETS[name]
            )
        )


    # ========================================================
    # MOTOR OUTPUTS
    # ========================================================

    p9_l_rate = rate("p9_l")
    p9_r_rate = rate("p9_r")

    a02_l_rate = rate("a02_l")
    a02_r_rate = rate("a02_r")

    p01_rate = rate("p01")
    p02_rate = rate("p02")
    p04_rate = rate("p04")
    p11_rate = rate("p11")


    # Escape activity above spontaneous baseline

    p01_delta = max(
        0.0,
        p01_rate - BASELINES["p01"]
    )

    p02_delta = max(
        0.0,
        p02_rate - BASELINES["p02"]
    )

    p04_delta = max(
        0.0,
        p04_rate - BASELINES["p04"]
    )

    p11_delta = max(
        0.0,
        p11_rate - BASELINES["p11"]
    )


    # ========================================================
    # CHASE DRIVE
    # ========================================================

    pursuit_drive = (
        p9_l_rate
        + p9_r_rate
    )

    pursuit_drive = max(
        0.0,
        pursuit_drive
        - P9_DEADZONE
    )

    forward_component = (
        pursuit_drive
        * FORWARD_GAIN
    )


    # ========================================================
    # ESCAPE DRIVE
    # ========================================================
    #
    # DNp02 -> backward postural movement
    # DNp02 + DNp04 -> backward escape bias
    #
    # DNp01 is monitored as danger but is not directly
    # interpreted as reverse throttle.
    # ========================================================

    backward_escape_drive = (
        p02_delta
        + p04_delta
    ) / 2.0

    reverse_component = (
        backward_escape_drive
        * REVERSE_GAIN
    )


    # ========================================================
    # COMPETITION:
    #
    # CHASE and ESCAPE continuously fight over velocity.
    # ========================================================

    speed = clamp(
        forward_component
        - reverse_component,
        -MAX_REVERSE_SPEED,
        MAX_FORWARD_SPEED
    )


    # --------------------------------------------------------
    # CHASSIS STEERING
    # --------------------------------------------------------

    body_turn_signal = (
        p9_r_rate
        - p9_l_rate
    )

    body_turn_rate = clamp(
        body_turn_signal
        * BODY_TURN_GAIN,
        -MAX_BODY_TURN,
        MAX_BODY_TURN
    )


    body_yaw = wrap_angle(
        body_yaw
        + body_turn_rate
        * brain.dt
    )


    body_rad = math.radians(
        body_yaw
    )


    tank_x += (
        math.sin(body_rad)
        * speed
        * brain.dt
    )

    tank_y += (
        math.cos(body_rad)
        * speed
        * brain.dt
    )


    # --------------------------------------------------------
    # TURRET
    # --------------------------------------------------------

    turret_signal = (
        a02_l_rate
        - a02_r_rate
    )

    if abs(turret_signal) < 1.0:
        turret_signal = 0.0


    turret_turn_rate = clamp(
        -turret_signal
        * TURRET_GAIN,
        -MAX_TURRET_TURN,
        MAX_TURRET_TURN
    )


    turret_relative_yaw = wrap_angle(
        turret_relative_yaw
        + turret_turn_rate
        * brain.dt
    )


    # ========================================================
    # MODE LABEL — OBSERVATIONAL ONLY
    # ========================================================

    if speed < -1.0:
        mode = "ESCAPE"

    elif reverse_component > 3.0:
        mode = "BRAKE"

    else:
        mode = "CHASE"


    mode_counter[mode] += 1

    if (
        previous_mode is not None
        and mode != previous_mode
    ):
        mode_transitions += 1

    previous_mode = mode


    # ========================================================
    # POST-ACTION STATE
    # ========================================================

    dx2 = target_x - tank_x
    dy2 = target_y - tank_y

    post_distance = math.hypot(
        dx2,
        dy2
    )

    post_bearing = bearing(
        dx2,
        dy2
    )

    post_body_error = wrap_angle(
        post_bearing
        - body_yaw
    )

    post_turret_world = wrap_angle(
        body_yaw
        + turret_relative_yaw
    )

    post_turret_error = wrap_angle(
        post_bearing
        - post_turret_world
    )


    # ========================================================
    # LOG
    # ========================================================

    rows.append({
        "step": step,
        "sim_time_s": sim_t,

        "tank_x": tank_x,
        "tank_y": tank_y,

        "target_x": target_x,
        "target_y": target_y,

        "distance": post_distance,

        "angular_size_deg":
            current_angular_size,

        "loom_rate_deg_s":
            smooth_loom_rate,

        "loom_input":
            loom_amount,

        "body_error_deg":
            post_body_error,

        "turret_error_deg":
            post_turret_error,

        "DNp09_L_hz":
            p9_l_rate,

        "DNp09_R_hz":
            p9_r_rate,

        "DNa02_L_hz":
            a02_l_rate,

        "DNa02_R_hz":
            a02_r_rate,

        "DNp01_delta_hz":
            p01_delta,

        "DNp02_delta_hz":
            p02_delta,

        "DNp04_delta_hz":
            p04_delta,

        "DNp11_delta_hz":
            p11_delta,

        "forward_component":
            forward_component,

        "reverse_component":
            reverse_component,

        "speed":
            speed,

        "mode":
            mode,
    })


    # ========================================================
    # DRAW
    # ========================================================

    screen.fill(
        (20, 24, 27)
    )

    tank_sx = WIDTH // 2
    tank_sy = int(
        HEIGHT * 0.68
    )

    SCALE = 1.1


    # Grid

    for x in range(
        0,
        WIDTH,
        50
    ):
        pygame.draw.line(
            screen,
            (32, 38, 42),
            (x, 0),
            (x, HEIGHT),
            1
        )

    for y in range(
        0,
        HEIGHT,
        50
    ):
        pygame.draw.line(
            screen,
            (32, 38, 42),
            (0, y),
            (WIDTH, y),
            1
        )


    # Target relative to tank

    rel_x = target_x - tank_x
    rel_y = target_y - tank_y

    tx = int(
        tank_sx
        + rel_x * SCALE
    )

    ty = int(
        tank_sy
        - rel_y * SCALE
    )


    pygame.draw.circle(
        screen,
        (210, 70, 70),
        (tx, ty),
        max(
            5,
            int(
                TARGET_VISUAL_RADIUS
                * SCALE
            )
        )
    )


    # Body

    body_surface = pygame.Surface(
        (80, 105),
        pygame.SRCALPHA
    )

    pygame.draw.rect(
        body_surface,
        (85, 115, 90),
        (10, 10, 60, 85)
    )

    rotated_body = pygame.transform.rotate(
        body_surface,
        -body_yaw
    )

    rect = rotated_body.get_rect(
        center=(
            tank_sx,
            tank_sy
        )
    )

    screen.blit(
        rotated_body,
        rect
    )


    # Turret

    pygame.draw.circle(
        screen,
        (125, 150, 120),
        (tank_sx, tank_sy),
        22
    )


    turret_world = wrap_angle(
        body_yaw
        + turret_relative_yaw
    )

    rad = math.radians(
        turret_world
    )

    bx = int(
        tank_sx
        + math.sin(rad) * 90
    )

    by = int(
        tank_sy
        - math.cos(rad) * 90
    )

    pygame.draw.line(
        screen,
        (215, 220, 195),
        (tank_sx, tank_sy),
        (bx, by),
        7
    )


    # ========================================================
    # HUD
    # ========================================================

    title = big_font.render(
        "FlyTank 0.4 — CHASE vs ESCAPE",
        True,
        (235, 235, 235)
    )

    screen.blit(
        title,
        (20, 18)
    )


    hud = [
        f"MODE              {mode}",
        "",
        f"distance          {post_distance:7.1f}",
        f"speed             {speed:+7.2f}",
        "",
        f"angular size      {current_angular_size:7.2f} deg",
        f"loom rate         {smooth_loom_rate:+7.2f} deg/s",
        f"loom input        {loom_amount:7.3f}",
        "",
        f"CHASE drive       {forward_component:7.2f}",
        f"ESCAPE drive      {reverse_component:7.2f}",
        "",
        f"DNp09 L/R         {p9_l_rate:5.1f} / {p9_r_rate:5.1f}",
        f"DNp02 delta       {p02_delta:7.2f}",
        f"DNp04 delta       {p04_delta:7.2f}",
        f"DNp01 danger      {p01_delta:7.2f}",
        f"DNp11 forward     {p11_delta:7.2f}",
        "",
        f"body error        {post_body_error:+7.2f}",
        f"turret error      {post_turret_error:+7.2f}",
    ]


    y = 65

    for line in hud:

        if mode == "ESCAPE":
            colour = (
                245,
                120,
                100
            )

        elif mode == "BRAKE":
            colour = (
                245,
                210,
                100
            )

        else:
            colour = (
                210,
                220,
                210
            )

        text = font.render(
            line,
            True,
            colour
        )

        screen.blit(
            text,
            (20, y)
        )

        y += 22


    pygame.display.flip()

    clock.tick(1000)

    sim_t += brain.dt
    step += 1


# ============================================================
# FINISH
# ============================================================

pygame.quit()

wall_time = (
    time.perf_counter()
    - wall_start
)


csv_path = (
    RESULTS
    / "flytank_04_chase_escape.csv"
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

minimum_distance = min(
    r["distance"]
    for r in rows
)

maximum_distance = max(
    r["distance"]
    for r in rows
)

final_distance = rows[-1][
    "distance"
]

last_10 = [
    r["distance"]
    for r in rows
    if r["sim_time_s"]
    >= SIM_DURATION - 10
]

mean_last10_distance = (
    sum(last_10)
    / len(last_10)
)

max_loom = max(
    r["loom_rate_deg_s"]
    for r in rows
)

max_loom_input = max(
    r["loom_input"]
    for r in rows
)

reverse_pct = (
    sum(
        r["speed"] < -1
        for r in rows
    )
    / len(rows)
    * 100
)

brake_pct = (
    sum(
        r["mode"] == "BRAKE"
        for r in rows
    )
    / len(rows)
    * 100
)

chase_pct = (
    sum(
        r["mode"] == "CHASE"
        for r in rows
    )
    / len(rows)
    * 100
)

mean_body_error = (
    sum(
        abs(r["body_error_deg"])
        for r in rows
    )
    / len(rows)
)

mean_turret_error = (
    sum(
        abs(r["turret_error_deg"])
        for r in rows
    )
    / len(rows)
)


print()
print(
    "=========================================="
)

print(
    "FLYTANK 0.4 — CHASE / ESCAPE RESULTS"
)

print(
    "=========================================="
)

print(
    f"Simulated time       : {sim_t:.2f} s"
)

print(
    f"Wall time            : {wall_time:.2f} s"
)

print()

print(
    f"Start distance       : {initial_distance:.1f}"
)

print(
    f"Minimum distance     : {minimum_distance:.1f}"
)

print(
    f"Final distance       : {final_distance:.1f}"
)

print(
    f"Mean distance last10 : {mean_last10_distance:.1f}"
)

print()

print(
    f"CHASE time           : {chase_pct:.1f}%"
)

print(
    f"BRAKE time           : {brake_pct:.1f}%"
)

print(
    f"ESCAPE time          : {reverse_pct:.1f}%"
)

print(
    f"Mode transitions     : {mode_transitions}"
)

print()

print(
    f"Max loom rate        : {max_loom:.2f} deg/s"
)

print(
    f"Max loom input       : {max_loom_input:.3f}"
)

print()

print(
    f"Mean body error      : {mean_body_error:.2f} deg"
)

print(
    f"Mean turret error    : {mean_turret_error:.2f} deg"
)

print()

print(
    f"Saved to {csv_path}"
)
