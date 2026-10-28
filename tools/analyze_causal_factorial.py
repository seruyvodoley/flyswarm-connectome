#!/usr/bin/env python3
"""Analyze E4 factorial pilot at independent seed level; no confirmatory claims."""
from __future__ import annotations
import csv, json, math, statistics
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ARM_LABELS = {
    "BLUE_OFF_RED_OFF": "BLUE выкл. / RED выкл.",
    "BLUE_OFF_RED_ON": "BLUE выкл. / RED вкл.",
    "BLUE_ON_RED_OFF": "BLUE вкл. / RED выкл.",
    "BLUE_ON_RED_ON": "BLUE вкл. / RED вкл.",
}
METRIC_LABELS = {
    "terminal_ticket_balance": "Разница конечных очков (BLUE − RED), доля",
    "objective_zone_presence_fraction": "Δ присутствия в целевых зонах",
    "mean_blue_team_cohesion_m": "BLUE: расстояние между союзниками, м",
    "mean_red_team_cohesion_m": "RED: расстояние между союзниками, м",
    "mean_blue_heading_alignment": "BLUE: согласованность курса",
    "mean_red_heading_alignment": "RED: согласованность курса",
    "blue_alive_fraction": "BLUE: доля живых агентов",
    "red_alive_fraction": "RED: доля живых агентов",
    "mean_blue_delivered_audio": "BLUE: доставленный сигнал",
    "mean_red_delivered_audio": "RED: доставленный сигнал",
    "mean_blue_applied_action_ch_0": "BLUE: действие, канал 0",
    "mean_red_applied_action_ch_0": "RED: действие, канал 0",
    "mean_blue_applied_action_ch_2": "BLUE: действие, канал 2",
    "mean_red_applied_action_ch_2": "RED: действие, канал 2",
    "mean_blue_applied_action_ch_3": "BLUE: действие, канал 3",
    "mean_red_applied_action_ch_3": "RED: действие, канал 3",
    "mean_blue_applied_action_ch_5": "BLUE: действие, канал 5",
    "mean_red_applied_action_ch_5": "RED: действие, канал 5",
}


def plot_seed_level(experiment: Path, seed_rows: list[dict], metrics: list[str]) -> None:
    """Create article-ready plots from seed-level rows without rereading raw JSONL."""
    plot_root=experiment/"figures";plot_root.mkdir(exist_ok=True)
    labels=sorted({row["arm"] for row in seed_rows})
    x_by_arm={arm:index for index,arm in enumerate(labels)}
    for metric in metrics:
        fig,ax=plt.subplots(figsize=(10,5))
        for arm in labels:
            values=[row.get(metric) for row in seed_rows if row["arm"]==arm and row.get(metric) is not None]
            x=x_by_arm[arm]
            # Small deterministic x offsets keep tied seed observations visible.
            offsets=np.linspace(-.11,.11,len(values)) if len(values)>1 else [0.0]
            if values:
                ax.scatter([x+offset for offset in offsets],values,color="#527a68",s=32,alpha=.75,zorder=3)
                ax.plot([x],[np.mean(values)],marker="D",markersize=7,color="#bd8b49",zorder=4)
        ax.set_xticks(list(x_by_arm.values()),[ARM_LABELS.get(arm,arm) for arm in labels])
        ax.set_title("E4: факторный пилот коммуникации")
        ax.set_ylabel(METRIC_LABELS.get(metric,metric.replace("_"," ")))
        ax.set_xlabel("Условие: канал BLUE / RED\nТочки — независимые seed; ромб — среднее")
        if metric in {"objective_zone_presence_fraction","terminal_ticket_balance"}:
            ax.axhline(0,color="#68716b",linewidth=.8,alpha=.7,zorder=1)
        ax.tick_params(axis="x",rotation=8,labelsize=9);ax.grid(axis="y",alpha=.25)
        fig.subplots_adjust(left=.17,right=.98,top=.90,bottom=.25)
        for ext in ("png","svg","pdf"):
            fig.savefig(plot_root/f"e4_{metric}.{ext}",dpi=180 if ext=="png" else None)
        plt.close(fig)


def plot_existing(experiment: Path) -> None:
    path=Path(experiment)/"processed/e4_seed_level.csv"
    with path.open(newline="",encoding="utf-8") as stream:
        seed_rows=[]
        for row in csv.DictReader(stream):
            seed_rows.append({key:(None if value=="" else (value if key in {"arm","side_assignments"} else float(value)))
                              for key,value in row.items()})
    metrics=[key for key in seed_rows[0] if key not in {"arm","seed","side_assignments","duration_s","game_frames"}]
    plot_seed_level(Path(experiment),seed_rows,metrics)


