#!/usr/bin/env python3
"""Replay logged stateless MaleCNS command adapters on fixed battle snapshots.

This estimates conditional final-command effects at recorded world states. It
does not advance Godot physics or claim counterfactual trajectories.
"""
from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(os.environ.get("FLYSWARM_CAUSAL_OUT",ROOT/"research/studies/malecns_communication/experiments/causal-context-20261029"))
ZONE_RADIUS=45.0
# Godot's Vector3/float intermediates are single precision; the saved command
# vectors are decimal JSON, so controller replay is validated at 1e-6.
TOL=1e-6


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def clamp(x,lo,hi): return max(lo,min(hi,x))


def wrap_pi(x): return (x+math.pi)%(2*math.pi)-math.pi


def backend_action(decoded,obs):
    command=np.asarray(decoded,dtype=float).copy()
    if not obs.get("visible",False): command[0]=max(float(command[0]),.18)
    command[4]=clamp(float(obs.get("elevation",0.0))*6.0,-1.0,1.0)
    command[5]=float(bool(obs.get("visible",False)) and abs(float(obs.get("bearing",0.0)))<.015 and abs(float(obs.get("elevation",0.0)))<.012)
    if not obs.get("alive",True): command[:]=0.0
    return command


def objective_destination(agent,zones):
    if not zones: return None
    agent_id=int(agent["agent_id"]); team=0 if agent.get("team")=="blue" else 1
    preferred=agent_id%len(zones); preferred_zone=zones[preferred]
    if int(preferred_zone.get("owner",-1))!=team or bool(preferred_zone.get("contested",False)):
        return np.asarray(preferred_zone["position"],dtype=float)
    best=-1; best_distance=float("inf")
    position=np.asarray(agent["position"],dtype=float)
    for offset in range(len(zones)):
        index=(preferred+offset)%len(zones); zone=zones[index]
        if int(zone.get("owner",-1))==team and not bool(zone.get("contested",False)):
            continue
        distance=float(np.sum((position-np.asarray(zone["position"],dtype=float))**2))
        if distance<best_distance: best_distance=distance;best=index
    return np.asarray(zones[best if best>=0 else preferred]["position"],dtype=float)


def objective_action(command,agent,zones,ray_blocked=False):
    command=np.asarray(command,dtype=float).copy()
    if not agent.get("alive",True): return np.zeros(6,dtype=float)
    if not zones: return command
    destination=objective_destination(agent,zones)
    position=np.asarray(agent["position"],dtype=float)
    delta=destination-position;delta[1]=0.0
    distance=float(np.linalg.norm(delta))
    if distance<.001:return command
    desired=math.atan2(float(delta[0]),float(delta[2]))
    error=wrap_pi(desired-float(agent.get("hull_yaw_rad",0.0)))
    inside=distance<ZONE_RADIUS*.62
    if not inside:
        steer=clamp(error*1.55,-1.0,1.0)
        throttle=.82
        if abs(error)>.60: throttle=.46
        if abs(error)>1.15: throttle=.22
        if distance<ZONE_RADIUS*1.45: throttle=min(throttle,.34)
        weight=.78
        if agent.get("visible",False):
            weight=.30;throttle*=.72
        command[2]=(1-weight)*float(command[2])+weight*steer
        command[0]=max(float(command[0]),throttle)
    elif agent.get("visible",False):
        command[0]=clamp(float(command[0]),0.0,.28)
    else:
        command[0]=0.0;command[2]=0.0
    if not inside and ray_blocked:
        command[0]=-.15
        command[2]=1.0 if int(agent["agent_id"])%2==0 else -1.0
    return command


def infer_ray_blocked(decoder,obs,agent,zones,logged_final):
    baseline=objective_action(backend_action(decoder,obs),agent,zones,False)
    if np.max(np.abs(baseline-np.asarray(logged_final,dtype=float)))<=TOL:
        return False
    blocked=objective_action(backend_action(decoder,obs),agent,zones,True)
    if np.max(np.abs(blocked-np.asarray(logged_final,dtype=float)))<=TOL:
        return True
    raise ValueError("logged final action does not match reconstructed objective controller")


