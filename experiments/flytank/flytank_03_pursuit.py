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

WIDTH = 1200
HEIGHT = 800

SIM_DURATION = 25.0
SEED = 64

STIMULUS = 0.8

RATE_WINDOW = 10     # 200 ms at dt=20 ms
WARMUP_STEPS = 25

# Visual fields
BODY_FOV = 150.0
TURRET_FOV = 120.0

BODY_DEADZONE = 4.0
TURRET_DEADZONE = 1.5

# DNp09 -> chassis
FORWARD_DEADZONE_HZ = 2.0
SPEED_GAIN = 1.8
MAX_SPEED = 32.0

BODY_TURN_GAIN = 5.0
MAX_BODY_TURN = 60.0

# DNa02 -> turret
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
    """
    0 degrees = +Y / forward
    +90 = right
    -90 = left
    """
    return math.degrees(
        math.atan2(dx, dy)
    )


def target_position(t):
    """
    Independently moving target.

    It gradually moves forward while weaving.
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

# Pursuit visual pathway
lc9_left = brain.cells(
    ["LC9"],
    side="L"
)

lc9_right = brain.cells(
    ["LC9"],
    side="R"
)

# Turret tracking pathway
lc10_left = brain.cells(
    ["LC10a"],
    side="L"
)

lc10_right = brain.cells(
    ["LC10a"],
    side="R"
)

# Chassis outputs
dnp09_left = brain.cells(
    ["DNp09"],
    side="L"
)

dnp09_right = brain.cells(
    ["DNp09"],
    side="R"
)

# Turret outputs
dna02_left = brain.cells(
    ["DNa02"],
    side="L"
)

dna02_right = brain.cells(
    ["DNa02"],
    side="R"
)

print(
    f"LC9 L/R    : "
    f"{len(lc9_left)} / {len(lc9_right)}"
)

print(
    f"DNp09 L/R  : "
    f"{len(dnp09_left)} / {len(dnp09_right)}"
)

print(
    f"LC10a L/R  : "
    f"{len(lc10_left)} / {len(lc10_right)}"
)

print(
    f"DNa02 L/R  : "
    f"{len(dna02_left)} / {len(dna02_right)}"
)


dnp09_left_set = set(dnp09_left)
dnp09_right_set = set(dnp09_right)

dna02_left_set = set(dna02_left)
dna02_right_set = set(dna02_right)


print("Warming up...")

for _ in range(WARMUP_STEPS):
    brain.step()


# ============================================================
# RATE HISTORIES
# ============================================================

p9_l_history = deque(
    [0] * RATE_WINDOW,
    maxlen=RATE_WINDOW
)

p9_r_history = deque(
    [0] * RATE_WINDOW,
    maxlen=RATE_WINDOW
)

a02_l_history = deque(
    [0] * RATE_WINDOW,
    maxlen=RATE_WINDOW
)

a02_r_history = deque(
    [0] * RATE_WINDOW,
    maxlen=RATE_WINDOW
)


def firing_rate(history):
    return (
        sum(history)
        /
        (len(history) * brain.dt)
    )


# ============================================================
# WORLD STATE
# ============================================================

tank_x = 0.0
tank_y = 0.0

body_yaw = 0.0

# turret angle relative to chassis
turret_relative_yaw = 0.0


# ============================================================
# PYGAME
# ============================================================

pygame.init()

screen = pygame.display.set_mode(
    (WIDTH, HEIGHT)
)

pygame.display.set_caption(
    "FlyTank 0.3 — MaleCNS pursuit"
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
# LOGGING
# ============================================================

rows = []

sim_t = 0.0
step = 0

running = True

wall_start = time.perf_counter()

start_distance = None


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

    # --------------------------------------------------------
    # TARGET
    # --------------------------------------------------------

    target_x, target_y = (
        target_position(sim_t)
    )

    dx = target_x - tank_x
    dy = target_y - tank_y

    distance = math.hypot(
        dx,
        dy
    )

    if start_distance is None:
        start_distance = distance

    target_world_bearing = bearing(
        dx,
        dy
    )

    # --------------------------------------------------------
    # BODY-RELATIVE TARGET BEARING
    # --------------------------------------------------------

    body_error = wrap_angle(
        target_world_bearing
        - body_yaw
    )

    body_visible = (
        abs(body_error)
        <= BODY_FOV / 2
    )

    # --------------------------------------------------------
    # TURRET-RELATIVE TARGET BEARING
    # --------------------------------------------------------

    turret_world_yaw = wrap_angle(
        body_yaw
        + turret_relative_yaw
    )

    turret_error = wrap_angle(
        target_world_bearing
        - turret_world_yaw
    )

    turret_visible = (
        abs(turret_error)
        <= TURRET_FOV / 2
    )

    # ========================================================
    # SENSORY ENCODER
    # ========================================================

    inject = []

    # --------------------------------------------------------
    # LC9 — PURSUIT / OBJECT-DIRECTED WALKING
    # --------------------------------------------------------

    if body_visible:

        if body_error < -BODY_DEADZONE:

            inject.append(
                (lc9_left, STIMULUS)
            )

        elif body_error > BODY_DEADZONE:

            inject.append(
                (lc9_right, STIMULUS)
            )

        else:

            # Object is approximately ahead.
            #
            # Bilateral LC9 activates bilateral DNp09,
            # which gives us straight forward pursuit.
            inject.append(
                (lc9_left, STIMULUS)
            )

            inject.append(
                (lc9_right, STIMULUS)
            )

    # --------------------------------------------------------
    # LC10a — TURRET TARGET TRACKING
    # --------------------------------------------------------

    if turret_visible:

        if turret_error < -TURRET_DEADZONE:

            inject.append(
                (lc10_left, STIMULUS)
            )

        elif turret_error > TURRET_DEADZONE:

            inject.append(
                (lc10_right, STIMULUS)
            )

    # ========================================================
    # FULL 166,700-NEURON CNS
    # ========================================================

    fired = set(
        brain.step(
            inject=inject
        )
    )

    # --------------------------------------------------------
    # READ MOTOR NEURONS
    # --------------------------------------------------------

    p9_l = len(
        fired.intersection(
            dnp09_left_set
        )
    )

    p9_r = len(
        fired.intersection(
            dnp09_right_set
        )
    )

    a02_l = len(
        fired.intersection(
            dna02_left_set
        )
    )

    a02_r = len(
        fired.intersection(
            dna02_right_set
        )
    )


    p9_l_history.append(p9_l)
    p9_r_history.append(p9_r)

    a02_l_history.append(a02_l)
    a02_r_history.append(a02_r)


    p9_l_rate = firing_rate(
        p9_l_history
    )

    p9_r_rate = firing_rate(
        p9_r_history
    )

    a02_l_rate = firing_rate(
        a02_l_history
    )

    a02_r_rate = firing_rate(
        a02_r_history
    )


    # ========================================================
    # CHASSIS MOTOR DECODER
    # ========================================================

    pursuit_drive = (
        p9_l_rate
        + p9_r_rate
    )

    forward_signal = max(
        0.0,
        pursuit_drive
        - FORWARD_DEADZONE_HZ
    )

    speed = clamp(
        forward_signal
        * SPEED_GAIN,
        0.0,
        MAX_SPEED
    )


    # DNp09 ipsilateral turning:
    #
    # more LEFT activity -> turn left
    # more RIGHT activity -> turn right

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


    # Move along chassis heading

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


    # ========================================================
    # TURRET MOTOR DECODER
    # ========================================================

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


    # --------------------------------------------------------
    # POST-ACTION ERRORS
    # --------------------------------------------------------

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

        "body_yaw_deg":
            body_yaw,

        "turret_relative_deg":
            turret_relative_yaw,

        "target_bearing_deg":
            post_bearing,

        "body_error_deg":
            post_body_error,

        "turret_error_deg":
            post_turret_error,

        "body_visible":
            int(body_visible),

        "turret_visible":
            int(turret_visible),

        "DNp09_L_hz":
            p9_l_rate,

        "DNp09_R_hz":
            p9_r_rate,

        "DNa02_L_hz":
            a02_l_rate,

        "DNa02_R_hz":
            a02_r_rate,

        "speed":
            speed,

        "body_turn_rate":
            body_turn_rate,

        "turret_turn_rate":
            turret_turn_rate,
    })


    # ========================================================
    # DRAW
    # ========================================================

    screen.fill(
        (20, 24, 27)
    )


    # Camera follows tank

    tank_screen_x = WIDTH // 2
    tank_screen_y = int(
        HEIGHT * 0.68
    )

    SCALE = 1.1


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


    # --------------------------------------------------------
    # TARGET RELATIVE POSITION
    # --------------------------------------------------------

    rel_x = (
        target_x - tank_x
    )

    rel_y = (
        target_y - tank_y
    )

    target_screen_x = int(
        tank_screen_x
        + rel_x * SCALE
    )

    target_screen_y = int(
        tank_screen_y
        - rel_y * SCALE
    )


    # target

    pygame.draw.rect(
        screen,
        (195, 65, 65),
        (
            target_screen_x - 18,
            target_screen_y - 12,
            36,
            24
        )
    )

    pygame.draw.circle(
        screen,
        (240, 100, 100),
        (
            target_screen_x,
            target_screen_y
        ),
        28,
        2
    )


    # --------------------------------------------------------
    # BODY
    # --------------------------------------------------------

    body_surface = pygame.Surface(
        (80, 105),
        pygame.SRCALPHA
    )

    pygame.draw.rect(
        body_surface,
        (85, 115, 90),
        (10, 10, 60, 85)
    )

    pygame.draw.rect(
        body_surface,
        (150, 165, 145),
        (10, 10, 60, 85),
        2
    )

    rotated_body = pygame.transform.rotate(
        body_surface,
        -body_yaw
    )

    body_rect = rotated_body.get_rect(
        center=(
            tank_screen_x,
            tank_screen_y
        )
    )

    screen.blit(
        rotated_body,
        body_rect
    )


    # --------------------------------------------------------
    # TURRET
    # --------------------------------------------------------

    pygame.draw.circle(
        screen,
        (125, 150, 120),
        (
            tank_screen_x,
            tank_screen_y
        ),
        22
    )

    turret_world_angle = wrap_angle(
        body_yaw
        + turret_relative_yaw
    )

    turret_rad = math.radians(
        turret_world_angle
    )

    barrel_length = 90

    barrel_x = int(
        tank_screen_x
        + math.sin(turret_rad)
        * barrel_length
    )

    barrel_y = int(
        tank_screen_y
        - math.cos(turret_rad)
        * barrel_length
    )

    pygame.draw.line(
        screen,
        (215, 220, 195),
        (
            tank_screen_x,
            tank_screen_y
        ),
        (
            barrel_x,
            barrel_y
        ),
        7
    )


    # --------------------------------------------------------
    # BODY HEADING INDICATOR
    # --------------------------------------------------------

    heading_length = 65

    hx = int(
        tank_screen_x
        + math.sin(body_rad)
        * heading_length
    )

    hy = int(
        tank_screen_y
        - math.cos(body_rad)
        * heading_length
    )

    pygame.draw.line(
        screen,
        (100, 180, 255),
        (
            tank_screen_x,
            tank_screen_y
        ),
        (hx, hy),
        2
    )


    # --------------------------------------------------------
    # TARGET LINE
    # --------------------------------------------------------

    if (
        0 <= target_screen_x < WIDTH
        and
        0 <= target_screen_y < HEIGHT
    ):

        pygame.draw.line(
            screen,
            (65, 75, 70),
            (
                tank_screen_x,
                tank_screen_y
            ),
            (
                target_screen_x,
                target_screen_y
            ),
            1
        )


    # ========================================================
    # HUD
    # ========================================================

    title = big_font.render(
        "FlyTank 0.3 — MaleCNS pursuit",
        True,
        (235, 235, 235)
    )

    screen.blit(
        title,
        (20, 18)
    )


    hud = [
        f"simulation       {sim_t:6.2f} s",
        "",
        f"distance         {post_distance:7.1f}",
        f"speed            {speed:7.1f}",
        "",
        f"body error       {post_body_error:+7.2f} deg",
        f"turret error     {post_turret_error:+7.2f} deg",
        "",
        f"DNp09 L          {p9_l_rate:6.2f} Hz",
        f"DNp09 R          {p9_r_rate:6.2f} Hz",
        f"body turn        {body_turn_rate:+6.1f} deg/s",
        "",
        f"DNa02 L          {a02_l_rate:6.2f} Hz",
        f"DNa02 R          {a02_r_rate:6.2f} Hz",
        f"turret turn      {turret_turn_rate:+6.1f} deg/s",
    ]


    y = 65

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

        y += 23


    status = []

    if body_visible:
        status.append("LC9 TARGET")
    else:
        status.append("LC9 LOST")

    if turret_visible:
        status.append("LC10a TARGET")
    else:
        status.append("LC10a LOST")


    status_text = font.render(
        " | ".join(status),
        True,
        (
            130,
            230,
            150
        )
    )

    screen.blit(
        status_text,
        (
            WIDTH - 330,
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


# ============================================================
# SAVE DATA
# ============================================================

csv_path = (
    RESULTS
    / "flytank_03_pursuit.csv"
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

mean_body_error = sum(
    abs(r["body_error_deg"])
    for r in rows
) / len(rows)


mean_turret_error = sum(
    abs(r["turret_error_deg"])
    for r in rows
) / len(rows)


within_body_10 = (
    sum(
        abs(r["body_error_deg"])
        <= 10
        for r in rows
    )
    / len(rows)
    * 100
)


within_turret_5 = (
    sum(
        abs(r["turret_error_deg"])
        <= 5
        for r in rows
    )
    / len(rows)
    * 100
)


body_visible_pct = (
    sum(
        r["body_visible"]
        for r in rows
    )
    / len(rows)
    * 100
)


turret_visible_pct = (
    sum(
        r["turret_visible"]
        for r in rows
    )
    / len(rows)
    * 100
)


mean_speed = sum(
    r["speed"]
    for r in rows
) / len(rows)


final_distance = rows[-1][
    "distance"
]

minimum_distance = min(
    r["distance"]
    for r in rows
)


print()
print(
    "========================================"
)

print(
    "FLYTANK 0.3 — PURSUIT RESULTS"
)

print(
    "========================================"
)

print(
    f"Simulated time      : {sim_t:.2f} s"
)

print(
    f"Wall time           : {wall_time:.2f} s"
)

print()

print(
    f"Start distance      : {start_distance:.1f}"
)

print(
    f"Final distance      : {final_distance:.1f}"
)

print(
    f"Minimum distance    : {minimum_distance:.1f}"
)

print(
    f"Mean speed          : {mean_speed:.2f}"
)

print()

print(
    f"Mean body error     : {mean_body_error:.2f} deg"
)

print(
    f"Body within +/-10   : {within_body_10:.1f}%"
)

print(
    f"Body target visible : {body_visible_pct:.1f}%"
)

print()

print(
    f"Mean turret error   : {mean_turret_error:.2f} deg"
)

print(
    f"Turret within +/-5  : {within_turret_5:.1f}%"
)

print(
    f"Turret visible      : {turret_visible_pct:.1f}%"
)

print()

print(
    f"Saved to {csv_path}"
)