def bootstrap_mean_ci(values, seed: int, draws: int = 10000) -> dict:
    """Seed-cluster percentile interval; seeds, not frames, are resampled."""
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return {"mean": None, "ci95": [None, None], "n_seed_blocks": 0}
    rng = np.random.default_rng(seed)
    means = rng.choice(values, size=(draws, values.size), replace=True).mean(axis=1)
    return {"mean": float(values.mean()),
            "ci95": [float(np.quantile(means, .025)), float(np.quantile(means, .975))],
            "n_seed_blocks": int(values.size)}


def read_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def analyze_run(run_dir: Path) -> dict:
    manifest=json.loads((run_dir/"manifest.json").read_text(encoding="utf-8"))
    summary=json.loads((run_dir/"summary.json").read_text(encoding="utf-8"))
    frames=read_jsonl(run_dir/"game_steps.jsonl")
    neural_rows=read_jsonl(run_dir/"neural_steps.jsonl")
    duration=float(summary.get("time",manifest["duration_s"]))
    n_zones=max((len(row.get("zones",[])) for row in frames),default=0)
    metrics={"terminal_ticket_balance": (float(summary["tickets"][0])-float(summary["tickets"][1]))/600.0,
             "duration_s":duration,"game_frames":len(frames),"objective_zone_presence_fraction":None,
             "mean_blue_team_cohesion_m":None,"mean_red_team_cohesion_m":None,
             "mean_blue_heading_alignment":None,"mean_red_heading_alignment":None,
             "blue_target_concentration":None,"red_target_concentration":None,
             "blue_alive_fraction":None,"red_alive_fraction":None,
             "blue_mean_speed_m_s":None,"red_mean_speed_m_s":None}
    # Sum per-agent zone-occupancy time, normalized by agent x zone opportunity.
    teams={"blue":[],"red":[]}
    cohesion={"blue":[],"red":[]}; alignment={"blue":[],"red":[]}
    alive={"blue":[],"red":[]}; speed={"blue":[],"red":[]}; concentration={"blue":[],"red":[]}
    for row in frames:
        agents=row.get("agents",[])
        for team in ("blue","red"):
            group=[a for a in agents if a.get("team")==team]
            living=[a for a in group if a.get("alive")]
            for a in group:
                teams[team].append(float(a.get("metrics",{}).get("objective_presence_s",0.0)))
            alive[team].append(len(living)/8.0)
            speed[team].append(float(np.mean([a.get("speed_m_s",0.0) for a in living])) if living else 0.0)
            positions=np.asarray([a.get("position",[0,0,0]) for a in living],dtype=float)
            if len(positions)>=2:
                d=[]
                for i in range(len(positions)):
                    for j in range(i+1,len(positions)):
                        d.append(float(np.linalg.norm(positions[i,[0,2]]-positions[j,[0,2]])))
                cohesion[team].append(float(np.mean(d)))
                yaws=np.asarray([a.get("hull_yaw_rad",0.0) for a in living],dtype=float)
                pair_cos=[math.cos(float(yaws[i]-yaws[j])) for i in range(len(yaws)) for j in range(i+1,len(yaws))]
                alignment[team].append(float(np.mean(pair_cos)))
            targets=[int(a.get("target_agent_id",-1)) for a in living if int(a.get("target_agent_id",-1))>=0]
            if targets:
                counts=np.unique(targets,return_counts=True)[1]/len(targets)
                concentration[team].append(float(np.sum(counts**2)))
    denom=8.0*duration*max(n_zones,1)
    for team in ("blue","red"):
        metrics[f"{team}_objective_presence_fraction"]=sum(teams[team])/denom if denom else None
        metrics[f"mean_{team}_team_cohesion_m"]=float(np.mean(cohesion[team])) if cohesion[team] else None
        metrics[f"mean_{team}_heading_alignment"]=float(np.mean(alignment[team])) if alignment[team] else None
        metrics[f"{team}_target_concentration"]=float(np.mean(concentration[team])) if concentration[team] else None
        metrics[f"{team}_alive_fraction"]=float(np.mean(alive[team])) if alive[team] else None
        metrics[f"{team}_mean_speed_m_s"]=float(np.mean(speed[team])) if speed[team] else None
    metrics["objective_zone_presence_fraction"]=metrics["blue_objective_presence_fraction"]-metrics["red_objective_presence_fraction"]
    # Descriptive mediators on the synchronized neural -> decoder -> applied-action
    # chain. These time/agent samples are collapsed to one run value and then to one
    # seed-block value; they are never treated as independent observations.
    mediator_values={}
    for team in ("blue","red"):
        mediator_values[f"mean_{team}_delivered_audio"]=[]
        for stage in ("neural_trace","decoder_action","applied_action"):
            for channel in range(6): mediator_values[f"mean_{team}_{stage}_ch_{channel}"]=[]
    if len(neural_rows)!=len(frames):
        raise ValueError(f"neural/game frame count mismatch in {run_dir}")
    for neural,game in zip(neural_rows,frames):
        if int(neural.get("neural_step_id",-1))!=int(game.get("neural_step_id",-2)):
            raise ValueError(f"neural/game step ID mismatch in {run_dir}")
        teams_by_id={int(a["agent_id"]):a.get("team") for a in game.get("agents",[])}
        layers=neural.get("control_layers",[])
        traces=neural.get("effective_traces",[])
        heard=neural.get("heard",[])
        applied=neural.get("applied_actions",[])
        for agent_id,team in teams_by_id.items():
            if team not in ("blue","red") or agent_id>=len(layers) or agent_id>=len(traces) or agent_id>=len(applied) or agent_id>=len(heard):
                continue
            layer=layers[agent_id]
            mediator_values[f"mean_{team}_delivered_audio"].append(float(heard[agent_id]))
            for key,vector in (("neural_trace",traces[agent_id]),
                                ("decoder_action",layer.get("decoder_action",[])),
                                ("applied_action",applied[agent_id])):
                if len(vector)==6:
                    for channel,value in enumerate(vector): mediator_values[f"mean_{team}_{key}_ch_{channel}"].append(float(value))
    for key,values in mediator_values.items(): metrics[key]=float(np.mean(values)) if values else None
    return {"arm":manifest["condition"],"seed":int(manifest["seed"]),"side_swap":bool(manifest["side_swap"]),
            "run_id":manifest["run_id"],"duration_s":duration,**metrics}


