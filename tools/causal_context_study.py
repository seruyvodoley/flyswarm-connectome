#!/usr/bin/env python3
"""Paired open-loop causal study over validated real MaleCNS E4 histories.

Selection uses only pre-intervention baseline channel and recipient state. The
physical observation history is held fixed; this is not closed-loop physics.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from flyswarm.brain import DualBrain

SOURCE_ROOT = ROOT / "research/studies/malecns_communication/experiments/causal-20261028/e4_factorial/extended_pilot_20261028/raw/e4"
OUT = Path(__import__("os").environ.get("FLYSWARM_CAUSAL_OUT", ROOT / "research/studies/malecns_communication/experiments/causal-context-20261029"))
MAX_SCAN_STEPS = 250
HORIZONS = (0, 1, 5, 25, 50)  # 0, 20, 100, 500, 1000 ms at 50 Hz
COMMAND_IMPORTANCE_THRESHOLD = 0.05  # L2 in normalized command vector [-1, 1]


def read_source(path: Path, count: int):
    manifest = json.loads((path.parent / "manifest.json").read_text())
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise ValueError(f"truncated JSONL row in {path}")
            row = json.loads(line)
            rows.append(row)
            if len(rows) == count:
                break
    if len(rows) != count or [int(x["neural_step_id"]) for x in rows] != list(range(1, count + 1)):
        raise ValueError(f"invalid contiguous source history: {path}")
    if manifest.get("backend_condition", manifest.get("condition")) != "MALECNS_REAL" or manifest.get("audio") != "team_audio":
        raise ValueError(f"source is not real team-audio MaleCNS: {path}")
    if not all(bool(x.get("metadata", {}).get("causal_communication_config", {}).get("enabled_teams", [False, False])[i])
               for x in rows[:1] for i in (0, 1)):
        raise ValueError(f"both team channels are not enabled: {path}")
    return manifest, rows


def result_vectors(brain: DualBrain, rows: list[dict], upto: int, spec: dict | None):
    brain.configure_causal_communication(spec or {"events": []})
    brain.reset(int(rows[0]["seed"]))
    traces = np.zeros((upto, 16, 6), dtype=np.float64)
    commands = np.zeros_like(traces)
    heard = np.zeros((upto, 16), dtype=np.float64)
    frames = []
    for ix, row in enumerate(rows[:upto]):
        trace, received, _ = brain.step(row["observations"], "team_audio")
        traces[ix] = trace
        heard[ix] = received
        commands[ix] = np.stack([brain.baseline(t) for t in trace])
        frames.append(brain.last_communication_frame)
    return traces, commands, heard, frames


def baseline_scan(brain: DualBrain, rows: list[dict]):
    brain.configure_causal_communication({"events": []})
    brain.reset(int(rows[0]["seed"]))
    traces = np.zeros((len(rows), 16, 6), dtype=np.float64)
    commands = np.zeros_like(traces)
    heard = np.zeros((len(rows), 16), dtype=np.float64)
    candidates = []
    for ix, row in enumerate(rows):
        tick = ix + 1
        obs = row["observations"]
        before = brain.trace.copy()
        song_before = brain.song.copy()
        trace, received, _ = brain.step(obs, "team_audio")
        traces[ix] = trace
        heard[ix] = received
        commands[ix] = np.stack([brain.baseline(t) for t in trace])
        frame = brain.last_communication_frame
        if tick < 25 or tick > MAX_SCAN_STEPS - max(HORIZONS) or tick % 5 != 0 or frame is None:
            continue
        links = frame["links"]
        raw_sum = {}
        link_by_pair = {}
        for link in links:
            r, s = int(link["receiver"]), int(link["sender"])
            raw_sum[r] = raw_sum.get(r, 0.0) + float(link["raw_contribution"])
            link_by_pair[(r, s)] = link
        # The event is applied inside this tick to the previous-step song,
        # exactly the signal represented by the recorded baseline frame.
        signals = song_before
        for (receiver, sender), link in link_by_pair.items():
            if sender // 8 != receiver // 8 or not obs[sender]["alive"] or not obs[receiver]["alive"]:
                continue
            signal = float(signals[sender])
            contribution = float(link["raw_contribution"])
            if signal <= 0 or contribution <= 0:
                continue
            total = raw_sum[receiver]
            before_cap = min(total, 0.8)
            mute_delta = before_cap - min(max(0.0, total - contribution), 0.8)
            team_start = (sender // 8) * 8
            donors = [j for j in range(team_start, team_start + 8)
                      if j not in (sender, receiver) and obs[j]["alive"] and signals[j] > 0]
            weight = contribution / signal
            donor_options = []
            for j in donors:
                replacement_total = max(0.0, total - contribution + weight * float(signals[j]))
                replacement_heard = min(replacement_total, 0.8)
                replacement_delta = replacement_heard - before_cap
                donor_options.append({"donor": j, "signal": float(signals[j]),
                                      "delivered_delta": float(replacement_delta)})
            candidates.append({
                "tick": tick, "sender": sender, "receiver": receiver,
                "signal": signal, "distance_m": float(link["distance_m"]),
                "raw_contribution": contribution, "baseline_heard": float(frame["baseline_heard"][receiver]),
                "cap_margin": max(0.0, 0.8 - float(frame["baseline_heard"][receiver])),
                "mute_input_delta": float(mute_delta),
                "recipient_pre_trace": before[receiver].astype(float).tolist(),
                "recipient_pre_activity": float(np.linalg.norm(before[receiver])),
                "donor_options": donor_options,
                "seed": int(rows[0]["seed"]),
            })
    return traces, commands, heard, candidates


def choose_events(candidates: list[dict]):
    def matched_active_donors(candidate):
        tolerance=max(0.005,0.20*candidate["mute_input_delta"])
        return [d for d in candidate["donor_options"]
                if abs(d["delivered_delta"])>1e-8
                and abs(abs(d["delivered_delta"])-candidate["mute_input_delta"])<=tolerance]
    usable = [c for c in candidates if c["mute_input_delta"] > 1e-8 and matched_active_donors(c)]
    if len(usable) < 2:
        return []
    pairs = []
    for i, a in enumerate(usable):
        for b in usable[i + 1:]:
            if a["receiver"] == b["receiver"]:
                continue
            delta_gap = abs(a["mute_input_delta"] - b["mute_input_delta"])
            tolerance = max(0.005, 0.20 * max(a["mute_input_delta"], b["mute_input_delta"]))
            if delta_gap > tolerance:
                continue
            state_gap = abs(a["recipient_pre_activity"] - b["recipient_pre_activity"])
            amplitude_gap=abs(float(a["signal"])-float(b["signal"]))
            # Prefer within-seed amplitude diversity, then maximize the
            # pre-treatment neural-state contrast at matched channel effect.
            pairs.append((amplitude_gap,state_gap,-delta_gap,-max(a["tick"],b["tick"]),a,b))
    if pairs:
        _, _, _, _, a, b = max(pairs, key=lambda x: x[:4])
        chosen = (a, b)
    else:
        # Fallback remains prespecified and outcome-blind: maximum and minimum
        # nonzero channel deltas, reported as unmatched-context events.
        ordered = sorted(usable, key=lambda c: (c["mute_input_delta"], c["tick"], c["receiver"], c["sender"]))
        a, b = ordered[0], ordered[-1]
        if (a["tick"], a["sender"], a["receiver"]) == (b["tick"], b["sender"], b["receiver"]):
            return []
        chosen = (a, b)
    for event in chosen:
        # Choose a same-team donor whose substituted signal produces a
        # nonzero delivered-input change as close as possible to the mute
        # effect. A same-amplitude donor is never accepted as a control.
        active = matched_active_donors(event)
        if not active:
            raise RuntimeError(f"no matched active sender-shuffle control for selected event: {event}")
        donor = min(active, key=lambda d: (abs(abs(d["delivered_delta"])-event["mute_input_delta"]),
                                           abs(d["delivered_delta"]), d["donor"]))
        event["donor"] = int(donor["donor"])
        event["donor_signal"] = float(donor["signal"])
        event["control_input_delta_expected"] = float(donor["delivered_delta"])
        event.pop("donor_options", None)
    return sorted(chosen, key=lambda x: (x["tick"], x["receiver"], x["sender"]))


def max_abs(a, b):
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b))))


def run_event(brain, rows, event, kind):
    spec_event = {"tick": int(event["tick"]), "sender": int(event["sender"]),
                  "receiver": int(event["receiver"]), "kind": kind}
    if kind == "shuffle_sender":
        spec_event["substitute_sender"] = int(event["donor"])
    return result_vectors(brain, rows, int(event["tick"]) + max(HORIZONS), {"events": [spec_event]})


def seed_sources():
    paths = sorted(SOURCE_ROOT.glob("e4-blue_on_red_on-s*-swap0-*/neural_steps.jsonl"))
    by_seed = {}
    for path in paths:
        with path.open(encoding="utf-8") as f:
            first = json.loads(f.readline())
        validation_path = path.parent / "validation.json"
        validation = json.loads(validation_path.read_text()) if validation_path.is_file() else {}
        if not validation.get("valid"):
            continue
        seed = int(first["seed"])
        if seed not in by_seed:
            by_seed[seed] = path
    if len(by_seed) < 8:
        raise RuntimeError(f"expected at least 8 all-on independent seed blocks, found {len(by_seed)}")
    return [(seed, by_seed[seed]) for seed in sorted(by_seed)[:8]]


def bootstrap_ci(seed_values, draws=20000, seed=20261029):
    values = np.asarray(seed_values, dtype=float)
    if not len(values):
        return [None, None]
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(draws, len(values)), replace=True).mean(axis=1)
    return [float(np.quantile(samples, .025)), float(np.quantile(samples, .975))]


def save_csv(path: Path, rows: list[dict]):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def make_figures(event_rows: list[dict]):
    figdir = OUT / "figures"
    figdir.mkdir(exist_ok=True)
    # Fig 1: protocol chain, deliberately content-first and not decorative.
    fig, ax = plt.subplots(figsize=(13, 2.6))
    ax.axis("off")
    boxes = [(0.01, "Направленный\nсигнал"), (0.18, "Сумма +\nнасыщение 0,8"),
             (0.35, "MaleCNS\nфиксированный"), (0.52, "DN-выходы +\nдекодер"),
             (0.69, "Backend\nадаптер"), (0.85, "Godot objective-\ncontroller → команда")]
    for x, label in boxes:
        ax.text(x, .52, label, transform=ax.transAxes, ha="left", va="center", fontsize=11,
                bbox={"boxstyle":"round,pad=.55", "facecolor":"#edf2ef", "edgecolor":"#385449"})
    for x in (.13, .30, .47, .64, .81):
        ax.annotate("", xy=(x+.035,.52), xytext=(x,.52), xycoords="axes fraction",
                    arrowprops={"arrowstyle":"->", "color":"#b07b37", "lw":1.6})
    ax.text(.01,.04,"Нейронный replay измеряет условный эффект на декодере; выход адаптеров и objective-controller пересчитан на тех же записанных состояниях. Физическая траектория не моделировалась.",
            transform=ax.transAxes,ha="left",va="bottom",fontsize=8,color="#4d5b54")
    ax.set_title("Причинная цепочка от сигнала до итоговой команды", fontsize=12)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(figdir / f"fig1_causal_chain.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)

    horizons = [0, 20, 100, 500, 1000]
    by_h = {}
    for h in horizons:
        rows = [r for r in event_rows if r["horizon_ms"] == h]
        by_h[h] = rows
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), constrained_layout=True)
    for ax, key, title, ylabel in [
        (axes[0], "neural_l2_mute", "Нейронный отклик", "L2, 6 выходов"),
        (axes[1], "decoder_l2_mute", "Декодированная команда", "L2, нормированные команды"),
    ]:
        for i, h in enumerate(horizons):
            vals = [r[key] for r in by_h[h] if r[key] is not None]
            if vals:
                jitter = np.linspace(-.13, .13, len(vals)) if len(vals) > 1 else [0]
                ax.scatter(np.asarray([i]*len(vals))+jitter, vals, color="#527a68", alpha=.72, s=20)
                ax.plot(i, np.mean(vals), marker="D", color="#bd8b49", ms=6)
        ax.set_xticks(range(len(horizons)), [str(x) for x in horizons])
        ax.set_xlabel("Время после вмешательства, мс")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="y", alpha=.25)
    fig.suptitle("Mute против baseline · точки — события, кластеры — seed (n=8)")
    for ext in ("png", "svg", "pdf"):
        fig.savefig(figdir / f"fig2_response.{ext}", dpi=180)
    plt.close(fig)

    at1000 = [r for r in event_rows if r["horizon_ms"] == 1000]
    fig, ax = plt.subplots(figsize=(6.5, 4.5), constrained_layout=True)
    for r in at1000:
        ax.scatter(r["recipient_pre_activity"], r["decoder_l2_mute"], color="#527a68", alpha=.78)
    ax.set_xlabel("Предварительная активность получателя, L2")
    ax.set_ylabel("Изменение декодера через 1000 мс, L2")
    ax.set_title("Ответ при matched ненулевом Δ входа; exploratory")
    ax.grid(alpha=.25)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(figdir / f"fig3_context.{ext}", dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 4.3), constrained_layout=True)
    for ax, key, title, ylabel in [
        (axes[0], "neural_l2", "Нейронный выход · mute vs shuffle", "L2"),
        (axes[1], "decoder_l2", "Команда декодера · mute vs shuffle", "L2"),
    ]:
        xs, ys = [], []
        for i, r in enumerate(at1000):
            xs += [i-.12, i+.12]
            ys += [r[f"{key}_mute"], r[f"{key}_control"]]
            ax.plot([i-.12,i+.12], [r[f"{key}_mute"],r[f"{key}_control"]], color="#a9b0a8", lw=.8)
        ax.scatter(xs[::2], ys[::2], label="mute", color="#b07b37", s=25)
        ax.scatter(xs[1::2], ys[1::2], label="shuffle", color="#527a68", s=25)
        ax.set_xlabel("Событие")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="y", alpha=.25)
        ax.legend(frameon=False)
    fig.suptitle("Mute и matched shuffle: нейронный выход и команда декодера через 1000 мс")
    for ext in ("png", "svg", "pdf"):
        fig.savefig(figdir / f"fig4_mute_vs_control.{ext}", dpi=180)
    plt.close(fig)


def analyze_existing_outputs():
    """Add reproducibility, detectability, and paired seed-level summaries."""
    OUT.mkdir(parents=True, exist_ok=True)
    plan=json.loads((OUT/"selection_and_reproducibility.json").read_text(encoding="utf-8"))
    replay=[]
    for block in plan["seed_blocks"]:
        npz_path=OUT/"raw"/f"seed-{block['seed']}-baseline.npz"
        source=ROOT/block["source_path"]
        if hashlib.sha256(source.read_bytes()).hexdigest()!=block["source_sha256"]:
            raise ValueError(f"source checksum mismatch for seed {block['seed']}")
        validation=json.loads((source.parent/"validation.json").read_text(encoding="utf-8"))
        if not validation.get("valid"):
            raise ValueError(f"source run is not validated for seed {block['seed']}")
        observed=[]
        with source.open(encoding="utf-8") as stream:
            for line in stream:
                if line.strip():
                    observed.append(json.loads(line).get("neural_traces"))
                    if len(observed)>=len(np.load(npz_path)["neural"]): break
        cached=np.load(npz_path)["neural"]
        observed=np.asarray(observed,dtype=float)
        if cached.shape!=observed.shape:
            raise ValueError(f"baseline replay shape mismatch for seed {block['seed']}")
        replay.append({"seed":block["seed"],"source_run":block["source_run"],
                       "source_sha256_valid":True,"run_validation_valid":True,
                       "steps":len(cached),"max_abs_neural_error":max_abs(cached,observed)})
    save_csv(OUT/"baseline_replay_validation.csv",replay)

    with (OUT/"intervention_event_metrics.csv").open(newline="",encoding="utf-8") as stream:
        rows=list(csv.DictReader(stream))
    for row in rows:
        for key in ("seed","event_index","horizon_ms"):
            row[key]=int(row[key])
        for key in ("neural_l2_mute","decoder_l2_mute","neural_l2_control","decoder_l2_control"):
            row[key]=float(row[key])
    threshold=1e-9  # exact sham replay was zero at all measured levels
    events={}
    for row in rows:
        events.setdefault((row["seed"],row["event_index"]),[]).append(row)
    detect_rows=[]
    for (seed,event),series in sorted(events.items()):
        series.sort(key=lambda x:x["horizon_ms"])
        first_neural=next((r["horizon_ms"] for r in series if r["neural_l2_mute"]>threshold),None)
        first_decoder=next((r["horizon_ms"] for r in series if r["decoder_l2_mute"]>threshold),None)
        detect_rows.append({"seed":seed,"event_index":event,"first_neural_detectable_ms":first_neural,
                            "first_decoder_detectable_ms":first_decoder,
                            "neural_detectable_by_1000ms":first_neural is not None,
                            "decoder_detectable_by_1000ms":first_decoder is not None})
    save_csv(OUT/"event_detectability.csv",detect_rows)
    per_seed=[]
    for seed in sorted({r["seed"] for r in detect_rows}):
        part=[r for r in detect_rows if r["seed"]==seed]
        per_seed.append({"seed":seed,
                         "neural_detectable_fraction":float(np.mean([r["neural_detectable_by_1000ms"] for r in part])),
                         "decoder_detectable_fraction":float(np.mean([r["decoder_detectable_by_1000ms"] for r in part]))})
    detection={"threshold_l2":threshold,"sham_max_abs":json.loads((OUT/"statistics.json").read_text())["sham_max_abs"],
               "seed_level_neural_detectable_fraction":{"mean":float(np.mean([r["neural_detectable_fraction"] for r in per_seed])),
                 "seed_cluster_bootstrap_95ci":bootstrap_ci([r["neural_detectable_fraction"] for r in per_seed]),"n_seed":len(per_seed)},
               "seed_level_decoder_detectable_fraction":{"mean":float(np.mean([r["decoder_detectable_fraction"] for r in per_seed])),
                 "seed_cluster_bootstrap_95ci":bootstrap_ci([r["decoder_detectable_fraction"] for r in per_seed],seed=20261030),"n_seed":len(per_seed)},
               "first_detectable_decoder_ms_median":float(np.median([r["first_decoder_detectable_ms"] for r in detect_rows if r["first_decoder_detectable_ms"] is not None]))}
    seed_rows=[]
    for seed in sorted({r["seed"] for r in rows if r["horizon_ms"]==1000}):
        part=[r for r in rows if r["seed"]==seed and r["horizon_ms"]==1000]
        seed_rows.append({"seed":seed,"mute_decoder_l2_mean":float(np.mean([r["decoder_l2_mute"] for r in part])),
                          "control_decoder_l2_mean":float(np.mean([r["decoder_l2_control"] for r in part])),
                          "control_minus_mute":float(np.mean([r["decoder_l2_control"]-r["decoder_l2_mute"] for r in part]))})
    paired={"control_minus_mute_decoder_l2":{"mean":float(np.mean([r["control_minus_mute"] for r in seed_rows])),
            "seed_cluster_bootstrap_95ci":bootstrap_ci([r["control_minus_mute"] for r in seed_rows],seed=20261031),"n_seed":len(seed_rows)}}
    stats=json.loads((OUT/"statistics.json").read_text(encoding="utf-8"))
    stats["reproducibility"]={"baseline_replay_max_abs_neural_error":max(r["max_abs_neural_error"] for r in replay),
                               "n_valid_source_runs":len(replay)}
    stats["detectability"]=detection
    stats["paired_control_contrast"]=paired
    (OUT/"statistics.json").write_text(json.dumps(stats,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    save_csv(OUT/"paired_seed_control_contrasts.csv",seed_rows)
    make_figures(rows)
    print(json.dumps({"reproducibility":stats["reproducibility"],"detectability":detection,"paired":paired},indent=2))


def channel_census():
    """Describe how often sender removal survives the baseline 0.8 cap."""
    OUT.mkdir(parents=True,exist_ok=False)
    candidate_rows=[];seed_rows=[]
    for seed,path in seed_sources():
        _,rows=read_source(path,MAX_SCAN_STEPS)
        brain=DualBrain(seed=seed)
        _,_,_,candidates=baseline_scan(brain,rows)
        for item in candidates:
            candidate_rows.append({k:v for k,v in item.items() if k!="donor_options"})
        nonzero=[x for x in candidates if x["mute_input_delta"]>1e-9]
        seed_rows.append({"seed":seed,"candidate_links":len(candidates),
          "saturated_fraction":float(np.mean([x["baseline_heard"]>=.8-1e-9 for x in candidates])) if candidates else None,
          "zero_mute_effect_fraction":float(np.mean([x["mute_input_delta"]<=1e-9 for x in candidates])) if candidates else None,
          "nonzero_mute_effect_fraction":len(nonzero)/len(candidates) if candidates else None,
          "mean_mute_input_delta":float(np.mean([x["mute_input_delta"] for x in candidates])) if candidates else None,
          "mean_distance_m":float(np.mean([x["distance_m"] for x in candidates])) if candidates else None})
        print(json.dumps({"seed":seed,"candidate_links":len(candidates)}),flush=True)
    save_csv(OUT/"channel_link_census.csv",candidate_rows)
    save_csv(OUT/"channel_seed_summary.csv",seed_rows)
    summary={"schema":"flyswarm.causal.context.channel_census.v1",
      "independent_unit":"seed","n_seed":len(seed_rows),
      "candidate_link_samples_not_independent":sum(x["candidate_links"] for x in seed_rows),
      "mean_seed_saturated_fraction":float(np.mean([x["saturated_fraction"] for x in seed_rows])),
      "mean_seed_zero_mute_effect_fraction":float(np.mean([x["zero_mute_effect_fraction"] for x in seed_rows])),
      "mean_seed_nonzero_mute_effect_fraction":float(np.mean([x["nonzero_mute_effect_fraction"] for x in seed_rows])),
      "mean_seed_mute_input_delta":float(np.mean([x["mean_mute_input_delta"] for x in seed_rows])),
      "note":"Candidate links are repeated observations nested in eight seeds, sampled every fifth neural tick; seed-level proportions are the descriptive summaries."}
    (OUT/"channel_census_statistics.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)


def main():
    if len(sys.argv)>1 and sys.argv[1]=="--analyze-existing":
        analyze_existing_outputs()
        return
    if len(sys.argv)>1 and sys.argv[1]=="--channel-census":
        channel_census()
        return
    start = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=False)
    all_plan, raw_results, metric_rows, seed_sham = [], [], [], []
    for seed, path in seed_sources():
        manifest = json.loads((path.parent / "manifest.json").read_text())
        # Baseline scan is performed before any outcome-producing intervention.
        # It is bounded to the first 5 s of recorded real combat history.
        _, rows = read_source(path, MAX_SCAN_STEPS)
        brain = DualBrain(seed=seed)
        base_trace, base_cmd, base_heard, candidates = baseline_scan(brain, rows)
        events = choose_events(candidates)
        if len(events) < 2:
            raise RuntimeError(f"pre-registered matched-event rule yielded <2 events for seed {seed}")
        max_tick = max(x["tick"] for x in events) + max(HORIZONS)
        # Exact repeated no-change replay (D: sham) against the scan baseline.
        sham_trace, sham_cmd, sham_heard, _ = result_vectors(brain, rows, max_tick, {"events": []})
        sham = {"seed": seed, "neural_max_abs": max_abs(base_trace[:max_tick], sham_trace),
                "command_max_abs": max_abs(base_cmd[:max_tick], sham_cmd),
                "heard_max_abs": max_abs(base_heard[:max_tick], sham_heard)}
        seed_sham.append(sham)
        if max(sham["neural_max_abs"], sham["command_max_abs"], sham["heard_max_abs"]) > 1e-9:
            raise RuntimeError(f"sham reproducibility failure: {sham}")
        source_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        seed_event_summaries = []
        for number, event in enumerate(events, 1):
            # The selector only saw baseline channel deltas and pre-event trace.
            muted = run_event(brain, rows, event, "mute")
            controlled = run_event(brain, rows, event, "shuffle_sender")
            mt, mc, mh, mf = muted
            ct, cc, ch, cf = controlled
            tick = int(event["tick"])
            applied_mute = next((x for x in (mf[tick-1] or {}).get("interventions", [])), None)
            applied_control = next((x for x in (cf[tick-1] or {}).get("interventions", [])), None)
            if not applied_mute or not applied_control:
                raise RuntimeError(f"intervention not applied exactly at selected tick: {seed}, {event}")
            if applied_mute["kind"] != "mute" or applied_control["kind"] != "shuffle_sender":
                raise RuntimeError("wrong intervention kind recorded")
            item = {**event, "seed": seed, "event_index": number, "source_run": manifest["run_id"],
                    "source_neural_steps_sha256": source_sha,
                    "mute_applied": applied_mute, "control_applied": applied_control,
                    "selection_rule": "matched baseline delivered mute deltas within max(0.005,20%); require nonzero same-team sender-shuffle matched to the mute input effect; prioritize source-amplitude diversity then pre-event receiver neural-state contrast; no post-treatment outcomes used"}
            seed_event_summaries.append(item)
            for step_h in HORIZONS:
                ix = tick - 1 + step_h
                base_n, mute_n, ctrl_n = base_trace[ix], mt[ix], ct[ix]
                base_a, mute_a, ctrl_a = base_cmd[ix], mc[ix], cc[ix]
                rec = int(event["receiver"])
                row = {"seed": seed, "event_index": number, "tick": tick,
                       "sender": int(event["sender"]), "receiver": rec, "horizon_ms": step_h * 20,
                       "mute_input_delta": float(event["mute_input_delta"]),
                       "baseline_heard": float(event["baseline_heard"]),
                       "cap_margin": float(event["cap_margin"]),
                       "distance_m": float(event["distance_m"]),
                       "source_signal": float(event["signal"]),
                       "recipient_pre_activity": float(event["recipient_pre_activity"]),
                       "neural_l2_mute": float(np.linalg.norm(mute_n[rec] - base_n[rec])),
                       "decoder_l2_mute": float(np.linalg.norm(mute_a[rec] - base_a[rec])),
                       "heard_delta_mute": float(mh[ix, rec] - base_heard[ix, rec]),
                       "neural_l2_control": float(np.linalg.norm(ctrl_n[rec] - base_n[rec])),
                       "decoder_l2_control": float(np.linalg.norm(ctrl_a[rec] - base_a[rec])),
                       "heard_delta_control": float(ch[ix, rec] - base_heard[ix, rec]),
                       "dnp09_l_mute": float(mute_n[rec,0]-base_n[rec,0]),
                       "dnp09_r_mute": float(mute_n[rec,1]-base_n[rec,1]),
                       "dna02_l_mute": float(mute_n[rec,2]-base_n[rec,2]),
                       "dna02_r_mute": float(mute_n[rec,3]-base_n[rec,3]),
                       "dnp01_mute": float(mute_n[rec,4]-base_n[rec,4]),
                       "wing_mute": float(mute_n[rec,5]-base_n[rec,5]),
                       "decoder_command_delta": json.dumps((mute_a[rec]-base_a[rec]).tolist()),
                       "control_command_delta": json.dumps((ctrl_a[rec]-base_a[rec]).tolist()),
                       "practically_meaningful": bool(np.linalg.norm(mute_a[rec]-base_a[rec]) >= COMMAND_IMPORTANCE_THRESHOLD)}
                metric_rows.append(row)
            payload = {"schema": "flyswarm.causal.context.event.v1", "event": item,
                       "horizons": [r for r in metric_rows if r["seed"] == seed and r["event_index"] == number]}
            raw_path = OUT / "raw" / f"seed-{seed}-event-{number}.json"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_text(json.dumps(payload, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        all_plan.append({"seed": seed, "source_run": manifest["run_id"], "source_path": str(path.relative_to(ROOT)),
                         "source_sha256": source_sha, "source_git_commit": manifest.get("metadata", {}).get("git_commit"),
                         "scan_steps": MAX_SCAN_STEPS, "candidate_count": len(candidates),
                         "events": seed_event_summaries, "sham": sham})
        (OUT / "raw" / f"seed-{seed}-baseline.npz").parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(OUT / "raw" / f"seed-{seed}-baseline.npz",
                            neural=base_trace[:max_tick], decoder=base_cmd[:max_tick], heard=base_heard[:max_tick])
        print(json.dumps({"seed": seed, "selected_events": len(events), "sham": sham,
                          "elapsed_min": round((time.monotonic()-start)/60,2)}), flush=True)

    (OUT / "protocol_lock.json").write_text(json.dumps({
        "schema":"flyswarm.causal.context.protocol.v1", "created_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
        "design":"E1 directed mute vs matched shuffle_sender, exact sham, repeated on fixed recorded observations",
        "primary":"receiver decoded-command L2 difference at 1000 ms; seed is independent unit",
        "thresholds":{"sham_numeric":1e-9,"practical_command_l2":COMMAND_IMPORTANCE_THRESHOLD},
        "selection":"baseline scan 25..250 ticks; pair nonzero mute effects with delivered-input deltas within max(0.005,20%); require a same-team shuffle_sender control with a nonzero delivered-input change matched to the mute effect; prioritize within-seed source-amplitude diversity then maximize pre-event recipient activity contrast; no treatment outputs used",
        "horizons_ms":[0,20,100,500,1000], "max_scan_steps":MAX_SCAN_STEPS,
        "notes":"Open-loop conditional neural/decoder effect; no physical-state restore or closed-loop trajectory claim. The shuffle_sender donor is selected by its predicted change to the capped delivered input, not by source-amplitude similarity. The scalar channel does not encode sender identity."}, indent=2)+"\n", encoding="utf-8")
    (OUT / "selection_and_reproducibility.json").write_text(json.dumps({"seed_blocks":all_plan,"sham_summary":seed_sham},indent=2,allow_nan=False)+"\n",encoding="utf-8")
    save_csv(OUT/"intervention_event_metrics.csv", metric_rows)

    # Seed-cluster inference: average within seed before resampling.
    by_seed = {}
    for row in metric_rows:
        if row["horizon_ms"] == 1000:
            by_seed.setdefault(row["seed"], []).append(row)
    seed_rows = []
    for seed, items in sorted(by_seed.items()):
        seed_rows.append({"seed":seed,"events":len(items),
                          "decoder_l2_mute_mean":float(np.mean([x["decoder_l2_mute"] for x in items])),
                          "decoder_l2_control_mean":float(np.mean([x["decoder_l2_control"] for x in items])),
                          "neural_l2_mute_mean":float(np.mean([x["neural_l2_mute"] for x in items])),
                          "decoder_practical_fraction":float(np.mean([x["practically_meaningful"] for x in items])),
                          "mean_mute_input_delta":float(np.mean([x["mute_input_delta"] for x in items])),
                          "mean_pre_activity":float(np.mean([x["recipient_pre_activity"] for x in items]))})
    save_csv(OUT/"seed_level_metrics.csv",seed_rows)
    means = {}
    for key in ("decoder_l2_mute_mean","decoder_l2_control_mean","neural_l2_mute_mean","decoder_practical_fraction"):
        v=[x[key] for x in seed_rows]
        means[key]={"mean":float(np.mean(v)),"seed_cluster_bootstrap_95ci":bootstrap_ci(v),"n_seed":len(v)}
    # Within-seed contrast in matched-context pairs (only when both events exist).
    context_diffs=[]
    for seed, items in sorted(by_seed.items()):
        if len(items)<2: continue
        low, high=sorted(items,key=lambda x:x["recipient_pre_activity"])
        context_diffs.append({"seed":seed,"pre_activity_gap":high["recipient_pre_activity"]-low["recipient_pre_activity"],
                              "decoder_effect_gap_high_minus_low":high["decoder_l2_mute"]-low["decoder_l2_mute"],
                              "input_delta_gap":high["mute_input_delta"]-low["mute_input_delta"]})
    save_csv(OUT/"matched_context_seed_contrasts.csv",context_diffs)
    stats={"schema":"flyswarm.causal.context.seed_summary.v1","seed_level":means,
           "context_high_minus_low":{"mean":float(np.mean([r["decoder_effect_gap_high_minus_low"] for r in context_diffs])) if context_diffs else None,
             "seed_cluster_bootstrap_95ci":bootstrap_ci([r["decoder_effect_gap_high_minus_low"] for r in context_diffs]) if context_diffs else [None,None],
             "n_seed":len(context_diffs)},
           "control_minus_mute_mean":float(np.mean([r["decoder_l2_control_mean"]-r["decoder_l2_mute_mean"] for r in seed_rows])) if seed_rows else None,
           "independent_unit":"seed; events and horizons are repeated measures", "confirmatory":False,
           "elapsed_minutes":round((time.monotonic()-start)/60,2), "practical_threshold_l2":COMMAND_IMPORTANCE_THRESHOLD,
           "sham_max_abs":{k:max(x[k] for x in seed_sham) for k in ("neural_max_abs","command_max_abs","heard_max_abs")}}
    (OUT/"statistics.json").write_text(json.dumps(stats,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    make_figures(metric_rows)
    print(json.dumps({"output":str(OUT),"events":len(all_plan)*2,"seed_blocks":len(all_plan),"statistics":stats,
                      "elapsed_minutes":round((time.monotonic()-start)/60,2)},indent=2),flush=True)


if __name__ == "__main__":
    main()
