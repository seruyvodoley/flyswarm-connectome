from flybrain import FlyBrain
from collections import deque
from statistics import mean, stdev
from pathlib import Path
import math
import csv


# ============================================================
# CONFIG
# ============================================================

SEEDS = [64, 65, 66, 67, 68]

CONDITIONS = [
    "full",
    "chase_only",
    "escape_output_ablated",
]

SIM_DURATION = 40.0

CHASE_STIMULUS = 0.8

RATE_WINDOW = 10
LOOM_WINDOW = 5

WARMUP_STEPS = 25
BASELINE_STEPS = 100

BODY_FOV = 150.0
TURRET_FOV = 120.0

BODY_DEADZONE = 4.0
TURRET_DEADZONE = 1.5

TARGET_VISUAL_RADIUS = 20.0

LOOM_GAIN = 0.12
LOOM_MIN_INPUT = 0.05
LOOM_MAX_INPUT = 1.0

P9_DEADZONE = 2.0

FORWARD_GAIN = 1.8
MAX_FORWARD_SPEED = 32.0

BODY_TURN_GAIN = 5.0
MAX_BODY_TURN = 60.0

REVERSE_GAIN = 1.65
MAX_REVERSE_SPEED = 28.0

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

    return math.degrees(
        2.0 * math.atan2(
            TARGET_VISUAL_RADIUS,
            max(distance, 0.001)
        )
    )


def target_position(t):

    x = (
        120.0 * math.sin(0.22 * t)
        + 35.0 * math.sin(
            0.55 * t + 0.8
        )
    )

    y = (
        300.0
        + 14.0 * t
        + 25.0 * math.sin(
            0.18 * t + 0.5
        )
    )

    return x, y


# ============================================================
# ONE RUN
# ============================================================

