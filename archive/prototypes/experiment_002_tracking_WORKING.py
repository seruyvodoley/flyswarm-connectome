from flybrain import FlyBrain
from pathlib import Path
from collections import deque
import pygame
import math
import csv
import time

# ============================================================
# CONFIG
# ============================================================

WIDTH = 1000
HEIGHT = 600

FOV_DEG = 120.0
HALF_FOV = FOV_DEG / 2

SIM_DURATION = 10.0       # simulated seconds
STIMULUS = 0.8

# DNa02 firing-rate -> camera angular velocity
TURN_GAIN = 10.0          # deg/s per Hz
MAX_TURN_RATE = 80.0      # deg/s

# firing-rate estimation window
RATE_WINDOW = 10          # 10 * 20ms = 200 ms

# don't react to tiny asymmetries
STEERING_DEADZONE = 1.0   # Hz

RESULTS = Path("results")
RESULTS.mkdir(exist_ok=True)


# ============================================================
# HELPERS
# ============================================================

def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def target_angle(t):
    """
    Moving target in world coordinates.

    Two sinusoids prevent perfectly periodic/simple tracking.
    """
    return (
        30.0 * math.sin(0.55 * t)
        + 10.0 * math.sin(1.30 * t)
    )


# ============================================================
# BRAIN
# ============================================================

print("Loading MaleCNS...")

brain = FlyBrain(device="cpu")

print(f"Brain dt: {brain.dt:.3f} s")

lc10_left = brain.cells(["LC10a"], side="L")
lc10_right = brain.cells(["LC10a"], side="R")

dna_left = brain.cells(["DNa02"], side="L")
dna_right = brain.cells(["DNa02"], side="R")

dna_left_set = set(dna_left)
dna_right_set = set(dna_right)

print(f"LC10a L/R: {len(lc10_left)} / {len(lc10_right)}")
print(f"DNa02 L/R: {len(dna_left)} / {len(dna_right)}")


# ============================================================
# WARMUP
# ============================================================

print("Warming up brain...")

for _ in range(25):
    brain.step()


# ============================================================
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))

pygame.display.set_caption(
    "FlyTank 0.1 — Drosophila MaleCNS Target Tracking"
)

font = pygame.font.SysFont("Menlo", 18)
big_font = pygame.font.SysFont("Menlo", 28)

clock = pygame.time.Clock()


# ============================================================
# STATE
# ============================================================

camera_yaw = 0.0

left_history = deque(maxlen=RATE_WINDOW)
right_history = deque(maxlen=RATE_WINDOW)

sim_t = 0.0
step = 0

rows = []

running = True

wall_start = time.perf_counter()


# ============================================================
# LOOP
# ============================================================

