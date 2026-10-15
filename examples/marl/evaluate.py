#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy

def evaluate(checkpoint,episodes,seed,max_steps,deterministic=True):
    policy=SharedPPOPolicy.load(checkpoint)
    obs_dim=policy.weights.shape[0]-1
    role_conditioning=obs_dim>20
    runs=[]
    for ep in range(episodes):
        env=FlySwarmParallelEnv(max_steps=max_steps,role_conditioning=role_conditioning)
        if env.observation_space(env.possible_agents[0]).shape[0]!=obs_dim:
            raise ValueError(f"Checkpoint expects {obs_dim} observations, environment provides {env.obs_dim}")
        obs,_=env.reset(seed=seed+ep);total={a:0. for a in env.possible_agents}
        while env.agents:
            actions={a:policy.act(o,deterministic=deterministic)[0] for a,o in obs.items()};obs,rewards,_,_,infos=env.step(actions)
            for a,r in rewards.items():total[a]+=r
        runs.append({'episode':ep,'blue_reward':sum(v for a,v in total.items() if a.startswith('blue'))/8,'red_reward':sum(v for a,v in total.items() if a.startswith('red'))/8,'tickets':next(iter(infos.values()))['tickets']})
    return {'backend':'analytical_training','deterministic':deterministic,'role_conditioning':role_conditioning,'observation_dim':obs_dim,'episodes':runs}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('checkpoint');p.add_argument('--episodes',type=int,default=3);p.add_argument('--seed',type=int,default=100);p.add_argument('--max-steps',type=int,default=300);p.add_argument('--stochastic',action='store_true');p.add_argument('--output',default='results/marl/evaluation.json');a=p.parse_args()
    report=evaluate(a.checkpoint,a.episodes,a.seed,a.max_steps,not a.stochastic);dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