def run(seed, condition):

    brain = FlyBrain(
        device="cpu",
        seed=seed
    )

    # ---------------- sensory ----------------

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

    lc4_l = brain.cells(
        ["LC4"],
        side="L"
    )

    lc4_r = brain.cells(
        ["LC4"],
        side="R"
    )

    lplc2_l = brain.cells(
        ["LPLC2"],
        side="L"
    )

    lplc2_r = brain.cells(
        ["LPLC2"],
        side="R"
    )

    # ---------------- outputs ----------------

    populations = {
        "p9_l":
            brain.cells(
                ["DNp09"],
                side="L"
            ),

        "p9_r":
            brain.cells(
                ["DNp09"],
                side="R"
            ),

        "a02_l":
            brain.cells(
                ["DNa02"],
                side="L"
            ),

        "a02_r":
            brain.cells(
                ["DNa02"],
                side="R"
            ),

        "p01":
            brain.cells(["DNp01"]),

        "p02":
            brain.cells(["DNp02"]),

        "p04":
            brain.cells(["DNp04"]),
    }

    sets = {
        key: set(value)
        for key, value
        in populations.items()
    }


    # ========================================================
    # WARMUP / BASELINE
    # ========================================================

    for _ in range(
        WARMUP_STEPS
    ):
        brain.step()


    baseline_sequence = []

    for _ in range(
        BASELINE_STEPS
    ):

        baseline_sequence.append(
            set(brain.step())
        )


    def population_rate(
        sequence,
        name
    ):

        cells = sets[name]

        spikes = sum(
            len(fired.intersection(cells))
            for fired in sequence
        )

        return (
            spikes
            / len(cells)
            / (
                len(sequence)
                * brain.dt
            )
        )


    baselines = {

        name:
            population_rate(
                baseline_sequence,
                name
            )

        for name in sets
    }


    # ========================================================
    # HISTORIES
    # ========================================================

    histories = {}

    for name in sets:

        history = deque(
            maxlen=RATE_WINDOW
        )

        for fired in (
            baseline_sequence[
                -RATE_WINDOW:
            ]
        ):

            history.append(
                len(
                    fired.intersection(
                        sets[name]
                    )
                )
            )

        histories[name] = history


    def rate(name):

        h = histories[name]

        return (
            sum(h)
            / len(sets[name])
            / (
                len(h)
                * brain.dt
            )
        )


    # ========================================================
    # STATE
    # ========================================================

    tank_x = 0.0
    tank_y = 0.0

    body_yaw = 0.0
    turret_relative = 0.0

    tx, ty = target_position(0)

    start_distance = math.hypot(
        tx,
        ty
    )

    previous_size = angular_size(
        start_distance
    )

    loom_history = deque(
        [0.0] * LOOM_WINDOW,
        maxlen=LOOM_WINDOW
    )


    rows = []

    steps = int(
        SIM_DURATION
        / brain.dt
    )


    # ========================================================
    # LOOP
    # ========================================================

    for step in range(steps):

        t = step * brain.dt

        target_x, target_y = (
            target_position(t)
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


        # ----------------------------------------------------
        # BODY / TURRET ERROR
        # ----------------------------------------------------

        body_error = wrap_angle(
            target_bearing
            - body_yaw
        )

        turret_world = wrap_angle(
            body_yaw
            + turret_relative
        )

        turret_error = wrap_angle(
            target_bearing
            - turret_world
        )

        body_visible = (
            abs(body_error)
            <= BODY_FOV / 2
        )

        turret_visible = (
            abs(turret_error)
            <= TURRET_FOV / 2
        )


        # ----------------------------------------------------
        # LOOMING
        # ----------------------------------------------------

        size = angular_size(
            distance
        )

        raw_loom = (
            size
            - previous_size
        ) / brain.dt

        previous_size = size

        loom_history.append(
            raw_loom
        )

        smooth_loom = (
            sum(loom_history)
            / len(loom_history)
        )

        loom_amount = clamp(
            max(
                0.0,
                smooth_loom
            )
            * LOOM_GAIN,
            0.0,
            LOOM_MAX_INPUT
        )

        if (
            loom_amount
            < LOOM_MIN_INPUT
        ):
            loom_amount = 0.0


        # ====================================================
        # SENSORY INPUT
        # ====================================================

        inject = []


        # ---------------- pursuit ----------------

        if body_visible:

            if (
                body_error
                < -BODY_DEADZONE
            ):

                inject.append(
                    (
                        lc9_l,
                        CHASE_STIMULUS
                    )
                )

            elif (
                body_error
                > BODY_DEADZONE
            ):

                inject.append(
                    (
                        lc9_r,
                        CHASE_STIMULUS
                    )
                )

            else:

                inject.extend([
                    (
                        lc9_l,
                        CHASE_STIMULUS
                    ),
                    (
                        lc9_r,
                        CHASE_STIMULUS
                    ),
                ])


        # ---------------- turret ----------------

        if turret_visible:

            if (
                turret_error
                < -TURRET_DEADZONE
            ):

                inject.append(
                    (
                        lc10_l,
                        CHASE_STIMULUS
                    )
                )

            elif (
                turret_error
                > TURRET_DEADZONE
            ):

                inject.append(
                    (
                        lc10_r,
                        CHASE_STIMULUS
                    )
                )


        # ---------------- looming ----------------
        #
        # ONLY chase_only removes the sensory
        # looming pathway.
        #

        if (
            condition != "chase_only"
            and body_visible
            and loom_amount > 0
        ):

            inject.extend([
                (
                    lc4_l,
                    loom_amount
                ),
                (
                    lc4_r,
                    loom_amount
                ),
                (
                    lplc2_l,
                    loom_amount
                ),
                (
                    lplc2_r,
                    loom_amount
                ),
            ])


        # ====================================================
        # BRAIN
        # ====================================================

        fired = set(
            brain.step(
                inject=inject
            )
        )


        for name in histories:

            histories[
                name
            ].append(

                len(
                    fired.intersection(
                        sets[name]
                    )
                )
            )


        p9_l_rate = rate(
            "p9_l"
        )

        p9_r_rate = rate(
            "p9_r"
        )

        a02_l_rate = rate(
            "a02_l"
        )

        a02_r_rate = rate(
            "a02_r"
        )


        p01_delta = max(
            0.0,
            rate("p01")
            - baselines["p01"]
        )

        p02_delta = max(
            0.0,
            rate("p02")
            - baselines["p02"]
        )

        p04_delta = max(
            0.0,
            rate("p04")
            - baselines["p04"]
        )


        # ====================================================
        # CHASE DRIVE
        # ====================================================

        pursuit = max(
            0.0,

            p9_l_rate
            + p9_r_rate
            - P9_DEADZONE
        )

        forward_component = (
            pursuit
            * FORWARD_GAIN
        )


        # ====================================================
        # ESCAPE DRIVE
        # ====================================================

        escape_drive = (
            p02_delta
            + p04_delta
        ) / 2.0


        if (
            condition
            == "escape_output_ablated"
        ):

            reverse_component = 0.0

        elif (
            condition
            == "chase_only"
        ):

            reverse_component = 0.0

        else:

            reverse_component = (
                escape_drive
                * REVERSE_GAIN
            )


        speed = clamp(

            forward_component
            - reverse_component,

            -MAX_REVERSE_SPEED,
            MAX_FORWARD_SPEED
        )


        # ====================================================
        # BODY STEERING
        # ====================================================

        body_turn = clamp(

            (
                p9_r_rate
                - p9_l_rate
            )
            * BODY_TURN_GAIN,

            -MAX_BODY_TURN,
            MAX_BODY_TURN
        )


        body_yaw = wrap_angle(

            body_yaw
            + body_turn
            * brain.dt
        )


        rad = math.radians(
            body_yaw
        )


        tank_x += (
            math.sin(rad)
            * speed
            * brain.dt
        )

        tank_y += (
            math.cos(rad)
            * speed
            * brain.dt
        )


        # ====================================================
        # TURRET
        # ====================================================

        turret_signal = (
            a02_l_rate
            - a02_r_rate
        )

        if (
            abs(turret_signal)
            < 1.0
        ):
            turret_signal = 0.0


        turret_turn = clamp(

            -turret_signal
            * TURRET_GAIN,

            -MAX_TURRET_TURN,
            MAX_TURRET_TURN
        )


        turret_relative = (
            wrap_angle(

                turret_relative
                + turret_turn
                * brain.dt
            )
        )


        # ----------------------------------------------------
        # POST STATE
        # ----------------------------------------------------

        dx2 = (
            target_x
            - tank_x
        )

        dy2 = (
            target_y
            - tank_y
        )

        post_distance = (
            math.hypot(
                dx2,
                dy2
            )
        )


        rows.append({
            "time": t,
            "distance":
                post_distance,

            "loom_input":
                loom_amount,

            "DNp01_delta":
                p01_delta,

            "DNp02_delta":
                p02_delta,

            "DNp04_delta":
                p04_delta,

            "forward":
                forward_component,

            "reverse":
                reverse_component,

            "speed":
                speed,
        })


    # ========================================================
    # METRICS
    # ========================================================

    distances = [
        r["distance"]
        for r in rows
    ]

    last10 = [
        r["distance"]
        for r in rows
        if (
            r["time"]
            >= SIM_DURATION - 10
        )
    ]

    close_150 = (
        sum(
            d < 150
            for d in distances
        )
        / len(distances)
        * 100
    )

    close_100 = (
        sum(
            d < 100
            for d in distances
        )
        / len(distances)
        * 100
    )

    reverse_pct = (
        sum(
            r["speed"] < 0
            for r in rows
        )
        / len(rows)
        * 100
    )


    return {
        "seed":
            seed,

        "condition":
            condition,

        "start_distance":
            start_distance,

        "min_distance":
            min(distances),

        "final_distance":
            distances[-1],

        "mean_last10":
            mean(last10),

        "pct_below_150":
            close_150,

        "pct_below_100":
            close_100,

        "reverse_pct":
            reverse_pct,

        "max_loom_input":
            max(
                r["loom_input"]
                for r in rows
            ),

        "max_DNp01":
            max(
                r["DNp01_delta"]
                for r in rows
            ),

        "max_DNp02":
            max(
                r["DNp02_delta"]
                for r in rows
            ),

        "max_DNp04":
            max(
                r["DNp04_delta"]
                for r in rows
            ),
    }


# ============================================================
# RUN EXPERIMENT
# ============================================================

results = []


for condition in CONDITIONS:

    print()
    print("=" * 70)
    print(condition.upper())
    print("=" * 70)

    for seed in SEEDS:

        result = run(
            seed,
            condition
        )

        results.append(
            result
        )

        print(
            f"seed={seed} | "
            f"min={result['min_distance']:6.1f} | "
            f"final={result['final_distance']:6.1f} | "
            f"last10={result['mean_last10']:6.1f} | "
            f"<150={result['pct_below_150']:5.1f}% | "
            f"<100={result['pct_below_100']:5.1f}%"
        )


# ============================================================
# SAVE
# ============================================================

path = (
    RESULTS
    / "experiment_008_escape_ablation.csv"
)

with open(
    path,
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
print("=" * 100)
print("EXPERIMENT 008 — ESCAPE ABLATION SUMMARY")
print("=" * 100)

print(
    f"{'condition':23} | "
    f"{'min distance':>16} | "
    f"{'last10 distance':>18} | "
    f"{'<150':>9} | "
    f"{'<100':>9} | "
    f"{'reverse':>9}"
)

print("-" * 100)


for condition in CONDITIONS:

    subset = [
        r
        for r in results
        if (
            r["condition"]
            == condition
        )
    ]


    def values(key):

        return [
            r[key]
            for r in subset
        ]


    min_d = values(
        "min_distance"
    )

    last10 = values(
        "mean_last10"
    )

    below150 = values(
        "pct_below_150"
    )

    below100 = values(
        "pct_below_100"
    )

    reverse = values(
        "reverse_pct"
    )


    print(
        f"{condition:23} | "
        f"{mean(min_d):6.1f} ± {stdev(min_d):5.1f} | "
        f"{mean(last10):7.1f} ± {stdev(last10):5.1f} | "
        f"{mean(below150):6.1f}% | "
        f"{mean(below100):6.1f}% | "
        f"{mean(reverse):6.1f}%"
    )


print()
print(
    f"Saved to {path}"
)
