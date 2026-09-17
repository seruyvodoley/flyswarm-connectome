"""python -m flyswarm.bridge.server --port 8765 [--collect DATASET.npz]."""
import argparse,hashlib,json,socket,time,os,signal,threading,sys
from pathlib import Path
import numpy as np
from flyswarm.brain import DualBrain
from flyswarm.bridge import read,encode
from flyswarm.policy import Readout,features

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,default=8765);p.add_argument('--seed',type=int,default=204)
    p.add_argument('--policy');p.add_argument('--collect');p.add_argument('--once',action='store_true')
    p.add_argument('--feature-mode',choices=['connectome_only','connectome_plus_proprioception'],default='connectome_only')
    p.add_argument('--status-file');p.add_argument('--parent-pid',type=int)
    p.add_argument('--blue-controller',default='brain');p.add_argument('--red-controller',default='brain')
    p.add_argument('--blue-policy');p.add_argument('--red-policy')
    a=p.parse_args()
    def status(stage,error=None):
        if a.status_file:
            dest=Path(a.status_file);dest.parent.mkdir(parents=True,exist_ok=True)
            tmp=dest.with_suffix('.tmp');tmp.write_text(json.dumps({'stage':stage,'error':error,'pid':os.getpid()}));tmp.replace(dest)
    def watch_parent():
        while True:
            time.sleep(1)
            try:os.kill(a.parent_pid,0)
            except ProcessLookupError:os._exit(0)
    if a.parent_pid:threading.Thread(target=watch_parent,daemon=True).start()
    try:brain=DualBrain(a.seed,status=status)
    except Exception as exc:
        status('ERROR',str(exc));return

    policies={}
    policy_hashes={}
    if a.policy:
        path=Path(a.policy)
        if path.is_dir():policies={f.parent.name:Readout.load(f) for f in path.glob('*/policy.npz')}
        else:policies={'shared':Readout.load(path)}
        files=path.glob('*/policy.npz') if path.is_dir() else [path]
        policy_hashes={f.parent.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if a.collect and a.policy:raise ValueError('Do not collect training data during policy evaluation')
    team_policies={}
    for team in ['blue','red']:
        file=getattr(a,team+'_policy')
        if file:
            try:team_policies[team]=Readout.load(file)
            except Exception as exc:status('ERROR',str(exc));return
    xs=[];ys=[];vehicles=[];seeds=[]
    metadata={'brain_seeds':[a.seed,a.seed+1000],'neuron_count':sum(b.n*b.batch for b in brain.brains),'feature_mode':a.feature_mode,'mode':'imitation' if a.collect else 'evaluation','policy_ids':{key:value.metadata for key,value in policies.items()},'policy_sha256':policy_hashes}
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server.bind(('127.0.0.1',a.port));server.listen(1)
        status('READY')
        print('READY 2 x FlyBrain(batch=8)',json.dumps(metadata),flush=True)
        while True:
            connection,_=server.accept()
            try:
                with connection,connection.makefile('rb') as stream:
                    last=0
                    while (packet:=read(stream)) is not None:
                        if packet['seq']<=last:raise ValueError('Non-monotonic sequence')
                        last=packet['seq'];obs=packet['observations']
                        traces,heard,ms=brain.step(obs,packet['audio'])
                        actions=[]
                        for o,t in zip(obs,traces):
                            team='blue' if o['id']<8 else 'red'
                            policy=team_policies.get(team,policies.get(o['vehicle'],policies.get('shared')))
                            if policies and policy is None:raise ValueError(f"No policy for {o['vehicle']}")
                            mode=policy.mode if policy else a.feature_mode
                            x=features(t,o['proprio'],mode)
                            if a.collect:
                                xs.append(x);ys.append(o['teacher']);vehicles.append(o['vehicle']);seeds.append(a.seed)
                                action=np.array(o['teacher'])
                            elif getattr(a,team+'_controller')=='rule':action=np.array(o['teacher'])
                            elif policy:action=policy.predict(x)
                            else:
                                action=brain.baseline(t)

                                # Explicit locomotion/search auxiliary.
                                #
                                # When no enemy is visible the visual encoder
                                # injects no LC9 pursuit stimulus. Without a
                                # floor the tank can remain indefinitely at
                                # spawn. This auxiliary knows no waypoint,
                                # objective coordinate, enemy coordinate or
                                # vehicle role.
                                if not o['visible']:
                                    action[0]=max(
                                        float(action[0]),
                                        .18
                                    )

                                # Explicit rule-based fire/elevation auxiliary baseline.
                                action[4]=np.clip(o['elevation']*6,-1,1)
                                action[5]=float(o['visible'] and abs(o['bearing'])<.015 and abs(o['elevation'])<.012)
                            if not o['alive']:action=np.zeros(6)
                            actions.append(action.tolist())
                        result=dict(version=1,seq=last,actions=actions,traces=traces.tolist(),heard=heard.tolist(),tick_ms=ms,dt=.02,mode='IMITATION_TEACHER' if a.collect else ('TRAINED_ADAPTER' if policies or team_policies else 'BIOLOGICAL_BASELINE'),metadata=metadata,communication=brain.last_communication)
                        connection.sendall(encode(result))
            except (ConnectionError,ValueError) as e:print(type(e).__name__,str(e),flush=True)
            finally:
                if a.collect and xs:
                    path=Path(a.collect);path.parent.mkdir(parents=True,exist_ok=True)
                    np.savez(path,x=xs,y=ys,vehicle=vehicles,seed=seeds,mode=a.feature_mode,metadata=json.dumps(metadata))
                    print('SAVED',len(xs),'imitation samples',a.collect,flush=True)
            if a.once:break
            brain.reset(a.seed)
if __name__=='__main__':main()
