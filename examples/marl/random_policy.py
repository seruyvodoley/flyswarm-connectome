#!/usr/bin/env python3
import argparse,json
from pathlib import Path
import numpy as np
from flyswarm.marl import FlySwarmParallelEnv

def run(episodes,seed,max_steps):
    rows=[]
    for episode in range(episodes):
        env=FlySwarmParallelEnv(max_steps=max_steps);obs,_=env.reset(seed=seed+episode);total={a:0. for a in env.possible_agents};steps=0;captures=0.;kills=0.;deaths=0.
        while env.agents:
            actions={a:env.action_space(a).sample() for a in env.agents};obs,rewards,_,_,infos=env.step(actions);steps+=1
            for a,r in rewards.items():total[a]+=r
            captures+=infos['blue_0']['reward_components'].get('objective_capture',0)+infos['red_0']['reward_components'].get('objective_capture',0)
            kills+=infos['blue_0']['reward_components'].get('enemy_kill',0)+infos['red_0']['reward_components'].get('enemy_kill',0)
            deaths+=sum(info['reward_components'].get('own_death',0) for info in infos.values())
        tickets=next(iter(infos.values()))["tickets"]
        rows.append({"episode":episode,"episode_length":steps,"blue_reward":sum(total[a] for a in total if a.startswith('blue'))/8,"red_reward":sum(total[a] for a in total if a.startswith('red'))/8,"captures":captures,"kills":kills,"deaths":deaths,"tickets":tickets,"winner":"blue" if tickets[0]>tickets[1] else ("red" if tickets[1]>tickets[0] else "draw")})
    return {"backend":"analytical_training","episodes":episodes,"mean_team_reward":float(np.mean([value for r in rows for value in [r['blue_reward'],r['red_reward']]])),"runs":rows}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--episodes',type=int,default=3);p.add_argument('--seed',type=int,default=7);p.add_argument('--max-steps',type=int,default=1500);p.add_argument('--output',default='results/marl/random_summary.json');a=p.parse_args()
    report=run(a.episodes,a.seed,a.max_steps);dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
