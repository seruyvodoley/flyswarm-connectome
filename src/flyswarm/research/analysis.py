"""Pair-aware, seed-level statistics and restrained publication figures."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
from scipy.stats import t


PRIMARY = "terminal_ticket_balance"


def _summary_metrics(summary: dict, validation: dict | None = None) -> dict[str, float]:
    tickets = summary.get("tickets", [None, None])
    alive = summary.get("alive", [None, None])
    if any(x is None for x in alive):
        states = summary.get("vehicles", [])
        alive = [sum(1 for state in states if state.get("team") == team and state.get("alive"))
                 for team in ("blue", "red")] if states else [None, None]
    if len(tickets) != 2 or any(x is None for x in tickets):
        raise ValueError("summary has no two-team terminal ticket values")
    result = {PRIMARY: (float(tickets[0]) - float(tickets[1])) / 600.0}
    if len(alive) == 2 and all(x is not None for x in alive):
        result["terminal_alive_balance"] = (float(alive[0]) - float(alive[1])) / 16.0
    if summary.get("time") is not None:
        result["duration_s"] = float(summary["time"])
    result["realtime_factor"] = float(summary.get("realtime_factor", 0.0))
    result["neural_tick_ms_mean"] = float(summary.get("male_cns_tick_ms", {}).get("mean") or 0.0)
    result["neural_tick_ms_p99"] = float(summary.get("male_cns_tick_ms", {}).get("p99") or 0.0)
    agent_metrics=[state.get("metrics",{}) for state in summary.get("vehicles",[])]
    for key, output in (("distance_travelled","mean_distance_m"),("stationary_s","mean_stationary_s"),
                        ("reverse_s","mean_reverse_s"),("target_visible_s","mean_target_visible_s"),
                        ("target_switches","mean_target_switches"),("capture_s","mean_capture_s"),
                        ("objective_presence_s","mean_objective_presence_s"),("chassis_aim_s","mean_chassis_aim_s")):
        values=[float(item[key]) for item in agent_metrics if isinstance(item.get(key),(int,float)) and np.isfinite(item[key])]
        if values:result[output]=float(np.mean(values))
    audit=(validation or {}).get("combat_events",{})
    counts=audit.get("counts",{})
    if audit.get("valid"):
        result["shot_count"]=float(audit.get("shots",0))
        result["hit_count"]=float(audit.get("vehicle_hits",0))
        result["penetration_count"]=float(audit.get("penetrations",0))
        result["damage_event_count"]=float(audit.get("damaging_shots",0))
        result["kill_count"]=float(audit.get("kills",0))
        if result["shot_count"]>0:result["accuracy"]=result["hit_count"]/result["shot_count"]
        if result["hit_count"]>0:
            result["penetration_rate"]=result["penetration_count"]/result["hit_count"]
            result["kill_per_hit_rate"]=result["kill_count"]/result["hit_count"]
        result["destruction_event_count"]=float(counts.get("vehicle_destroyed",0))
        result["objective_change_count"]=float(counts.get("objective_owner_changed",0))
    return result


def load_seed_level(experiment: Path) -> list[dict]:
    rows = []
    for manifest_path in sorted(experiment.glob("runs/*/manifest.json")):
        run = manifest_path.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validation_path = run / "validation.json"
        validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {"valid": False}
        if not validation.get("valid"):
            continue
        summary_path = run / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        saved_validation=json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.exists() else {}
        metrics = _summary_metrics(summary,saved_validation)
        intervention_path = run / "control_interventions.json"
        if intervention_path.exists():
            values = json.loads(intervention_path.read_text(encoding="utf-8")).get("mean_l1_per_agent_frame", {})
            metrics.update({f"intervention_{key}": float(value) for key, value in values.items() if value is not None})
        rows.append({"condition": manifest["condition"], "seed": int(manifest["seed"]),
                     "side_swap": bool(manifest["side_swap"]), "metrics": metrics})
    # Two map-side assignments are technical repetitions within a seed, not
    # independent observations. Average them before inferential statistics.
    grouped: dict[tuple[str, int], list[dict]] = {}
    for row in rows:
        grouped.setdefault((row["condition"], row["seed"]), []).append(row)
    result = []
    for (condition, seed), items in sorted(grouped.items()):
        if len(items)!=2 or {item["side_swap"] for item in items}!={False,True}:
            continue
        metrics = sorted(set.intersection(*(set(item["metrics"]) for item in items)))
        result.append({"condition": condition, "seed": seed,
                       "side_assignments": len(items),
                       "metrics": {key: float(np.mean([item["metrics"][key] for item in items])) for key in metrics}})
    return result


def count_incomplete_seed_pairs(experiment: Path) -> int:
    pairs: dict[tuple[str,int],set[bool]]={}
    for manifest_path in Path(experiment).glob("runs/*/manifest.json"):
        try:
            manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
            validation=json.loads((manifest_path.parent/"validation.json").read_text(encoding="utf-8"))
        except (OSError,json.JSONDecodeError):
            continue
        if not validation.get("valid"):continue
        pairs.setdefault((manifest["condition"],int(manifest["seed"])),set()).add(bool(manifest["side_swap"]))
    return sum(assignments!={False,True} for assignments in pairs.values())


def _sign_flip_p(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    observed = abs(float(values.mean()))
    if values.size <= 16:
        signs = np.asarray([[1 if (mask >> i) & 1 else -1 for i in range(values.size)]
                            for mask in range(1 << values.size)], dtype=float)
        null = np.abs((signs * values).mean(axis=1))
        return float(np.count_nonzero(null >= observed) / len(null))
    rng = np.random.default_rng(1937)
    null = np.abs(rng.choice([-1.0, 1.0], size=(100_000, len(values))) * values).mean(axis=1)
    return float((np.count_nonzero(null >= observed) + 1) / (len(null) + 1))


def paired_effect(x: np.ndarray, y: np.ndarray, seed: int = 73021) -> dict:
    delta = np.asarray(x, dtype=float) - np.asarray(y, dtype=float)
    n = len(delta)
    if not n:
        raise ValueError("No matched independent experimental seeds")
    mean = float(delta.mean())
    sd = float(delta.std(ddof=1)) if n > 1 else None
    if n > 1:
        half = float(t.ppf(.975, n - 1) * sd / np.sqrt(n))
        low, high = mean - half, mean + half
        d_z = mean / sd if sd > 0 else None
    else:
        low = high = None
        d_z = None
    rng = np.random.default_rng(seed)
    bootstrap = np.mean(rng.choice(delta, size=(20_000, n), replace=True), axis=1) if n>1 else None
    return {"n_independent_seeds": n, "mean_difference": mean,
            "median_difference": float(np.median(delta)), "sd_difference": sd,
            "ci95_t": [low, high],
            "bootstrap_ci95_seed_resampling": [float(np.quantile(bootstrap, .025)), float(np.quantile(bootstrap, .975))] if bootstrap is not None else None,
            "small_sample_note": "Seed-resampling and asymptotic inference are descriptive with fewer than 5 independent seeds." if n<5 else None,
            "paired_standardized_effect_dz": d_z,
            "exact_or_monte_carlo_sign_flip_p": _sign_flip_p(delta),
            "seed_differences": delta.tolist()}


def analyze(experiment: Path, reference: str = "RULE_BASED") -> dict:
    experiment = Path(experiment)
    rows = load_seed_level(experiment)
    if not rows:
        raise ValueError("No valid complete runs are available for analysis")
    conditions = sorted({row["condition"] for row in rows})
    if reference not in conditions:
        raise ValueError(f"Reference condition {reference} has no valid completed runs")
    metrics = sorted(set.intersection(*(set(row["metrics"]) for row in rows)))
    effects = {}
    raw_ps = []
    for condition in conditions:
        if condition == reference:
            continue
        left = {row["seed"]: row["metrics"] for row in rows if row["condition"] == condition}
        right = {row["seed"]: row["metrics"] for row in rows if row["condition"] == reference}
        shared = sorted(set(left) & set(right))
        if not shared:
            continue
        effects[condition] = {"reference": reference, "matched_seeds": shared, "metrics": {}}
        for metric in metrics:
            result = paired_effect(np.array([left[s][metric] for s in shared]),
                                   np.array([right[s][metric] for s in shared]),
                                   seed=73021 + sum(map(ord, condition + metric)))
            effects[condition]["metrics"][metric] = result
            raw_ps.append((condition, metric, result["exact_or_monte_carlo_sign_flip_p"]))
    # Benjamini-Hochberg across the explicitly secondary comparisons only.
    secondary = sorted((item for item in raw_ps if item[1] != PRIMARY), key=lambda item: item[2])
    qvalues = {}
    running = 1.0
    for rank in range(len(secondary), 0, -1):
        condition, metric, p_value = secondary[rank - 1]
        running = min(running, p_value * len(secondary) / rank)
        qvalues[(condition, metric)] = running
    for condition, metric, _ in raw_ps:
        effects[condition]["metrics"][metric]["bh_q_secondary"] = qvalues.get((condition, metric))
    report = {"schema": "flyswarm.research.analysis.v1", "experiment_id": experiment.name,
              "primary_metric": PRIMARY, "reference_condition": reference,
              "valid_condition_seed_rows": len(rows), "independent_seed_level_rows": len(rows),
              "excluded_incomplete_side_pairs": count_incomplete_seed_pairs(experiment),
              "conditions": conditions, "seed_level": rows, "paired_effects": effects,
              "interpretation": "Pilot or descriptive statistics only. Statistical significance does not establish a biological mechanism; report the prespecified design and all exclusions."}
    target = experiment / "processed"
    target.mkdir(exist_ok=True)
    json_path = target / "analysis.json"
    if json_path.exists():
        raise FileExistsError(json_path)
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    csv_path = target / "seed_level.csv"
    with csv_path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["condition", "seed", "side_assignments", *metrics])
        for row in rows:
            writer.writerow([row["condition"], row["seed"], row["side_assignments"], *(row["metrics"][key] for key in metrics)])
    run_rows=[]
    for manifest_path in sorted(experiment.glob("runs/*/manifest.json")):
        run=manifest_path.parent
        validation_path=run/"validation.json"
        if not validation_path.is_file():continue
        validation=json.loads(validation_path.read_text(encoding="utf-8"))
        if not validation.get("valid"):continue
        summary_path=run/"summary.json"
        if not summary_path.is_file():continue
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        row={"run_id":manifest["run_id"],"condition":manifest["condition"],"seed":int(manifest["seed"]),
             "side_swap":bool(manifest["side_swap"]),**_summary_metrics(json.loads(summary_path.read_text(encoding="utf-8")),validation)}
        intervention_path=run/"control_interventions.json"
        if intervention_path.is_file():
            row.update({f"intervention_{k}":v for k,v in json.loads(intervention_path.read_text(encoding="utf-8")).get("mean_l1_per_agent_frame",{}).items() if v is not None})
        run_rows.append(row)
    if run_rows:
        run_csv=target/"run_level.csv"
        fields=["run_id","condition","seed","side_swap",*sorted(set().union(*(set(row)-{"run_id","condition","seed","side_swap"} for row in run_rows)))]
        with run_csv.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(run_rows)
    _figures(experiment, rows, metrics)
    _time_series_figures(experiment)
    return report


def _figures(experiment: Path, rows: list[dict], metrics: list[str]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figures = experiment / "figures"
    figures.mkdir(exist_ok=True)
    conditions = sorted({row["condition"] for row in rows})
    for metric in metrics:
        fig, ax = plt.subplots(figsize=(7.2, 4.2), constrained_layout=True)
        for index, condition in enumerate(conditions):
            values = np.asarray([row["metrics"][metric] for row in rows if row["condition"] == condition])
            if values.size == 0:
                continue
            ax.scatter(np.full(values.size, index), values, s=20, alpha=.75)
            mean = float(values.mean())
            if values.size > 1:
                ci = float(t.ppf(.975, values.size - 1) * values.std(ddof=1) / np.sqrt(values.size))
                ax.errorbar(index, mean, yerr=ci, color="black", marker="D", capsize=4, linewidth=1)
            else:
                ax.scatter([index],[mean],marker="D",color="black",zorder=3)
                ax.annotate("n=1; CI unavailable",(index,mean),xytext=(5,5),textcoords="offset points",fontsize=7)
        ax.set_xticks(range(len(conditions)), conditions, rotation=20, ha="right")
        ax.set_ylabel(metric.replace("_", " "))
        ax.set_title(f"FlySwarm Godot 3D + MaleCNS: {metric.replace('_', ' ')}")
        ax.grid(axis="y", color="#dddddd", linewidth=.6)
        for suffix in ("png", "svg", "pdf"):
            fig.savefig(figures / f"{metric}.{suffix}", dpi=180 if suffix == "png" else None)
        plt.close(fig)


def _time_series_figures(experiment: Path) -> None:
    """Export descriptive neural, controller, behavior, and trajectory series."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_root=experiment/"figures"
    figure_root.mkdir(exist_ok=True)
    channel_names=("DNp09_L","DNp09_R","DNa02_L","DNa02_R","DNp01","wing")
    action_names=("throttle","brake","steering","turret","elevation","fire")
    neural_rows=[];behavior_rows=[];trajectory_rows=[];correlation_rows=[]
    for manifest_path in sorted(experiment.glob("runs/*/manifest.json")):
        run=manifest_path.parent
        validation_path=run/"validation.json"
        if not validation_path.is_file() or not json.loads(validation_path.read_text()).get("valid"):continue
        manifest=json.loads(manifest_path.read_text())
        condition=manifest["condition"];run_id=manifest["run_id"]
        npath=run/"neural_steps.jsonl"
        if npath.is_file():
            for line in npath.read_text(encoding="utf-8").splitlines():
                if not line:continue
                row=json.loads(line);traces=row.get("neural_traces",[]);actions=row.get("applied_actions",[])
                if len(traces)<8:continue
                for channel,name in enumerate(channel_names):
                    if any(len(trace)<=channel for trace in traces[:8]):continue
                    neural_rows.append({"condition":condition,"run_id":run_id,"simulation_time_s":row["simulation_time_s"],
                                        "signal_type":"neural","name":name,"mean_value":float(np.mean([trace[channel] for trace in traces[:8]]))})
                if len(actions)>=8:
                    for channel,name in enumerate(action_names):
                        if any(len(action)<=channel for action in actions[:8]):continue
                        neural_rows.append({"condition":condition,"run_id":run_id,"simulation_time_s":row["simulation_time_s"],
                                            "signal_type":"applied_action","name":name,"mean_value":float(np.mean([action[channel] for action in actions[:8]]))})
        if npath.is_file():
            samples=[]
            for line in npath.read_text(encoding="utf-8").splitlines():
                if not line:continue
                row=json.loads(line);traces=row.get("neural_traces",[]);actions=row.get("applied_actions",[])
                if len(traces)<8 or len(actions)<8:continue
                if any(len(value)<6 for value in traces[:8]) or any(len(value)<6 for value in actions[:8]):continue
                samples.append((np.asarray(traces[:8],dtype=float),np.asarray(actions[:8],dtype=float)))
            for neural_channel,channel_name in enumerate(channel_names):
                for action_index,action_name in enumerate(action_names):
                    x=np.concatenate([pair[0][:,neural_channel] for pair in samples]) if samples else np.asarray([])
                    y=np.concatenate([pair[1][:,action_index] for pair in samples]) if samples else np.asarray([])
                    correlation=float(np.corrcoef(x,y)[0,1]) if x.size>=3 and np.std(x)>0 and np.std(y)>0 else None
                    correlation_rows.append({"condition":condition,"run_id":run_id,"neural_channel":channel_name,
                        "action":action_name,"pearson_r_descriptive":correlation,"agent_step_pairs":int(x.size),
                        "interpretation":"within-run descriptive association; repeated agent/time samples are not independent observations"})
        gpath=run/"game_steps.jsonl"
        if not gpath.is_file():continue
        for line in gpath.read_text(encoding="utf-8").splitlines():
            if not line:continue
            row=json.loads(line);agents=row.get("agents",[])
            blue=[agent for agent in agents if agent.get("team")=="blue"]
            red=[agent for agent in agents if agent.get("team")=="red"]
            if len(blue)!=8 or len(red)!=8:continue
            time_s=float(row["simulation_time_s"])
            behavior_rows.append({"condition":condition,"run_id":run_id,"simulation_time_s":time_s,
                "blue_tickets":float(row["tickets"][0]),"red_tickets":float(row["tickets"][1]),
                "blue_mean_speed_m_s":float(np.mean([agent["speed_m_s"] for agent in blue])),
                "red_mean_speed_m_s":float(np.mean([agent["speed_m_s"] for agent in red])),
                "blue_visible_fraction":float(np.mean([bool(agent["visible"]) for agent in blue])),
                "red_visible_fraction":float(np.mean([bool(agent["visible"]) for agent in red]))})
            for agent in agents:
                point=agent.get("position",[])
                if len(point)>=3:
                    trajectory_rows.append({"condition":condition,"run_id":run_id,"simulation_time_s":time_s,
                        "team":agent["team"],"agent_id":agent["agent_id"],"x_m":point[0],"z_m":point[2]})

    if neural_rows:
        path=figure_root/"neural_motor_timeseries.csv"
        with path.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(neural_rows[0]));writer.writeheader();writer.writerows(neural_rows)
        fig,axes=plt.subplots(2,1,figsize=(9,7),sharex=True,constrained_layout=True)
        for condition in sorted({row["condition"] for row in neural_rows}):
            for name in channel_names:
                values=[row for row in neural_rows if row["condition"]==condition and row["signal_type"]=="neural" and row["name"]==name]
                if values:axes[0].plot([r["simulation_time_s"] for r in values],[r["mean_value"] for r in values],label=f"{condition} · {name}",alpha=.8)
            for name in action_names:
                values=[row for row in neural_rows if row["condition"]==condition and row["signal_type"]=="applied_action" and row["name"]==name]
                if values:axes[1].plot([r["simulation_time_s"] for r in values],[r["mean_value"] for r in values],label=f"{condition} · {name}",alpha=.8)
        axes[0].set_ylabel("Mean blue-team DN trace");axes[1].set_ylabel("Mean applied action");axes[1].set_xlabel("Simulation time (s)")
        axes[0].set_title("Neural activity and applied control (descriptive, not causal)")
        for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=7,ncol=2)
        for suffix in ("png","svg","pdf"):fig.savefig(figure_root/f"neural_motor_timeseries.{suffix}",dpi=180 if suffix=="png" else None)
        plt.close(fig)
    if correlation_rows:
        with (figure_root/"neural_motor_correlations.csv").open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(correlation_rows[0]));writer.writeheader();writer.writerows(correlation_rows)
        fig,axes=plt.subplots(1,len(sorted({r["condition"] for r in correlation_rows})),figsize=(6*len(sorted({r["condition"] for r in correlation_rows})),5),squeeze=False,constrained_layout=True)
        for ax,condition in zip(axes[0],sorted({r["condition"] for r in correlation_rows})):
            matrix=np.full((len(channel_names),len(action_names)),np.nan)
            for i,channel in enumerate(channel_names):
                for j,action in enumerate(action_names):
                    vals=[r["pearson_r_descriptive"] for r in correlation_rows if r["condition"]==condition and r["neural_channel"]==channel and r["action"]==action and r["pearson_r_descriptive"] is not None]
                    if vals:matrix[i,j]=float(np.mean(vals))
            image=ax.imshow(matrix,vmin=-1,vmax=1,cmap="coolwarm",aspect="auto")
            ax.set_xticks(range(len(action_names)),action_names,rotation=35,ha="right");ax.set_yticks(range(len(channel_names)),channel_names)
            ax.set_title(f"{condition}: run-level mean r");ax.set_xlabel("Applied action");ax.set_ylabel("MaleCNS trace")
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    if np.isfinite(matrix[i,j]):ax.text(j,i,f"{matrix[i,j]:.2f}",ha="center",va="center",fontsize=8)
        fig.colorbar(image,ax=list(axes[0]),label="Pearson r (descriptive only)")
        for suffix in ("png","svg","pdf"):fig.savefig(figure_root/f"neural_motor_correlations.{suffix}",dpi=180 if suffix=="png" else None)
        plt.close(fig)

    if behavior_rows:
        path=figure_root/"behavior_timeseries.csv"
        with path.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(behavior_rows[0]));writer.writeheader();writer.writerows(behavior_rows)
        fig,axes=plt.subplots(3,1,figsize=(9,8),sharex=True,constrained_layout=True)
        for condition in sorted({row["condition"] for row in behavior_rows}):
            values=[r for r in behavior_rows if r["condition"]==condition]
            axes[0].plot([r["simulation_time_s"] for r in values],[r["blue_mean_speed_m_s"] for r in values],label=condition)
            axes[1].plot([r["simulation_time_s"] for r in values],[r["blue_visible_fraction"] for r in values],label=condition)
            axes[2].plot([r["simulation_time_s"] for r in values],[r["blue_tickets"]-r["red_tickets"] for r in values],label=condition)
        axes[0].set_ylabel("Blue mean speed (m/s)");axes[1].set_ylabel("Blue visible fraction");axes[2].set_ylabel("Ticket difference");axes[2].set_xlabel("Simulation time (s)")
        axes[0].set_title("Behavior time series (per-run descriptive traces)")
        for ax in axes:ax.grid(alpha=.2);ax.legend(fontsize=8)
        for suffix in ("png","svg","pdf"):fig.savefig(figure_root/f"behavior_timeseries.{suffix}",dpi=180 if suffix=="png" else None)
        plt.close(fig)

    if trajectory_rows:
        path=figure_root/"agent_trajectories.csv"
        with path.open("x",newline="",encoding="utf-8") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(trajectory_rows[0]));writer.writeheader();writer.writerows(trajectory_rows)
        fig,ax=plt.subplots(figsize=(8,6),constrained_layout=True)
        for run_id in sorted({row["run_id"] for row in trajectory_rows}):
            for team,color in (("blue","#277da1"),("red","#d1495b")):
                values=[row for row in trajectory_rows if row["run_id"]==run_id and row["team"]==team and int(row["agent_id"])%8==0]
                if values:ax.plot([r["x_m"] for r in values],[r["z_m"] for r in values],color=color,alpha=.65,label=team if run_id==sorted({r["run_id"] for r in trajectory_rows})[0] else None)
        ax.set_xlabel("X (m)");ax.set_ylabel("Z (m)");ax.set_title("Representative agent trajectories by physical side");ax.axis("equal");ax.grid(alpha=.2);ax.legend()
        for suffix in ("png","svg","pdf"):fig.savefig(figure_root/f"agent_trajectories.{suffix}",dpi=180 if suffix=="png" else None)
        plt.close(fig)
