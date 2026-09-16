"""Two independent real MaleCNS objects. Importing this module loads no brain."""
import time
import numpy as np
from flyswarm.sensory import visual,audio_signal

WING=['DLMn a, b','DLMn c-f','DVMn 1a-c','DVMn 2a, b','DVMn 3a, b','MNwm35','MNwm36','b1 MN','b2 MN','b3 MN','hg1 MN','hg2 MN','hg3 MN','hg4 MN','i1 MN','i2 MN','iii1 MN','iii3 MN','ps1 MN','tp1 MN','tp2 MN','tpn MN']

class DualBrain:
    def __init__(self,seed=204,status=None):
        from flybrain import FlyBrain
        from flybrain.data import has_data
        if not has_data():raise RuntimeError('MaleCNS dataset missing; configure flybrain data separately')
        if status:status('Loading BLUE MaleCNS · FlyBrain(batch=8)')
        self.blue=FlyBrain(device='cpu',batch=8,seed=seed)
        if status:status('Loading RED MaleCNS · FlyBrain(batch=8)')
        self.red=FlyBrain(device='cpu',batch=8,seed=seed+1000)
        assert self.blue is not self.red
        assert not np.shares_memory(self.blue.weights,self.red.weights)
        assert self.blue.dt==self.red.dt==.02
        self.brains=[self.blue,self.red]
        self.groups=[]
        self.seed=seed
        for b in self.brains:
            g={}
            for label,cell in [('lc9','LC9'),('lc10','LC10a')]:
                for side in ['L','R']:g[label+'_'+side.lower()]=b.cells([cell],side=side)
            g['loom']=b.cells(['LC4','LPLC2'])
            g['ear']=b.cells(sorted({str(c) for c in b.cell_type if str(c).startswith(('JO-A','JO-B'))}))
            g['wing']=b.cells(WING)
            g['outputs']=[b.cells(['DNp09'],side='L'),b.cells(['DNp09'],side='R'),b.cells(['DNa02'],side='L'),b.cells(['DNa02'],side='R'),b.cells(['DNp01']),g['wing']]
            assert len(g['wing']) and len(g['ear'])
            self.groups.append(g)
        if status:status("Warming up two independent brains")
        self.reset(seed)
    def reset(self,seed):
        self.seed=seed
        for i,b in enumerate(self.brains):
            b.reset(seed+i*1000)
            for _ in range(25):b.step()
        self.song=np.zeros(16)
        self.trace=np.zeros((16,6))
        self.ticks=0
    def step(self,observations,audio):
        start=time.perf_counter()
        alive=np.array([o['alive'] for o in observations])
        heard=audio_signal(self.song,[o['position'] for o in observations],alive,audio)
        stimulus=visual(observations)
        self.song[:]=0
        for team,(b,g) in enumerate(zip(self.brains,self.groups)):
            span=slice(team*8,(team+1)*8)
            inject=[(g[k],v[span]) for k,v in stimulus.items()]
            inject.append((g['ear'],heard[span]))
            fired=b.step(inject=inject)
            for local,spikes in enumerate(fired):
                index=team*8+local
                counts=np.array([np.count_nonzero(np.isin(spikes,ids)) for ids in g['outputs']])
                self.trace[index]=.9*self.trace[index]+.1*counts/b.dt
                self.song[index]=counts[-1] if alive[index] else 0
        self.ticks+=1
        return self.trace.copy(),heard,(time.perf_counter()-start)*1000
    def baseline(self,trace):
        # Natural lateral and pursuit decoders; no hidden role or ballistics teacher.
        p9l,p9r,a02l,a02r,escape,wing=trace
        return np.clip([(p9l+p9r-escape*.2)/80,0,(p9r-p9l)/40,(a02r-a02l)/40,0,0],-1,1)
