#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy

def evaluate(checkpoint,episodes,seed,max_steps,deterministic=True):
    policy=SharedPPOPolicy.load(checkpoint);runs=[]
    for ep in range(episodes):
        env=FlySwarmParallelEnv(max_steps=max_steps);obs,_=env.reset(seed=seed+ep);total={a:0. for a in env.possible_agents}
        while env.agents:
            actions={a:policy.act(o,deterministic=deterministic)[0] for a,o in obs.items()};obs,rewards,_,_,infos=env.step(actions)
            for a,r in rewards.items():total[a]+=r
        runs.append({'episode':ep,'blue_reward':sum(v for a,v in total.items() if a.startswith('blue'))/8,'red_reward':sum(v for a,v in total.items() if a.startswith('red'))/8,'tickets':next(iter(infos.values()))['tickets']})
    return {'backend':'analytical_training','deterministic':deterministic,'episodes':runs}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--episodes',type=int,default=3);p.add_argument('--seed',type=int,default=100);p.add_argument('--max-steps',type=int,default=300);p.add_argument('--stochastic',action='store_true');p.add_argument('--output',default='results/marl/evaluation.json');a=p.parse_args()
    report=evaluate(a.checkpoint,a.episodes,a.seed,a.max_steps,not a.stochastic);dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
