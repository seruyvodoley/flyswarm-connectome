from flybrain import FlyBrain
from collections import deque
from pathlib import Path
import pygame
import math
import csv
import time


# ============================================================
# CONFIG
# ============================================================

WIDTH = 1100
HEIGHT = 750

SIM_DURATION = 20.0

FOV_DEG = 120.0
HALF_FOV = FOV_DEG / 2.0

STIMULUS = 0.8
SENSOR_DEADZONE = 1.5

RATE_WINDOW = 10

TURN_GAIN = 10.0
MAX_TURN_RATE = 80.0

# Gun is automatic in v0.2.
FIRE_ALIGNMENT_DEG = 5.0
HIT_ALIGNMENT_DEG = 2.0
FIRE_COOLDOWN = 0.75

WARMUP_STEPS = 25

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


def target_position(t):
    """
    Target remains in the forward half of the arena,
    but its bearing and distance both change.
    Coordinates:
        x = right
        y = forward
    """
    x = (
        150.0 * math.sin(0.43 * t)
        + 45.0 * math.sin(1.11 * t + 0.7)
    )

    y = (
        280.0
        + 55.0 * math.sin(0.31 * t + 1.2)
        + 20.0 * math.sin(0.83 * t)
    )

    return x, y


def bearing_to(x, y):
    # 0 degrees = straight ahead
    # positive = target to the right
    # negative = target to the left
    return math.degrees(
        math.atan2(x, y)
    )


# ============================================================
# BRAIN
# ============================================================

print("Loading MaleCNS...")

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

print(
    f"LC10a L/R: "
    f"{len(lc10_left)} / {len(lc10_right)}"
)

print(
    f"DNa02 L/R: "
    f"{len(dna_left)} / {len(dna_right)}"
)

print("Warming up...")

for _ in range(WARMUP_STEPS):
    brain.step()


# ============================================================
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT)
)

pygame.display.set_caption(
    "FlyTank 0.2 — MaleCNS turret control"
)

font = pygame.font.SysFont(
    "Menlo",
    17
)

big_font = pygame.font.SysFont(
    "Menlo",
    27
)

clock = pygame.time.Clock()


# ============================================================
# STATE
# ============================================================

turret_yaw = 0.0

left_history = deque(
    maxlen=RATE_WINDOW
)

right_history = deque(
    maxlen=RATE_WINDOW
)

sim_t = 0.0
step = 0

shots = 0
hits = 0

last_shot_time = -999

rows = []

running = True

wall_start = time.perf_counter()


# ============================================================
# MAIN LOOP
# ============================================================