while running and sim_t < SIM_DURATION:

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --------------------------------------------------------
    # WORLD
    # --------------------------------------------------------

    world_target = target_angle(sim_t)

    # Screen-space angular error:
    #
    # negative = target is left
    # positive = target is right

    error = world_target - camera_yaw

    # --------------------------------------------------------
    # SENSOR ENCODER
    # --------------------------------------------------------

    inject = []

    if error < -2.0:
        # target is on the LEFT
        inject.append(
            (lc10_left, STIMULUS)
        )

    elif error > 2.0:
        # target is on the RIGHT
        inject.append(
            (lc10_right, STIMULUS)
        )

    # --------------------------------------------------------
    # FULL MALE CNS STEP
    # --------------------------------------------------------

    fired = brain.step(inject=inject)

    fired_set = set(fired)

    l_spikes = len(
        fired_set.intersection(dna_left_set)
    )

    r_spikes = len(
        fired_set.intersection(dna_right_set)
    )

    left_history.append(l_spikes)
    right_history.append(r_spikes)

    # --------------------------------------------------------
    # FIRING RATES
    # --------------------------------------------------------

    window_seconds = (
        len(left_history) * brain.dt
    )

    left_rate = (
        sum(left_history) / window_seconds
        if window_seconds > 0
        else 0
    )

    right_rate = (
        sum(right_history) / window_seconds
        if window_seconds > 0
        else 0
    )

    steering = left_rate - right_rate

    if abs(steering) < STEERING_DEADZONE:
        steering = 0.0

    # --------------------------------------------------------
    # MOTOR DECODER
    # --------------------------------------------------------
    #
    # LEFT DNa02 activity -> camera turns left
    # RIGHT DNa02 activity -> camera turns right
    #
    # Negative yaw = left
    #

    turn_rate = clamp(
        -steering * TURN_GAIN,
        -MAX_TURN_RATE,
        MAX_TURN_RATE
    )

    camera_yaw += (
        turn_rate * brain.dt
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    passive_error = abs(world_target)

    rows.append({
        "step": step,
        "sim_time": sim_t,
        "target_world_deg": world_target,
        "camera_yaw_deg": camera_yaw,
        "tracking_error_deg": error,
        "abs_error_deg": abs(error),
        "passive_abs_error_deg": passive_error,
        "dna02_left_hz": left_rate,
        "dna02_right_hz": right_rate,
        "steering_hz": steering,
        "turn_rate_deg_s": turn_rate,
    })

    # --------------------------------------------------------
    # DRAW
    # --------------------------------------------------------

    screen.fill((15, 17, 22))

    center_x = WIDTH // 2
    center_y = HEIGHT // 2

    # horizon
    pygame.draw.line(
        screen,
        (80, 80, 90),
        (0, center_y),
        (WIDTH, center_y),
        1
    )

    # aim reticle
    pygame.draw.line(
        screen,
        (220, 220, 220),
        (center_x - 15, center_y),
        (center_x + 15, center_y),
        2
    )

    pygame.draw.line(
        screen,
        (220, 220, 220),
        (center_x, center_y - 15),
        (center_x, center_y + 15),
        2
    )

    # target screen coordinate
    visible = abs(error) <= HALF_FOV

    if visible:

        normalized = error / HALF_FOV

        target_x = int(
            center_x
            + normalized * center_x
        )

        pygame.draw.circle(
            screen,
            (240, 80, 80),
            (target_x, center_y - 80),
            18
        )

        pygame.draw.circle(
            screen,
            (255, 150, 150),
            (target_x, center_y - 80),
            28,
            2
        )

    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    title = big_font.render(
        "FlyTank 0.1 — MaleCNS closed loop",
        True,
        (240, 240, 240)
    )

    screen.blit(title, (25, 20))

    lines = [
        f"sim time       : {sim_t:6.2f} s",
        f"target angle   : {world_target:+7.2f} deg",
        f"camera yaw     : {camera_yaw:+7.2f} deg",
        f"tracking error : {error:+7.2f} deg",
        "",
        f"DNa02 LEFT     : {left_rate:6.2f} Hz",
        f"DNa02 RIGHT    : {right_rate:6.2f} Hz",
        f"L-R signal     : {steering:+6.2f} Hz",
        f"turn rate      : {turn_rate:+6.1f} deg/s",
    ]

    y = 75

    for line in lines:

        text = font.render(
            line,
            True,
            (210, 210, 215)
        )

        screen.blit(text, (25, y))

        y += 25

    # directional indicator

    if error < -2:
        sensor_text = "LC10a LEFT stimulus"

    elif error > 2:
        sensor_text = "LC10a RIGHT stimulus"

    else:
        sensor_text = "TARGET CENTERED"

    text = font.render(
        sensor_text,
        True,
        (150, 220, 160)
    )

    screen.blit(
        text,
        (WIDTH - 300, 25)
    )

    pygame.display.flip()

    # Do NOT force real-time speed.
    # Brain computes as fast as CPU allows.
    clock.tick(1000)

    sim_t += brain.dt
    step += 1


# ============================================================
# FINISH
# ============================================================

pygame.quit()

wall_time = time.perf_counter() - wall_start

csv_path = (
    RESULTS
    / "experiment_002_tracking.csv"
)

with open(csv_path, "w", newline="") as f:

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

passive_error = sum(
    r["passive_abs_error_deg"]
    for r in rows
) / len(rows)

improvement = (
    (passive_error - mean_error)
    / passive_error
    * 100
)

print()
print("==============================")
print("EXPERIMENT 002 COMPLETE")
print("==============================")

print(
    f"Simulated time : {sim_t:.2f} s"
)

print(
    f"Wall time      : {wall_time:.2f} s"
)

print(
    f"Mean error     : {mean_error:.2f} deg"
)

print(
    f"Passive error  : {passive_error:.2f} deg"
)

print(
    f"Improvement    : {improvement:+.1f}%"
)

print()
print(
    f"Saved to {csv_path}"
)
