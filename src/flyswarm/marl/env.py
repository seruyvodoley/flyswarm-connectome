"""PettingZoo API for repeatable, headless FlySwarm practicals.

The interactive Godot battle remains the authoritative high-fidelity runtime.
This bounded analytical backend preserves the same 16 agents, six controls,
simultaneous stepping, domination transitions and ticket/death semantics. It
is explicitly tagged in ``infos`` so its results cannot be mistaken for a
MaleCNS/Godot experiment. MaleCNS features may be supplied by a caller; zeros
mean unavailable and are never fabricated.

Role/country conditioning is an ENGINEERED policy input. It is never injected
into MaleCNS and should be interpreted as a controllable research prior rather
than biological or historical doctrine.
"""
from __future__ import annotations
from functools import lru_cache
import numpy as np
from gymnasium import spaces
from pettingzoo import ParallelEnv
from .roles import DEFAULT_COMPOSITION, ROLE_FEATURE_DIM, role_features, vehicle_profile

AGENTS=tuple([f"blue_{i}" for i in range(8)]+[f"red_{i}" for i in range(8)])
ACTION_NAMES=("throttle","brake","steering","turret","elevation","fire")
DEFAULT_REWARDS={
    "objective_progress":.02,"objective_capture":3.,"objective_neutralization":1.,
    "damage_dealt":.01,"enemy_kill":4.,"own_death":-4.,"ticket_delta":.01,
    "battle_win":10.,"battle_loss":-10.,"role_shaping":.25,
}

