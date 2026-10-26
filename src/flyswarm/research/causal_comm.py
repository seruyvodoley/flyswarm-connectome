"""Directed-message interventions for open-loop causal MaleCNS studies.

This module deliberately does not claim to restore Godot physics.  An event
affects one directed sender -> receiver input BEFORE the receiver's global
JO-A/JO-B cap; other inputs are renormalized if the cap changes.

Indices are global 0..15, ticks are one-based 20-ms neural ticks.  The
non-intervened computation is numerically equivalent to sensory.audio_frame.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import numpy as np

KINDS = frozenset({"mute", "replace", "time_shift", "shuffle_sender"})


@dataclass(frozen=True)
class DirectedEvent:
    tick: int
    sender: int
    receiver: int
    kind: str
    value: float | None = None
    lag_steps: int = 0
    substitute_sender: int | None = None

    @classmethod
    def parse(cls, data: Mapping) -> "DirectedEvent":
        if not isinstance(data, Mapping):
            raise ValueError("intervention event must be an object")
        keys = set(data)
        allowed = {"tick", "sender", "receiver", "kind", "value", "lag_steps", "substitute_sender"}
        if keys - allowed:
            raise ValueError(f"unknown directed event fields: {sorted(keys - allowed)}")
        event = cls(
            tick=int(data["tick"]), sender=int(data["sender"]),
            receiver=int(data["receiver"]), kind=str(data["kind"]),
            value=None if data.get("value") is None else float(data["value"]),
            lag_steps=int(data.get("lag_steps", 0)),
            substitute_sender=None if data.get("substitute_sender") is None
            else int(data["substitute_sender"]),
        )
        if event.tick <= 0 or not (0 <= event.sender < 16) or not (0 <= event.receiver < 16):
            raise ValueError("tick must be positive and agent IDs must be 0..15")
        if event.sender == event.receiver:
            raise ValueError("a sender cannot send to itself")
        if event.kind not in KINDS:
            raise ValueError(f"unknown intervention kind {event.kind!r}")
        if event.kind == "replace":
            if event.value is None or not np.isfinite(event.value) or event.value < 0:
                raise ValueError("replace requires a finite nonnegative value")
        elif event.value is not None:
            raise ValueError("value is only allowed for replace")
        if event.kind == "time_shift":
            if event.lag_steps <= 0:
                raise ValueError("time_shift requires a positive lag_steps")
        elif event.lag_steps:
            raise ValueError("lag_steps is only allowed for time_shift")
        if event.kind == "shuffle_sender":
            other = event.substitute_sender
            if other is None or not 0 <= other < 16 or other == event.sender:
                raise ValueError("shuffle_sender requires another valid agent")
            if other // 8 != event.sender // 8:
                raise ValueError("shuffle_sender must use the same team")
        elif event.substitute_sender is not None:
            raise ValueError("substitute_sender is only allowed for shuffle_sender")
        return event


class CausalCommunication:
    """Apply a prespecified directed event to the real FlySwarm audio channel."""

    def __init__(self, specification: Mapping | None = None):
        specification = specification or {}
        if not isinstance(specification, Mapping) or set(specification) - {"events", "enabled_teams"}:
            raise ValueError("causal specification permits only events and enabled_teams")
        self.events = [DirectedEvent.parse(x) for x in specification.get("events", [])]
        keys = [(x.tick, x.sender, x.receiver) for x in self.events]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate interventions on one directed link at the same tick")
        teams = specification.get("enabled_teams", [True, True])
        if not isinstance(teams, list) or len(teams) != 2 or any(not isinstance(t, bool) for t in teams):
            raise ValueError("enabled_teams must be an array of two booleans")
        self.enabled_teams = tuple(teams)
        self.by_tick = {}
        for e in self.events:
            self.by_tick.setdefault(e.tick, []).append(e)
        self.reset()

    def reset(self):
        self.history: list[np.ndarray] = []
        self.next_tick = 1

    def step(self, song, positions, alive, mode: str, tick: int):
        from flyswarm.sensory import MODES
        if mode not in MODES:
            raise ValueError(f"unknown audio mode: {mode}")
        if tick != self.next_tick:
            raise ValueError(f"neural step sequence gap: expected {self.next_tick}, got {tick}")
        signal = np.asarray(song, dtype=float)
        coords = np.asarray(positions, dtype=float)
        living = np.asarray(alive, dtype=bool)
        if signal.shape != (16,) or coords.shape != (16, 3) or living.shape != (16,):
            raise ValueError("expected 16 signals, 16 positions, 16 alive flags")
        if not np.isfinite(signal).all() or (signal < 0).any() or not np.isfinite(coords).all():
            raise ValueError("nonfinite/negative signals or nonfinite coordinates")

        distance = np.linalg.norm(coords[:, None] - coords[None, :], axis=-1)
        mask = ~np.eye(16, dtype=bool)
        mask &= living[:, None] & living[None, :]
        if mode == "no_audio":
            mask[:] = False
        elif mode == "team_audio":
            index = np.arange(16) // 8
            mask &= index[:, None] == index[None, :]
        for receiver in range(16):
            if not self.enabled_teams[receiver // 8]:
                mask[receiver, :] = False

        sender_signal = np.broadcast_to(signal, (16, 16)).copy()
        original_raw = mask * sender_signal * .08 / (1 + (distance / 250) ** 2)
        current_raw = original_raw.copy()
        interventions = []
        for event in self.by_tick.get(tick, []):
            r, s = event.receiver, event.sender
            if not mask[r, s]:
                # Intervention on a non-existent link is an error, not silent success.
                raise ValueError(f"inactive directed link {s}->{r} at tick {tick}")
            if event.kind == "mute":
                changed_signal = 0.0
            elif event.kind == "replace":
                changed_signal = float(event.value)
            elif event.kind == "time_shift":
                earlier = tick - 1 - event.lag_steps
                if earlier < 0:
                    raise ValueError(f"no sender history for lag {event.lag_steps} at tick {tick}")
                changed_signal = float(self.history[earlier][s])
            else:
                changed_signal = float(signal[event.substitute_sender])
            current_raw[r, s] = changed_signal * .08 / (1 + (distance[r, s] / 250) ** 2)
            interventions.append({
                "tick": tick, "sender": s, "receiver": r,
                "kind": event.kind, "original_signal": float(signal[s]),
                "effective_signal": changed_signal,
            })

        def cap(raw):
            totals = raw.sum(axis=1)
            scale = np.ones(16, dtype=float)
            saturated = totals > .8
            scale[saturated] = .8 / totals[saturated]
            return raw * scale[:, None], scale

        baseline, baseline_scale = cap(original_raw)
        delivered, scale = cap(current_raw)
        heard = delivered.sum(axis=1)
        links = []
        for r, s in np.argwhere(mask):
            links.append({
                "sender": int(s), "receiver": int(r),
                "source_amplitude": float(signal[s]),
                "distance_m": float(distance[r, s]),
                "raw_contribution": float(original_raw[r, s]),
                "baseline_delivered": float(baseline[r, s]),
                "effective_delivered": float(delivered[r, s]),
                "baseline_cap_scale": float(baseline_scale[r]),
                "cap_scale": float(scale[r]),
            })
        self.history.append(signal.copy())
        self.next_tick += 1
        record = {
            "tick": tick, "mode": mode, "enabled_teams": list(self.enabled_teams),
            "baseline_heard": baseline.sum(axis=1).astype(float).tolist(),
            "heard": heard.astype(float).tolist(), "links": links,
            "interventions": interventions,
            "saturation_receivers": np.nonzero(scale < 1)[0].astype(int).tolist(),
        }
        return heard, delivered, distance, record
