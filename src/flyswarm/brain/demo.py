"""Single-agent MaleCNS runtime for the visitor-vs-fly Open Day battle."""
import time

import numpy as np

from flyswarm.sensory import audio_frame, visual
from flyswarm.brain import WING


class DemoBrain:
    """One real batch=1 FlyBrain for red agent 8; inactive slots stay zero."""

    def __init__(self, seed=204, status=None):
        from flybrain import FlyBrain
        from flybrain.data import has_data

        if not has_data():
            raise RuntimeError("MaleCNS dataset missing; configure flybrain data separately")
        if status:
            status("Loading MaleCNS · FlyBrain(batch=1)")
        self.brain = FlyBrain(device="cpu", batch=1, seed=seed)
        self.brains = [self.brain]
        self.seed = seed
        self.groups = self._make_groups(self.brain)
        if status:
            status("Warming up one MaleCNS opponent")
        self.reset(seed)

    @staticmethod
    def _make_groups(brain):
        groups = {}
        for label, cell in [("lc9", "LC9"), ("lc10", "LC10a")]:
            for side in ["L", "R"]:
                groups[label + "_" + side.lower()] = brain.cells([cell], side=side)
        groups["loom"] = brain.cells(["LC4", "LPLC2"])
        groups["ear"] = brain.cells(
            sorted({str(cell) for cell in brain.cell_type if str(cell).startswith(("JO-A", "JO-B"))})
        )
        groups["wing"] = brain.cells(WING)
        groups["outputs"] = [
            brain.cells(["DNp09"], side="L"),
            brain.cells(["DNp09"], side="R"),
            brain.cells(["DNa02"], side="L"),
            brain.cells(["DNa02"], side="R"),
            brain.cells(["DNp01"]),
            groups["wing"],
        ]
        assert len(groups["wing"]) and len(groups["ear"])
        return groups

    def reset(self, seed):
        self.seed = seed
        self.brain.reset(seed)
        for _ in range(25):
            self.brain.step()
        self.song = np.zeros(16)
        self.trace = np.zeros(6)
        self.ticks = 0
        self.last_communication = {
            "sample": -1,
            "song_out": [0.0] * 16,
            "heard_total": [0.0] * 16,
            "events": [],
            "delay_steps": 1,
        }

    def step(self, observations, audio_mode):
        start = time.perf_counter()
        alive = np.asarray([observation["alive"] for observation in observations], dtype=bool)
        positions = [observation["position"] for observation in observations]
        previous_song = self.song.copy()
        heard, contribution, distance = audio_frame(previous_song, positions, alive, audio_mode)
        opponent = observations[8]
        stimulus = visual([opponent])
        group = self.groups
        inject = [(group[key], value) for key, value in stimulus.items()]
        inject.append((group["ear"], heard[8:9]))
        fired = self.brain.step(inject=inject)
        counts = np.asarray(
            [np.count_nonzero(np.isin(fired[0], ids)) for ids in group["outputs"]],
            dtype=float,
        )
        self.trace = 0.9 * self.trace + 0.1 * counts / self.brain.dt
        self.song[:] = 0
        self.song[8] = counts[-1] if alive[8] else 0
        self.ticks += 1
        if self.ticks % 10 == 0:
            events = []
            receivers, senders = np.nonzero(contribution >= 0.01)
            for receiver, sender in zip(receivers.tolist(), senders.tolist()):
                events.append({
                    "sender": int(sender),
                    "receiver": int(receiver),
                    "raw": float(previous_song[sender]),
                    "received": float(contribution[receiver, sender]),
                    "distance_m": float(distance[receiver, sender]),
                })
            events.sort(key=lambda event: event["received"], reverse=True)
            self.last_communication = {
                "sample": int(self.ticks // 10),
                "song_out": previous_song.astype(float).tolist(),
                "heard_total": heard.astype(float).tolist(),
                "events": events[:12],
                "delay_steps": 1,
            }
        traces = np.zeros((16, 6))
        traces[8] = self.trace
        return traces, heard, (time.perf_counter() - start) * 1000

    @staticmethod
    def baseline(trace):
        p9l, p9r, a02l, a02r, escape, _wing = trace
        throttle = np.clip(max(0.0, float(p9l + p9r) - 2.0) / 10.0, 0.0, 1.0)
        steer = np.clip(float(p9r - p9l) / 6.0, -1.0, 1.0)
        turret = np.clip(float(a02r - a02l) / 8.0, -1.0, 1.0)
        throttle *= 1.0 - np.clip(float(escape) / 80.0, 0.0, 0.70)
        return np.array([throttle, 0.0, steer, turret, 0.0, 0.0], dtype=float)