class FlySwarmParallelEnv(ParallelEnv):
    metadata={"name":"flyswarm_analytical_v1","render_modes":[]}
    possible_agents=list(AGENTS)
    def __init__(self,max_steps=1500,reward_coefficients=None,dt=.1,vehicle_ids=None,role_conditioning=True):
        self.max_steps=int(max_steps);self.dt=float(dt)
        self.coefficients=DEFAULT_REWARDS|dict(reward_coefficients or {})
        self.vehicle_ids=tuple(vehicle_ids or DEFAULT_COMPOSITION)
        if len(self.vehicle_ids)!=16:raise ValueError("vehicle_ids must contain 16 vehicle ids")
        self.role_conditioning=bool(role_conditioning)
        self.obs_dim=20+(ROLE_FEATURE_DIM if self.role_conditioning else 0)
        self.profiles=[vehicle_profile(v) for v in self.vehicle_ids]
        self._rng=np.random.default_rng();self.agents=[]
    @lru_cache(None)
    def action_space(self,agent):return spaces.Box(-1.,1.,(6,),np.float32)
    @lru_cache(None)
    def observation_space(self,agent):return spaces.Box(-10.,10.,(self.obs_dim,),np.float32)
    def reset(self,seed=None,options=None):
        self._rng=np.random.default_rng(seed);self.agents=list(self.possible_agents);self.steps=0
        self.pos=np.zeros((16,2),float);self.pos[:8]=[-450,-180];self.pos[8:]=[450,180]
        self.pos[:,1]+=np.linspace(-210,210,8).tolist()*2
        self.heading=np.r_[np.full(8,np.pi/2),np.full(8,-np.pi/2)]
        self.speed=np.zeros(16);self.health=np.ones(16);self.reload=np.zeros(16)
        self.tickets=np.array([300.,300.]);self.zones_owner=np.full(3,-1,int);self.zones_progress=np.zeros(3)
        self.zones=np.array([[-240.,0.],[0.,0.],[240.,0.]])
        self.neural=np.zeros((16,6),np.float32);self.last_components=[{} for _ in range(16)]
        return self._observations(),{a:self._info(i) for i,a in enumerate(self.agents)}
    def set_connectome_features(self,features):
        value=np.asarray(features,np.float32)
        if value.shape!=(16,6):raise ValueError("connectome features must be (16, 6)")
        self.neural=np.log1p(np.maximum(0,value))/5
    def step(self,actions):
        if not self.agents:raise RuntimeError("step() after episode end")
        previous_tickets=self.tickets.copy();previous_owner=self.zones_owner.copy();previous_progress=self.zones_progress.copy();previous_health=self.health.copy();previous_pos=self.pos.copy()
        applied=np.zeros((16,6),float)
        for i,a in enumerate(self.possible_agents):
            action=np.clip(np.asarray(actions.get(a,np.zeros(6)),float),-1,1);applied[i]=action
            if self.health[i]<=0:continue
            spec=self.profiles[i]
            self.heading[i]+=action[2]*float(spec["turn_rate_rad_s"])*self.dt
            self.speed[i]+=(action[0]*float(spec["accel_m_s2"])-max(0.,action[1])*8.-self.speed[i]*.28)*self.dt
            self.speed[i]=np.clip(self.speed[i],-float(spec["reverse_m_s"]),float(spec["max_speed_m_s"]))
            self.pos[i]+=np.array([np.cos(self.heading[i]),np.sin(self.heading[i])])*self.speed[i]*self.dt
            self.reload[i]=max(0.,self.reload[i]-self.dt)
            if action[5]>.5 and self.reload[i]<=0:
                targets=np.arange(8,16) if i<8 else np.arange(0,8)
                alive=targets[self.health[targets]>0]
                if len(alive):
                    distance=np.linalg.norm(self.pos[alive]-self.pos[i],axis=1);target=alive[np.argmin(distance)]
                    if distance.min()<float(spec["effective_range_m"]):
                        self.health[target]=max(0.,self.health[target]-float(spec["damage_per_hit"]))
                    self.reload[i]=float(spec["reload_s"])
        self._objectives()
        self.steps+=1
        rewards={};infos={}
        done=bool(self.steps>=self.max_steps or min(self.tickets)<=0 or np.all(self.health[:8]<=0) or np.all(self.health[8:]<=0))
        health_loss=np.maximum(0,previous_health-self.health)
        for i,a in enumerate(self.possible_agents):
            team=0 if i<8 else 1;enemy=1-team
            damage=float(health_loss[8:].sum() if team==0 else health_loss[:8].sum())
            deaths=float(previous_health[i]>0 and self.health[i]<=0)
            kills=float(np.sum((previous_health[8:]>0)&(self.health[8:]<=0)) if team==0 else np.sum((previous_health[:8]>0)&(self.health[:8]<=0)))
            captures=float(np.sum((previous_owner!=team)&(self.zones_owner==team)))
            neutralized=float(np.sum((previous_owner==enemy)&(self.zones_owner==-1)))
            delta_progress=self.zones_progress-previous_progress
            progress=float(np.maximum(0,delta_progress).sum() if team==0 else np.maximum(0,-delta_progress).sum())/100.
            c={
                "objective_progress":progress,"objective_capture":captures,"objective_neutralization":neutralized,
                "damage_dealt":damage,"enemy_kill":kills,"own_death":deaths,
                "ticket_delta":float((previous_tickets[enemy]-self.tickets[enemy])-(previous_tickets[team]-self.tickets[team])),
                "battle_win":float(done and self.tickets[team]>self.tickets[enemy]),
                "battle_loss":float(done and self.tickets[team]<self.tickets[enemy]),
                "role_shaping":self._role_shaping(i,previous_pos,applied[i]),
            }
            self.last_components[i]=c;rewards[a]=sum(self.coefficients[k]*v for k,v in c.items());infos[a]=self._info(i)
        terminations={a:done and self.steps<self.max_steps for a in self.possible_agents}
        truncations={a:done and self.steps>=self.max_steps for a in self.possible_agents}
        observations=self._observations()
        if done:self.agents=[]
        return observations,rewards,terminations,truncations,infos
    def _objectives(self):
        for z,center in enumerate(self.zones):
            inside=np.linalg.norm(self.pos-center,axis=1)<65
            blue=np.any(inside[:8]&(self.health[:8]>0));red=np.any(inside[8:]&(self.health[8:]>0))
            if blue==red:continue
            team=0 if blue else 1;direction=1 if team==0 else -1
            if self.zones_owner[z] not in (-1,team):
                self.zones_progress[z]-=np.sign(self.zones_progress[z])*20*self.dt
                if abs(self.zones_progress[z])<1e-6:self.zones_owner[z]=-1
            else:
                self.zones_progress[z]=np.clip(self.zones_progress[z]+direction*20*self.dt,-100,100)
                if abs(self.zones_progress[z])>=100:self.zones_owner[z]=team
        for owner in self.zones_owner:
            if owner>=0:self.tickets[1-owner]=max(0.,self.tickets[1-owner]-.2*self.dt)
    def _role_shaping(self,i,previous_pos,action):
        """Small role prior; team success remains the dominant reward signal."""
        profile=self.profiles[i];zone=i%3;center=self.zones[zone]
        before=float(np.linalg.norm(previous_pos[i]-center));after=float(np.linalg.norm(self.pos[i]-center))
        scale=max(1.,float(profile["max_speed_m_s"])*self.dt)
        approach=float(np.clip((before-after)/scale,-1.,1.));inside=float(after<65.)
        targets=np.arange(8,16) if i<8 else np.arange(0,8);alive=targets[self.health[targets]>0]
        nearest=float(np.min(np.linalg.norm(self.pos[alive]-self.pos[i],axis=1))) if len(alive) else 9999.
        role=str(profile["vehicle_class"]);objective=float(profile["objective_bias"]);aggression=float(profile["aggression"])
        if role=="medium":
            value=objective*(.70*approach+.30*inside)
        elif role=="heavy":
            contact=float(nearest<float(profile["effective_range_m"])*.85)
            value=objective*(.45*approach+.40*inside)+.15*aggression*contact
        else:
            stand=max(1.,float(profile["standoff_m"]));band=float(np.exp(-abs(nearest-stand)/max(90.,stand*.65)))
            too_close=max(0.,(stand*.45-nearest)/max(1.,stand*.45))
            fire=float(action[5]>.5 and nearest<=float(profile["effective_range_m"]))
            value=.55*band+.25*fire-.45*too_close+.10*objective*approach
        # Engineered country prior: Germany favours stand-off use; USSR favours
        # objective pressure. These are experiment knobs, not historical claims.
        if profile["nation"]=="germany":
            value+=.08*float(nearest>=float(profile["standoff_m"]) and nearest<=float(profile["effective_range_m"]))
        else:
            value+=.08*aggression*max(0.,approach)
        return float(np.clip(value,-1.,1.))
    def _observations(self):
        out={}
        for i,a in enumerate(self.possible_agents):
            zone=i%3;delta=self.zones[zone]-self.pos[i];bearing=np.arctan2(delta[1],delta[0])-self.heading[i]
            owner=self.zones_owner[zone];spec=self.profiles[i]
            proprio=np.array([
                self.speed[i]/max(1.,float(spec["max_speed_m_s"])),
                self.reload[i]/max(1.,float(spec["reload_s"])),self.health[i],float(self.health[i]>0)
            ])
            task=np.array([np.sin(bearing),np.cos(bearing),np.linalg.norm(delta)/700,owner,self.zones_progress[zone]/100,self.tickets[i//8]/300,self.tickets[1-i//8]/300,zone/2,1.])
            base=np.concatenate([self.neural[i],proprio,task,[1.]]).astype(np.float32)
            out[a]=np.concatenate([base,role_features(self.vehicle_ids[i])]).astype(np.float32) if self.role_conditioning else base
        return out
    def _info(self,i):
        p=self.profiles[i]
        return {
            "backend":"analytical_training","authoritative_runtime":"Godot","reward_components":dict(self.last_components[i]),
            "tickets":self.tickets.tolist(),"alive":bool(self.health[i]>0),"action_order":ACTION_NAMES,
            "vehicle":self.vehicle_ids[i],"vehicle_class":p["vehicle_class"],"tactical_role":p["tactical_role"],
            "nation":p["nation"],"role_conditioning":self.role_conditioning,
        }
