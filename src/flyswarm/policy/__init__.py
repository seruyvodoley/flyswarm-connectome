"""Compact frozen-connectome readouts. No historical performance tables as input."""
import json
from pathlib import Path
import numpy as np

FEATURE_MODES=('connectome_only','connectome_plus_proprioception')
def features(trace,proprio,mode):
    if mode not in FEATURE_MODES:raise ValueError(mode)
    x=np.log1p(np.maximum(0,np.asarray(trace,dtype=float)))/5
    if mode=='connectome_plus_proprioception':x=np.concatenate([x,np.asarray(proprio,dtype=float)])
    return x

class Readout:
    def __init__(self,weights,mode='connectome_only',metadata=None):
        self.weights=np.array(weights,dtype=float,copy=True)
        self.mode=mode
        self.metadata=metadata or {}
        expected=6 if mode=='connectome_only' else 12
        if self.weights.shape!=(expected+1,6):raise ValueError('Readout feature/action dimension mismatch')
        self.weights.flags.writeable=False
    def predict(self,x):return np.clip(np.append(x,1)@self.weights,-1,1)
    def save(self,path):
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
        np.savez(p,weights=self.weights,mode=self.mode,metadata=json.dumps(self.metadata))
    @classmethod
    def load(cls,path):
        with np.load(path,allow_pickle=False) as d:return cls(d['weights'],str(d['mode']),json.loads(str(d['metadata'])))
    @classmethod
    def fit(cls,x,y,mode,metadata,ridge=.1):
        x=np.c_[np.asarray(x),np.ones(len(x))]
        w=np.linalg.solve(x.T@x+np.eye(x.shape[1])*ridge,x.T@np.asarray(y))
        return cls(w,mode,metadata)
