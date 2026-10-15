# Objective capture — Domination

Krasny Valley uses a three-zone Domination objective model inspired by the
visible behaviour of classic War Thunder ground Domination.

## Control

Each objective has a signed control value:

- `+1.0` — BLUE owns the objective
- `0.0` — neutral
- `-1.0` — RED owns the objective

A fully enemy-owned zone must first be neutralized and then captured.

With the default `capture_seconds = 12`:

- neutral → owned: approximately 12 simulation seconds with one vehicle
- fully enemy-owned → fully friendly-owned: approximately 24 seconds with one
  uninterrupted vehicle

Enemy presence inside the zone makes it contested and freezes capture progress.

## Multiple vehicles

Additional friendly vehicles accelerate capture with configurable diminishing
returns:

- one vehicle: ×1.00
- two: ×1.35
- three: ×1.70
- four or more: capped by `capture_multi_cap` (default ×2.00)

This scaling is a FlySwarm simulation parameter, not a claim about Gaijin's
undocumented internal formula.

## Tickets

Domination bleed is based on the difference in owned zones:

- 0–0 / 1–1: no objective ticket bleed
- 1–0 / 2–1: trailing team loses 1 × base bleed
- 2–0 / 3–1: trailing team loses 2 × base bleed
- 3–0: trailing team loses 3 × base bleed

Only the trailing team loses objective tickets.

Vehicle destruction remains an independent ticket loss.

## Controller separation

Rule AI may explicitly select an objective as part of its conventional baseline.

MaleCNS receives no objective coordinates, role labels or hidden waypoint command
from this change. Objective perception for the biological controller is a separate
research problem.

## Replay

Replay snapshots store:

- owner
- signed progress
- contested state
- BLUE/RED occupancy counts

so objective state can be reconstructed without running MaleCNS.
