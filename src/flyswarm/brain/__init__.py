"""Two independent real MaleCNS objects. Importing this module loads no brain."""
import time
import numpy as np
from flyswarm.sensory import visual,audio_frame

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
        self.last_communication={
            'sample':-1,
            'song_out':[0.0]*16,
            'heard_total':[0.0]*16,
            'events':[],
            'delay_steps':1,
        }
    def step(self,observations,audio):
        start=time.perf_counter()
        alive=np.array([o['alive'] for o in observations])
        previous_song=self.song.copy()
        heard,contribution,distance=audio_frame(
            previous_song,
            [o['position'] for o in observations],
            alive,
            audio,
        )
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

        # UI/replay telemetry only.  Five samples/second keeps the socket and
        # Godot UI light while preserving the actual 50 Hz neural simulation.
        if self.ticks%10==0:
            events=[]
            receivers,senders=np.nonzero(contribution>=.01)
            for receiver,sender in zip(receivers.tolist(),senders.tolist()):
                events.append({
                    'sender':int(sender),
                    'receiver':int(receiver),
                    'raw':float(previous_song[sender]),
                    'received':float(contribution[receiver,sender]),
                    'distance_m':float(distance[receiver,sender]),
                })
            events.sort(key=lambda event:event['received'],reverse=True)
            self.last_communication={
                'sample':int(self.ticks//10),
                'song_out':previous_song.astype(float).tolist(),
                'heard_total':heard.astype(float).tolist(),
                'events':events[:12],
                'delay_steps':1,
            }

        return self.trace.copy(),heard,(time.perf_counter()-start)*1000
    def baseline(self,trace):
        """Map measured DN rates into normalized vehicle controls.

        The previous 3D decoder divided pursuit/turn signals by very large
        constants and could leave vehicles effectively stationary.

        Scaling is based on the earlier successful FlyTank 0.3 pursuit
        decoder, adapted from direct speed/deg-s commands to [-1, 1] vehicle
        controls.  The connectome itself remains frozen.
        """
        p9l,p9r,a02l,a02r,escape,wing=trace

        pursuit_drive=max(0.0,float(p9l+p9r)-2.0)

        # Full drive at roughly 12 Hz combined DNp09 activity.
        throttle=np.clip(
            pursuit_drive/10.0,
            0.0,
            1.0
        )

        # FlyTank 0.3 used 5 deg/s per Hz DNp09 difference.
        # Here we map that response into a normalized steering control.
        steer=np.clip(
            float(p9r-p9l)/6.0,
            -1.0,
            1.0
        )

        # DNa02 was also much more strongly coupled in the validated
        # tracking experiment than in the old /40 3D mapping.
        turret=np.clip(
            float(a02r-a02l)/8.0,
            -1.0,
            1.0
        )

        # Escape-related activity suppresses pursuit but cannot reverse the
        # vehicle by itself.
        escape_suppression=np.clip(
            float(escape)/80.0,
            0.0,
            .70
        )

        throttle*=1.0-escape_suppression

        return np.array([
            throttle,
            0.0,
            steer,
            turret,
            0.0,
            0.0
        ],dtype=float)