def write_csv(path,rows):
    if not rows:return
    with Path(path).open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def bootstrap_ci(values,seed=20261029,draws=20000):
    values=np.asarray(values,dtype=float)
    if not len(values): return [None,None]
    rng=np.random.default_rng(seed)
    means=rng.choice(values,size=(draws,len(values)),replace=True).mean(axis=1)
    return [float(np.quantile(means,.025)),float(np.quantile(means,.975))]


def main():
    plan=json.loads((OUT/"selection_and_reproducibility.json").read_text(encoding="utf-8"))
    baseline_checks=[]; event_out=[]
    for block in plan["seed_blocks"]:
        source=ROOT/block["source_path"]
        neural=read_jsonl(source)
        games=read_jsonl(source.with_name("game_steps.jsonl"))
        frame_by_tick={}; state_by_physics={}
        for row in games:
            state_by_physics[int(row.get("physics_step_id",-1))]=row
            tick=int(row.get("neural_step_id",-1))
            if tick>0 and row.get("new_neural_response",False): frame_by_tick[tick]=row
        for event in block["events"]:
            payload=json.loads((OUT/"raw"/f"seed-{block['seed']}-event-{event['event_index']}.json").read_text(encoding="utf-8"))
            receiver=int(event["receiver"])
            for horizon in payload["horizons"]:
                tick=int(event["tick"])+int(horizon["horizon_ms"])//20
                nrow=neural[tick-1]
                applied_frame=frame_by_tick.get(tick)
                state_step=int(nrow.get("physics_step_id",-1))-1
                state_frame=state_by_physics.get(state_step)
                if applied_frame is None or state_frame is None:
                    raise ValueError(f"no aligned Godot state/action frame for seed={block['seed']} tick={tick}")
                obs=nrow["observations"][receiver]
                agent=state_frame["agents"][receiver]
                decoder=np.asarray(nrow["control_layers"][receiver]["decoder_action"],dtype=float)
                base_logged=np.asarray(applied_frame["agents"][receiver]["final_action"],dtype=float)
                try:
                    ray=infer_ray_blocked(decoder,obs,agent,state_frame["zones"],base_logged)
                except ValueError as exc:
                    raise ValueError(f"{exc}; seed={block['seed']} tick={tick} receiver={receiver}") from exc
                replayed=objective_action(backend_action(decoder,obs),agent,state_frame["zones"],ray)
                err=float(np.max(np.abs(replayed-base_logged)))
                baseline_checks.append({"seed":block["seed"],"event_index":event["event_index"],
                                        "tick":tick,"horizon_ms":horizon["horizon_ms"],
                                        "ray_blocked_inferred":ray,"max_abs_final_action_error":err})
                # command JSON fields are deltas; add them to the baseline decoder.
                # Both counterfactual arms share recorded observations, objective
                # ownership, and static obstruction at this tick.
                mute=objective_action(backend_action(decoder+np.asarray(json.loads(horizon["decoder_command_delta"]),dtype=float),obs),agent,state_frame["zones"],ray)
                control=objective_action(backend_action(decoder+np.asarray(json.loads(horizon["control_command_delta"]),dtype=float),obs),agent,state_frame["zones"],ray)
                event_out.append({"seed":block["seed"],"event_index":event["event_index"],"tick":tick,
                                  "receiver":receiver,"horizon_ms":horizon["horizon_ms"],
                                  "ray_blocked_inferred":ray,
                                  "final_action_l2_mute":float(np.linalg.norm(mute-base_logged)),
                                  "final_action_l2_control":float(np.linalg.norm(control-base_logged)),
                                  "final_action_delta_mute":json.dumps((mute-base_logged).tolist()),
                                  "final_action_delta_control":json.dumps((control-base_logged).tolist())})
    write_csv(OUT/"final_action_baseline_validation.csv",baseline_checks)
    write_csv(OUT/"final_action_counterfactual_metrics.csv",event_out)
    errors=[r["max_abs_final_action_error"] for r in baseline_checks]
    if max(errors,default=0.0)>TOL: raise ValueError(f"baseline controller reconstruction failed: max error {max(errors)}")
    seed_metrics=[]
    for seed in sorted({r["seed"] for r in event_out}):
        rows=[r for r in event_out if r["seed"]==seed and r["horizon_ms"]==1000]
        seed_metrics.append({"seed":seed,
          "mute_final_action_l2_mean":float(np.mean([r["final_action_l2_mute"] for r in rows])),
          "control_final_action_l2_mean":float(np.mean([r["final_action_l2_control"] for r in rows])),
          "control_minus_mute_l2":float(np.mean([r["final_action_l2_control"]-r["final_action_l2_mute"] for r in rows])),
          "practical_mute_fraction":float(np.mean([r["final_action_l2_mute"]>=.05 for r in rows]))})
    paired=[r["control_minus_mute_l2"] for r in seed_metrics]
    practical=[r["practical_mute_fraction"] for r in seed_metrics]
    stats={"schema":"flyswarm.causal.context.final_action.v1","independent_unit":"seed",
      "practical_threshold_l2":.05,"n_seed":len(seed_metrics),
      "mute_final_action_l2":{"mean":float(np.mean([r["mute_final_action_l2_mean"] for r in seed_metrics])),
        "seed_cluster_bootstrap_95ci":bootstrap_ci([r["mute_final_action_l2_mean"] for r in seed_metrics]),"n_seed":len(seed_metrics)},
      "control_final_action_l2":{"mean":float(np.mean([r["control_final_action_l2_mean"] for r in seed_metrics])),
        "seed_cluster_bootstrap_95ci":bootstrap_ci([r["control_final_action_l2_mean"] for r in seed_metrics],20261030),"n_seed":len(seed_metrics)},
      "control_minus_mute_l2":{"mean":float(np.mean(paired)),
        "seed_cluster_bootstrap_95ci":bootstrap_ci(paired,20261031),"n_seed":len(seed_metrics)},
      "mute_practical_fraction":{"mean":float(np.mean(practical)),
        "seed_cluster_bootstrap_95ci":bootstrap_ci(practical,20261101),"n_seed":len(seed_metrics)},
      "baseline_validation":{"snapshots":len(baseline_checks),"max_abs_final_action_error":max(errors),
        "tolerance":TOL,"ray_blocked_snapshots":sum(r["ray_blocked_inferred"] for r in baseline_checks)},
      "physical_trajectory_measured":False}
    (OUT/"final_action_statistics.json").write_text(json.dumps(stats,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    write_csv(OUT/"final_action_seed_metrics.csv",seed_metrics)
    make_final_action_figure(event_out)
    print(json.dumps({"validated_snapshots":len(baseline_checks),"max_abs_final_action_error":max(errors),
                      "ray_blocked_snapshots":sum(r["ray_blocked_inferred"] for r in baseline_checks),
                      "counterfactual_rows":len(event_out),"statistics":stats},indent=2))


def make_final_action_figure(rows):
    figdir=OUT/"figures";figdir.mkdir(exist_ok=True)
    final_rows=[r for r in rows if r["horizon_ms"]==1000]
    with (OUT/"intervention_event_metrics.csv").open(newline="",encoding="utf-8") as f:
        decoder_rows=[r for r in csv.DictReader(f) if int(r["horizon_ms"])==1000]
    for r in decoder_rows:r["seed"]=int(r["seed"])
    seeds=sorted({r["seed"] for r in final_rows})
    fig,axes=plt.subplots(1,2,figsize=(9.2,4.2),constrained_layout=True)
    for ax,keys,title in [
        (axes[0],("decoder_l2_mute","decoder_l2_control"),"Декодер"),
        (axes[1],("final_action_l2_mute","final_action_l2_control"),"Итоговая команда после адаптеров")]:
        panel_rows=decoder_rows if keys[0].startswith("decoder_") else final_rows
        for ix,seed in enumerate(seeds):
            group=[r for r in panel_rows if r["seed"]==seed]
            if not group:continue
            mute=float(np.mean([float(r[keys[0]]) for r in group]));control=float(np.mean([float(r[keys[1]]) for r in group]))
            ax.plot([0,1],[mute,control],color="#8a958e",alpha=.65,lw=1)
            ax.scatter([0,1],[mute,control],color=["#b07b37","#527a68"],s=27,zorder=3)
        ax.set_xticks([0,1],["Mute","Shuffle"])
        ax.set_title(title);ax.set_ylabel("L2 от baseline, нормированные команды");ax.grid(axis="y",alpha=.25)
    fig.suptitle("Вмешательство и matched control: 1000 мс; линии соединяют средние по seed")
    for ext in ("png","svg","pdf"):
        fig.savefig(figdir/f"fig4_final_action_control.{ext}",dpi=180 if ext=="png" else None)
    plt.close(fig)


if __name__=="__main__":main()
