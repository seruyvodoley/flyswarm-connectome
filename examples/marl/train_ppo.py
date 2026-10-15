#!/usr/bin/env python3
import argparse,csv,json
from pathlib import Path
import numpy as np
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy

def train(steps,seed,checkpoint,curve,max_episode_steps=300):
    rng=np.random.default_rng(seed)
    env=FlySwarmParallelEnv(max_steps=max_episode_steps,role_conditioning=True)
    obs_dim=env.observation_space(env.possible_agents[0]).shape[0]
    policy=SharedPPOPolicy(obs_dim=obs_dim,seed=seed)
    seen=0;updates=[]
    while seen<steps:
        obs,_=env.reset(seed=seed+len(updates));trajectories={a:[] for a in env.possible_agents}
        while env.agents and seen<steps:
            actions={};cache={}
            for a,o in obs.items():actions[a],raw,logp,value=policy.act(o,rng);cache[a]=(o,raw,logp,value)
            next_obs,rewards,terms,truncs,_=env.step(actions)
            for a,(o,raw,logp,value) in cache.items():trajectories[a].append((o,raw,logp,value,rewards[a],terms[a] or truncs[a]))
            obs=next_obs;seen+=1
        batch={k:[] for k in ['obs','raw','logp','adv','returns']}
        episode_reward=0.
        for trajectory in trajectories.values():
            future=0.
            for o,raw,logp,value,reward,done in reversed(trajectory):
                future=reward+.99*future*(not done);batch['obs'].append(o);batch['raw'].append(raw);batch['logp'].append(logp);batch['returns'].append(future);batch['adv'].append(future-value);episode_reward+=reward
        loss=policy.update(batch);updates.append({'steps':seen,'mean_agent_return':episode_reward/16,'value_mse':loss})
    policy.save(checkpoint,{"algorithm":"shared PPO/IPPO reference","seed":seed,"backend":"analytical_training","role_conditioned":True,"observation_dim":obs_dim})
    dest=Path(curve);dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=updates[0]);w.writeheader();w.writerows(updates)
    return updates
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--steps',type=int,default=5000);p.add_argument('--seed',type=int,default=7);p.add_argument('--checkpoint',default='policies/marl/shared_ppo.npz');p.add_argument('--curve',default='results/marl/learning_curve.csv');p.add_argument('--max-episode-steps',type=int,default=300);a=p.parse_args()
    print(json.dumps(train(a.steps,a.seed,a.checkpoint,a.curve,a.max_episode_steps)[-1],indent=2))
