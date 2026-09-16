"""Supervised application jobs. Own children, report actual progress, cancel cleanly."""
import hashlib,json,os,signal,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
class Cancelled(Exception):pass
class Job:
 def __init__(self,config):
  self.c=config;self.out=Path(config['output']);self.children=[];self.logs=[];self.started=time.monotonic();self.state={};self.stopping=False
  self.env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'PYTHONUNBUFFERED':'1'}
  signal.signal(signal.SIGTERM,lambda *_:setattr(self,'stopping',True))
  signal.signal(signal.SIGINT,lambda *_:setattr(self,'stopping',True))
 def status(self,**fields):
  self.state.update(fields);self.state['wall_time']=time.monotonic()-self.started
  p=self.out/'progress.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(self.state,indent=2));tmp.replace(p)
 def check(self):
  if self.stopping or (self.out/'cancel').exists():raise Cancelled()
  try:os.kill(int(self.c['parent_pid']),0)
  except ProcessLookupError:raise Cancelled()
 def spawn(self,args,log):
  handle=log.open('w');self.logs.append(handle)
  proc=subprocess.Popen(args,cwd=ROOT,env=self.env,stdout=handle,stderr=subprocess.STDOUT);self.children.append(proc);self.status(owned_pids=[p.pid for p in self.children]);return proc
 def cleanup(self):
  for child in self.children:
   if child.poll() is None:child.terminate()
  for child in self.children:
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait()
  self.children=[]
  for log in self.logs:log.close()
  self.logs=[]
 def run(self,condition,seed,index,total,extra=(),policy=None,collect=None,controllers=None):
  self.check();dest=self.out/f'{index:03d}-{condition}-{seed}';dest.mkdir()
  controllers=controllers or [self.c['blue_controller'],self.c['red_controller']]
  neural=collect is not None or policy is not None or any(c!='rule' for c in controllers)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  self.status(state='running',condition=condition,seed=seed,run=index,total=total,completed=index-1,message='Preparing run',sim_time=0)
  try:
   if neural:
    backend_status=dest/'backend-status.json'
    args=[sys.executable,'-m','flyswarm.bridge.server','--port',str(port),'--seed',str(seed),'--once','--status-file',str(backend_status),'--parent-pid',str(os.getpid()),'--blue-controller',controllers[0],'--red-controller',controllers[1]]
    if collect:args+=['--collect',str(collect)]
    if policy:args+=['--policy',str(policy)]
    else:
     for team in ['blue','red']:
      if self.c[team+'_controller']=='adapter':args+=['--'+team+'-policy',self.c[team+'_policy']]
    server=self.spawn(args,dest/'backend.log');deadline=time.monotonic()+120
    while True:
     self.check()
     state=json.loads(backend_status.read_text()) if backend_status.exists() else {}
     self.status(message=state.get('stage','Starting backend'))
     if state.get('stage')=='READY':break
     if state.get('error'):raise RuntimeError(state['error'])
     if server.poll() is not None:raise RuntimeError('Backend failed; see backend.log in the run folder')
     if time.monotonic()>deadline:raise TimeoutError('Backend startup exceeded 120 seconds')
     time.sleep(.15)
   args=[self.c['godot']]
   if self.c['render_mode']!='visual':args+=['--headless']
   args+=['--path',str(ROOT/'frontend/godot'),'--','--legacy-battle','--seed',str(self.c['map_seed']),'--battle-seed',str(seed),'--seconds',str(self.c['seconds']),'--quit','--record',str(dest),'--audio',self.c['audio_mode']]
   if not self.c['record']:args+=['--no-replay']
   if self.c['physics_mode']=='normalized':args+=['--normalized']
   if self.c['swap']:args+=['--swap']
   if self.c['vehicle_composition']!='mixed_1944':args+=['--mirror',self.c['vehicle_composition']]
   if neural:args+=['--connect','--port',str(port)]
   # A condition overrides a baseline option; do not leave duplicate CLI flags.
   extra=list(extra)
   for token in extra:
    if token.startswith('--') and token in args:
     at=args.index(token);args.pop(at)
     if at<len(args) and not args[at].startswith('--'):args.pop(at)
   args+=extra
   game=self.spawn(args,dest/'godot.log');deadline=time.monotonic()+max(120,float(self.c['seconds'])*30)
   while game.poll() is None:
    self.check()
    live=dest/'live.json'
    try:state=json.loads(live.read_text()) if live.exists() else {}
    except json.JSONDecodeError:state={}
    self.status(sim_time=state.get('sim_time',0),message='Simulation running')
    if time.monotonic()>deadline:raise TimeoutError('Simulation exceeded bounded run timeout')
    time.sleep(.1)
   if game.returncode:raise RuntimeError('Godot run failed; see godot.log')
   log=(dest/'godot.log').read_text()
   if 'SCRIPT ERROR' in log or 'ERROR:' in log:raise RuntimeError('Godot reported an error; see godot.log')
   if neural:
    server.wait(timeout=15)
    if server.returncode:raise RuntimeError('Backend failed during run')
   result=json.loads((dest/'summary.json').read_text())
   if neural and not result.get('backend_metadata'):raise RuntimeError('Missing actual neural response')
   self.status(completed=index,sim_time=result['time'])
   return result
  finally:self.cleanup()
 def research(self):
  c=self.c;kind=c['research_experiment'];policy=c['blue_policy'] or c['red_policy'] or None
  conditions={
   'communication':[(mode,['--audio',mode],None) for mode in ['no_audio','team_audio','all_audio']],
   'embodiment':[('historical',[],None),('normalized',['--normalized'],None)],
   'mirror':[(c['training_vehicle'],['--mirror',c['training_vehicle']],None)],
   'side_swap':[('normal',[],None),('swapped',['--swap'],None)],
   'policy':[('policy',[],policy)],
   'transfer':[('source',['--mirror',c['training_vehicle']],policy),('target',['--mirror',c['target_vehicle']],policy)],
   'trained_baseline':[('baseline',[],None),('trained',[],policy)]}
  if kind in ['policy','transfer','trained_baseline'] and not policy:raise ValueError('Select an existing policy for this experiment')
  if kind=='communication' and c['blue_controller']==c['red_controller']=='rule':raise ValueError('Communication comparison requires MaleCNS; Rule AI does not use neural audio')
  # Conditions override baseline rather than accumulating contradictory flags.
  if kind=='embodiment':c['physics_mode']='historical'
  if kind=='side_swap':c['swap']=False
  if kind in ['mirror','transfer']:c['vehicle_composition']='mixed_1944'
  total=len(conditions[kind])*int(c['seed_count']);rows=[]
  for seed in range(int(c['battle_seed']),int(c['battle_seed'])+int(c['seed_count'])):
   for condition,extra,head in conditions[kind]:
    controllers=['brain','brain'] if kind=='trained_baseline' else None
    result=self.run(condition,seed,len(rows)+1,total,extra,policy=head,controllers=controllers)
    rows.append({'condition':condition,'seed':seed,'result':result})
    (self.out/'results.json').write_text(json.dumps(rows,indent=2))
  self.status(state='complete',completed=total,message='Measured results saved. No scientific interpretation applied.')
 def training(self):
  import numpy as np
  from flyswarm.policy import Readout
  c=self.c;count=int(c['episodes']);seeds=list(range(int(c['battle_seed']),int(c['battle_seed'])+count));valid=int(c['validation_seed'])
  if valid in seeds:raise ValueError('Validation seed overlaps the training episode seeds')
  extra=['--training','--mirror',c['training_vehicle']]
  if c.get('evaluate'):
   policy=Path(c['blue_policy']);Readout.load(policy);before=hashlib.sha256(policy.read_bytes()).hexdigest()
   result=self.run('evaluation',valid,1,1,extra,policy=policy)
  else:
   xs=[];ys=[];feature_mode=None
   for index,seed in enumerate(seeds,1):
    dataset=self.out/f'episode-{index}.npz'
    # Shared policy collects the existing mixed training range; vehicle head uses mirror.
    train_extra=['--training'] if c['adapter']=='shared' else extra
    self.run('imitation',seed,index,count+1,train_extra,collect=dataset)
    with np.load(dataset,allow_pickle=False) as data:
     xs.append(data['x']);ys.append(data['y']);feature_mode=str(data['mode'])
   x=np.concatenate(xs);y=np.concatenate(ys)
   model=Readout.fit(x,y,feature_mode,{'vehicle':c['training_vehicle'] if c['adapter']=='vehicle' else 'shared','train_seeds':seeds,'validation_seed':valid,'samples':len(x),'stage':3,'method':'ridge imitation'})
   policy=self.out/'models'/('shared' if c['adapter']=='shared' else c['training_vehicle'])/'policy.npz';model.save(policy);model=Readout.load(policy)
   mse=float(np.mean((np.array([model.predict(row) for row in x])-y)**2))
   self.status(checkpoint=str(policy),message=f'Training imitation MSE {mse:.6f}; validation pending')
   before=hashlib.sha256(policy.read_bytes()).hexdigest()
   result=self.run('frozen-evaluation',valid,count+1,count+1,extra,policy=policy)
   (self.out/'fit.json').write_text(json.dumps({'training_imitation_mse':mse,'samples':len(x),'train_seeds':seeds,'validation_seed':valid},indent=2))
  assert before==hashlib.sha256(policy.read_bytes()).hexdigest(),'Evaluation modified policy bytes'
  (self.out/'evaluation.json').write_text(json.dumps(result,indent=2))
  self.status(state='complete',checkpoint=str(policy),message='Readout saved/reloaded; frozen evaluation complete. Reward: N/A; no validated combat-success metric.')
 def execute(self):
  try:
   if self.c['mode']=='training':self.training()
   else:self.research()
  except Cancelled:self.status(state='cancelled',message='Cancelled; owned child processes stopped.')
  except Exception as exc:self.status(state='error',message=str(exc))
  finally:self.cleanup()
if __name__=='__main__':
 config=json.loads(Path(sys.argv[1]).read_text());Job(config).execute()
