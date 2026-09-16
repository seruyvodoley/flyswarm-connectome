from flybrain import FlyBrain
import time

print("=== FlyTank Brain Smoke Test ===")

print("Loading MaleCNS...")
t0 = time.perf_counter()

brain = FlyBrain(device="cpu")

load_time = time.perf_counter() - t0

print(f"Brain loaded in {load_time:.2f} s")
print(f"dt = {brain.dt}")

# Зрительные нейроны левого глаза:
# LC4 и LPLC2 реагируют на looming-стимулы
left_loom = brain.cells(["LC4", "LPLC2"], side="L")

# DNp01 — descending neuron / giant fiber,
# связанный с escape response
giant_fiber_left = brain.cells(["DNp01"], side="L")

print(f"Left LC4/LPLC2 neurons: {len(left_loom)}")
print(f"Left DNp01 neurons: {len(giant_fiber_left)}")

giant_set = set(giant_fiber_left)

print("\nInjecting left-eye looming stimulus...")

fired_giant = []

t0 = time.perf_counter()

for step in range(50):
    fired = brain.step(
        inject=[(left_loom, 0.8)]
    )

    if giant_set.intersection(fired):
        t = step * brain.dt
        fired_giant.append(t)
        print(
            f"DNp01 fired: "
            f"step={step}, "
            f"simulation_time={t:.3f}s"
        )

run_time = time.perf_counter() - t0

print("\n=== RESULTS ===")
print(f"50 brain steps: {run_time:.3f} real seconds")
print(f"Average per step: {(run_time / 50) * 1000:.2f} ms")

if fired_giant:
    print(f"SUCCESS: DNp01 fired {len(fired_giant)} time(s)")
    print(f"First response at {fired_giant[0]:.3f} simulated seconds")
else:
    print("NO DNp01 RESPONSE")
    print("The brain ran, but this stimulus did not trigger DNp01.")

print("\nSmoke test finished.")