while running and sim_t < SIM_DURATION:

    for event in pygame.event.get():

        if event.type == pygame.QUIT:
            running = False

    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

    target_x, target_y = target_position(
        sim_t
    )

    target_bearing = bearing_to(
        target_x,
        target_y
    )

    pre_error = wrap_angle(
        target_bearing
        - turret_yaw
    )

    visible = (
        abs(pre_error)
        <= HALF_FOV
    )

    # --------------------------------------------------------
    # SENSOR ENCODER
    # --------------------------------------------------------

    inject = []

    if visible:

        if pre_error < -SENSOR_DEADZONE:

            inject.append(
                (lc10_left, STIMULUS)
            )

        elif pre_error > SENSOR_DEADZONE:

            inject.append(
                (lc10_right, STIMULUS)
            )

    # --------------------------------------------------------
    # MALE CNS
    # --------------------------------------------------------

    fired = set(
        brain.step(
            inject=inject
        )
    )

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

    # --------------------------------------------------------
    # TURRET MOTOR DECODER
    # --------------------------------------------------------

    turn_rate = clamp(
        -steering * TURN_GAIN,
        -MAX_TURN_RATE,
        MAX_TURN_RATE
    )

    turret_yaw += (
        turn_rate
        * brain.dt
    )

    turret_yaw = wrap_angle(
        turret_yaw
    )

    # error AFTER brain's action
    post_error = wrap_angle(
        target_bearing
        - turret_yaw
    )

    # --------------------------------------------------------
    # AUTOMATIC GUN
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # firing is NOT brain-controlled in v0.2.
    # This measures aiming performance only.
    # --------------------------------------------------------

    fired_gun = False
    hit = False

    if (
        visible
        and abs(post_error)
        <= FIRE_ALIGNMENT_DEG
        and sim_t - last_shot_time
        >= FIRE_COOLDOWN
    ):

        fired_gun = True
        shots += 1

        last_shot_time = sim_t

        if abs(post_error) <= HIT_ALIGNMENT_DEG:

            hit = True
            hits += 1

    # --------------------------------------------------------
    # LOGGING
    # --------------------------------------------------------

    rows.append({
        "step": step,
        "sim_time_s": sim_t,

        "target_x": target_x,
        "target_y": target_y,

        "target_bearing_deg":
            target_bearing,

        "turret_yaw_deg":
            turret_yaw,

        "error_deg":
            post_error,

        "abs_error_deg":
            abs(post_error),

        "visible":
            int(visible),

        "dna02_left_hz":
            left_rate,

        "dna02_right_hz":
            right_rate,

        "steering_hz":
            steering,

        "turn_rate_deg_s":
            turn_rate,

        "gun_fired":
            int(fired_gun),

        "hit":
            int(hit),
    })

    # ========================================================
    # DRAW
    # ========================================================

    screen.fill(
        (23, 28, 32)
    )

    tank_screen_x = WIDTH // 2
    tank_screen_y = HEIGHT - 140

    SCALE = 0.85

    # --------------------------------------------------------
    # GRID
    # --------------------------------------------------------

    for x in range(
        0,
        WIDTH,
        50
    ):
        pygame.draw.line(
            screen,
            (35, 42, 46),
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
            (35, 42, 46),
            (0, y),
            (WIDTH, y),
            1
        )

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    tx = int(
        tank_screen_x
        + target_x * SCALE
    )

    ty = int(
        tank_screen_y
        - target_y * SCALE
    )

    pygame.draw.rect(
        screen,
        (190, 70, 70),
        (
            tx - 18,
            ty - 12,
            36,
            24
        )
    )

    pygame.draw.circle(
        screen,
        (240, 100, 100),
        (tx, ty),
        28,
        2
    )

    # --------------------------------------------------------
    # TANK BODY
    # --------------------------------------------------------

    body_rect = pygame.Rect(
        tank_screen_x - 35,
        tank_screen_y - 45,
        70,
        90
    )

    pygame.draw.rect(
        screen,
        (90, 115, 90),
        body_rect
    )

    pygame.draw.rect(
        screen,
        (140, 155, 140),
        body_rect,
        2
    )

    # --------------------------------------------------------
    # TURRET
    # --------------------------------------------------------

    pygame.draw.circle(
        screen,
        (120, 145, 115),
        (
            tank_screen_x,
            tank_screen_y
        ),
        23
    )

    # yaw:
    # 0 = upwards
    # positive = right

    rad = math.radians(
        turret_yaw
    )

    barrel_length = 90

    barrel_end_x = int(
        tank_screen_x
        + math.sin(rad)
        * barrel_length
    )

    barrel_end_y = int(
        tank_screen_y
        - math.cos(rad)
        * barrel_length
    )

    pygame.draw.line(
        screen,
        (210, 215, 190),
        (
            tank_screen_x,
            tank_screen_y
        ),
        (
            barrel_end_x,
            barrel_end_y
        ),
        7
    )

    # --------------------------------------------------------
    # AIM LINE
    # --------------------------------------------------------

    if visible:

        pygame.draw.line(
            screen,
            (70, 90, 75),
            (
                tank_screen_x,
                tank_screen_y
            ),
            (tx, ty),
            1
        )

    # muzzle flash
    if fired_gun:

        pygame.draw.circle(
            screen,
            (
                255,
                220 if hit else 140,
                60
            ),
            (
                barrel_end_x,
                barrel_end_y
            ),
            14
        )

    # --------------------------------------------------------
    # HUD
    # --------------------------------------------------------

    title = big_font.render(
        "FlyTank 0.2 — Drosophila MaleCNS turret",
        True,
        (235, 235, 235)
    )

    screen.blit(
        title,
        (20, 18)
    )

    hit_rate = (
        hits / shots * 100
        if shots
        else 0.0
    )

    hud = [
        f"sim time       {sim_t:6.2f} s",
        "",
        f"target bearing {target_bearing:+7.2f} deg",
        f"turret yaw     {turret_yaw:+7.2f} deg",
        f"aim error      {post_error:+7.2f} deg",
        "",
        f"DNa02 L        {left_rate:6.2f} Hz",
        f"DNa02 R        {right_rate:6.2f} Hz",
        f"steering       {steering:+6.2f} Hz",
        f"turn rate      {turn_rate:+6.1f} deg/s",
        "",
        f"shots          {shots}",
        f"hits           {hits}",
        f"hit rate       {hit_rate:5.1f}%",
    ]

    y = 70

    for line in hud:

        text = font.render(
            line,
            True,
            (215, 215, 215)
        )

        screen.blit(
            text,
            (20, y)
        )

        y += 24

    if visible:
        state = "TARGET VISIBLE"
    else:
        state = "TARGET LOST"

    state_text = font.render(
        state,
        True,
        (
            (130, 230, 150)
            if visible
            else
            (240, 100, 100)
        )
    )

    screen.blit(
        state_text,
        (
            WIDTH - 200,
            25
        )
    )

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
    / "flytank_02_turret.csv"
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


mean_error = sum(
    r["abs_error_deg"]
    for r in rows
) / len(rows)

rmse = math.sqrt(
    sum(
        r["error_deg"] ** 2
        for r in rows
    )
    / len(rows)
)

within_5 = (
    sum(
        r["abs_error_deg"] <= 5
        for r in rows
    )
    / len(rows)
    * 100
)

hit_rate = (
    hits / shots * 100
    if shots
    else 0.0
)


print()
print(
    "========================================"
)

print(
    "FLYTANK 0.2 — RESULTS"
)

print(
    "========================================"
)

print(
    f"Simulated time : {sim_t:.2f} s"
)

print(
    f"Wall time      : {wall_time:.2f} s"
)

print(
    f"Mean aim error : {mean_error:.2f} deg"
)

print(
    f"RMSE           : {rmse:.2f} deg"
)

print(
    f"Within ±5 deg  : {within_5:.1f}%"
)

print(
    f"Shots          : {shots}"
)

print(
    f"Hits           : {hits}"
)

print(
    f"Hit rate       : {hit_rate:.1f}%"
)

print()
print(
    f"Saved to {csv_path}"
)