def analyze(experiment: Path):
    experiment=Path(experiment)
    manifests=sorted((experiment/"raw/e4").glob("*/manifest.json"))
    collection_validation_path = experiment / "validation/collection_validation.json"
    accepted_ids = None
    if collection_validation_path.is_file():
        collection = json.loads(collection_validation_path.read_text(encoding="utf-8"))
        if not collection.get("all_required_cells_valid"):
            raise ValueError("collection-level validation did not accept every required E4 cell")
        accepted_ids = set(collection.get("valid_run_ids_by_cell", {}).values())
        if len(accepted_ids) != int(collection.get("expected_runs", -1)):
            raise ValueError("collection-level validation has an incomplete or duplicate valid run list")
    rows=[]
    for path in manifests:
        run=path.parent
        manifest=json.loads(path.read_text(encoding="utf-8"))
        if accepted_ids is not None and manifest.get("run_id") not in accepted_ids:
            continue
        validation_path = run / "validation.json"
        if not validation_path.is_file():
            raise ValueError(f"accepted E4 run is missing validation.json: {run}")
        validation=json.loads(validation_path.read_text(encoding="utf-8"))
        if validation.get("valid"):
            rows.append(analyze_run(run))
        elif accepted_ids is not None:
            raise ValueError(f"collection accepted a run that failed run-level validation: {run}")
    if not rows:
        raise ValueError("no integrity-valid E4 runs")
    labels=sorted({r["arm"] for r in rows})
    if len(labels)!=4:
        raise ValueError("analysis requires all four factorial arms")
    fields=["arm","seed","side_swap","run_id"]+sorted(set().union(*(set(r) for r in rows))-{"arm","seed","side_swap","run_id"})
    with (experiment/"processed/e4_run_metrics.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    grouped={}
    for row in rows:grouped.setdefault((row["arm"],row["seed"]),[]).append(row)
    seed_rows=[]
    numeric=[key for key in fields if key not in {"arm","seed","side_swap","run_id","game_frames"}]
    for (arm,seed),items in sorted(grouped.items()):
        if len(items)!=2 or {x["side_swap"] for x in items}!={False,True}:continue
        seed_rows.append({"arm":arm,"seed":seed,"side_assignments":2,
                          **{key:float(np.mean([x[key] for x in items if x[key] is not None])) if all(x[key] is not None for x in items) else None for key in numeric}})
    with (experiment/"processed/e4_seed_level.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["arm","seed","side_assignments"]+numeric);writer.writeheader();writer.writerows(seed_rows)
    assignments={}
    for arm in labels:
        # Arm names encode the frozen treatment mapping; derive mapping from archived per-run configs.
        run=next((json.loads(p.read_text()) for p in manifests if json.loads(p.read_text()).get("condition")==arm),None)
        causal=run.get("causal_communication") if run else None
        enabled=causal.get("enabled_teams") if causal else None
        if not (isinstance(enabled,list) and len(enabled)==2):raise ValueError(f"missing enabled_teams for {arm}")
        assignments[arm]=tuple(bool(v) for v in enabled)
    all_metrics=[key for key in numeric if key not in {"duration_s","game_frames"}]
    metrics=["terminal_ticket_balance","objective_zone_presence_fraction","mean_blue_team_cohesion_m","mean_red_team_cohesion_m",
             "mean_blue_heading_alignment","mean_red_heading_alignment","blue_alive_fraction","red_alive_fraction",
             "mean_blue_delivered_audio","mean_red_delivered_audio",
             "mean_blue_applied_action_ch_0","mean_red_applied_action_ch_0",
             "mean_blue_applied_action_ch_2","mean_red_applied_action_ch_2",
             "mean_blue_applied_action_ch_3","mean_red_applied_action_ch_3",
             "mean_blue_applied_action_ch_5","mean_red_applied_action_ch_5"]
    summaries={}; effects={}
    for metric in metrics:
        table={}
        for arm in labels:
            vals=[r[metric] for r in seed_rows if r["arm"]==arm and r.get(metric) is not None]
            table[arm]={"n_seed_blocks":len(vals),"mean":float(np.mean(vals)) if vals else None,
                        "sd":float(np.std(vals,ddof=1)) if len(vals)>1 else None,"seed_values":vals}
        summaries[metric]=table
        by_seed={}
        for row in seed_rows:by_seed.setdefault(int(row["seed"]),{})[assignments[row["arm"]]]=row.get(metric)
        contrasts={"blue_main_effect":[],"red_main_effect":[],"interaction":[]}
        for seed,levels in sorted(by_seed.items()):
            if set(levels)!={(True,True),(False,True),(True,False),(False,False)} or any(levels[k] is None for k in levels):continue
            y11,y01,y10,y00=levels[(True,True)],levels[(False,True)],levels[(True,False)],levels[(False,False)]
            contrasts["blue_main_effect"].append({"seed":seed,"difference":((y11+y10)-(y01+y00))/2})
            contrasts["red_main_effect"].append({"seed":seed,"difference":((y11+y01)-(y10+y00))/2})
            contrasts["interaction"].append({"seed":seed,"difference":y11-y01-y10+y00})
        effects[metric]=contrasts
    effect_summaries = {}
    for metric, contrasts in effects.items():
        effect_summaries[metric] = {}
        for contrast_name, seed_differences in contrasts.items():
            values = [item["difference"] for item in seed_differences]
            estimate = bootstrap_mean_ci(values, seed=1944 + sum(map(ord, metric + contrast_name)))
            sd = float(np.std(values, ddof=1)) if len(values) > 1 else None
            estimate["sd_between_seeds"] = sd
            estimate["standardized_mean"] = (estimate["mean"] / sd if sd not in (None, 0.0) else None)
            effect_summaries[metric][contrast_name] = estimate
    result={"schema":"flyswarm.causal.e4.factorial.analysis.v1","independent_unit":"battle seed",
            "n_seed_blocks":len({r["seed"] for r in seed_rows}),"confirmatory":False,
            "side_swaps_averaged_within_seed":True,"arms":{k:list(v) for k,v in assignments.items()},
            "metric_definitions":{"terminal_ticket_balance":"(BLUE terminal tickets - RED terminal tickets)/600",
                "objective_zone_presence_fraction":"sum of per-agent objective_presence_s divided by 8 agents x episode duration x number of zones; BLUE minus RED",
                "team_cohesion_m":"mean pairwise horizontal distance between living teammates per frame, averaged over frames",
                "heading_alignment":"mean cos(pairwise hull yaw difference) among living teammates per frame; descriptive orientation proxy",
                "target_concentration":"Herfindahl index of valid target IDs per team per frame; descriptive targeting concentration"},
            "metrics":summaries,"all_seed_level_measurements":all_metrics,
            "seed_level_contrasts":effects,"factorial_effect_summary":effect_summaries,
            "limitations":[f"Exploratory pilot with {len({r['seed'] for r in seed_rows})} independent seeds; percentile bootstrap intervals are descriptive and do not replace a preregistered confirmatory analysis.",
                "Randomized factorial arms are not exact paired closed-loop counterfactual trajectories.",
                "Objective presence and heading/cohesion metrics are behavioral proxies, not direct proof of coordination mechanism.",
                "Neural, decoder, and applied-action time series are summarized within run/seed to avoid pseudoreplication; their contrasts are exploratory mediators."]}
    (experiment/"processed/e4_statistics.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    plot_seed_level(experiment,seed_rows,metrics)
    return result

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument("experiment",type=Path)
    parser.add_argument("--plots-only",action="store_true",help="Regenerate plots from existing seed-level CSV")
    args=parser.parse_args()
    if args.plots_only:
        plot_existing(args.experiment)
    else:
        print(json.dumps(analyze(args.experiment),ensure_ascii=False,indent=2))
