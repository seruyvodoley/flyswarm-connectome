"""Bounded end-to-end imitation collection, save/reload and frozen evaluation."""
import argparse,json,os,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run_pair(godot,output,seed,seconds,policy=None,collect=None):
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    args=[sys.executable,'-m','flyswarm.bridge.server','--port',str(port),'--seed',str(seed),'--once']
    if policy:args+=['--policy',str(policy)]
    if collect:args+=['--collect',str(collect)]
    output.mkdir(parents=True,exist_ok=False)
    env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUNBUFFERED':'1'}
    log_path=output/'backend.log'
    with log_path.open('w') as log:
        server=subprocess.Popen(args,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            deadline=time.monotonic()+90
            while 'READY 2 x' not in log_path.read_text():
                if server.poll() is not None:raise RuntimeError(log_path.read_text())
                if time.monotonic()>deadline:raise TimeoutError('MaleCNS load timeout')
                time.sleep(.1)
            with (output/'godot.log').open('w') as game_log:
                subprocess.run([godot,'--headless','--path',str(ROOT/'frontend/godot'),'--','--connect','--port',str(port),'--training','--seed',str(seed),'--seconds',str(seconds),'--quit','--record',str(output)],env=env,stdout=game_log,stderr=subprocess.STDOUT,check=True,timeout=150)
            server.wait(timeout=15)
            if server.returncode:raise RuntimeError(log_path.read_text())
            if 'ERROR' in (output/'godot.log').read_text():raise RuntimeError((output/'godot.log').read_text())
            summary=json.loads((output/'summary.json').read_text())
            if summary['brain_tick_ms'] is None:raise RuntimeError('No neural response')
            return summary
        finally:
            if server.poll() is None:server.terminate();server.wait(timeout=10)

def main():
    p=argparse.ArgumentParser();p.add_argument('--godot',required=True);p.add_argument('--seconds',type=float,default=1)
    p.add_argument('--output',default=str(ROOT/'results/raw/3d'/time.strftime('training-%Y%m%d-%H%M%S')));a=p.parse_args()
    dest=Path(a.output).resolve();dest.mkdir(parents=True,exist_ok=False)
    dataset=dest/'imitation.npz';policy=dest/'shared/policy.npz'
    train=run_pair(a.godot,dest/'train',100,a.seconds,collect=dataset)
    env={**os.environ,'PYTHONPATH':str(ROOT/'src')}
    subprocess.run([sys.executable,'-m','flyswarm.training.fit',str(dataset),str(policy)],check=True,env=env,cwd=ROOT)
    before=policy.read_bytes()
    evaluation=run_pair(a.godot,dest/'eval',200,a.seconds,policy=policy)
    assert before==policy.read_bytes(),'Evaluation changed weights'
    report={'task':'stage 3 turret imitation smoke','train_seed':100,'test_seed':200,'policy':str(policy.relative_to(dest)),'dataset_samples':int(a.seconds/.02)*16,'frozen_evaluation':True,'train_neural_tick_ms':train['brain_tick_ms'],'eval_neural_tick_ms':evaluation['brain_tick_ms'],'eval_realtime_factor':evaluation['realtime_factor'],'limitations':'tiny demonstration, no claim of learning quality/role emergence'}
    (dest/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2));print('ARTIFACTS',dest)
if __name__=='__main__':main()
