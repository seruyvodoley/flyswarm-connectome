"""Small NumPy shared-policy PPO reference; intended for teaching and smoke runs."""
from __future__ import annotations
from pathlib import Path
import numpy as np

class SharedPPOPolicy:
    def __init__(self,obs_dim=20,act_dim=6,seed=0):
        rng=np.random.default_rng(seed);self.weights=rng.normal(0,.03,(obs_dim+1,act_dim));self.value=np.zeros(obs_dim+1);self.log_std=np.full(act_dim,-.7);self.metadata={"method":"shared_ppo","backend":"analytical_training"}
    def act(self,obs,rng=None,deterministic=False):
        x=np.append(np.asarray(obs,float),1.);mean=x@self.weights
        raw=mean if deterministic else mean+(rng or np.random.default_rng()).normal(size=mean.shape)*np.exp(self.log_std)
        action=np.tanh(raw);logp=self._logp(raw,mean)
        return action.astype(np.float32),raw,float(logp),float(x@self.value)
    def _logp(self,raw,mean):
        std=np.exp(self.log_std);return np.sum(-.5*((raw-mean)/std)**2-self.log_std-.5*np.log(2*np.pi))
    def update(self,batch,lr=3e-4,clip=.2,epochs=4):
        obs=np.asarray(batch["obs"]);raw=np.asarray(batch["raw"]);old=np.asarray(batch["logp"]);adv=np.asarray(batch["adv"]);returns=np.asarray(batch["returns"])
        x=np.c_[obs,np.ones(len(obs))];adv=(adv-adv.mean())/(adv.std()+1e-8)
        for _ in range(epochs):
            mean=x@self.weights;std=np.exp(self.log_std);logp=np.sum(-.5*((raw-mean)/std)**2-self.log_std-.5*np.log(2*np.pi),axis=1)
            ratio=np.exp(np.clip(logp-old,-10,10));active=((adv>=0)&(ratio<1+clip))|((adv<0)&(ratio>1-clip))
            score=(raw-mean)/(std**2);grad=x.T@(score*(adv*ratio*active)[:,None])/len(x)
            self.weights+=lr*np.clip(grad,-5,5)
            error=returns-x@self.value;self.value+=lr*(x.T@error)/len(x)
        return float(np.mean((returns-x@self.value)**2))
    def save(self,path,metadata=None):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);np.savez(p,weights=self.weights,value=self.value,log_std=self.log_std,metadata=str(metadata or {}))
    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as d:
            obj=cls(d["weights"].shape[0]-1,d["weights"].shape[1]);obj.weights=d["weights"];obj.value=d["value"];obj.log_std=d["log_std"];return obj
