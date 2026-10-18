"""python -m flyswarm.bridge.server --port 8765 [--collect DATASET.npz]."""
import argparse,hashlib,json,socket,time,os,signal,threading,sys,platform,importlib.metadata,subprocess
from pathlib import Path
import numpy as np
from flyswarm.brain import DualBrain
from flyswarm.brain.demo import DemoBrain
from flyswarm.bridge import read,encode
from flyswarm.policy import Readout,features
from flyswarm.marl.policy import SharedPPOPolicy
from flyswarm.marl.roles import ROLE_FEATURE_DIM,role_features

class CombatPPOPolicy:
    """Versioned external controller exported by MaleCNS Combat Training."""
    def __init__(self,path,metadata):
        from stable_baselines3 import PPO
        from flyswarm.training.combat import SCHEMA,NEURAL_CHANNELS,GAME_FEATURES
        if metadata.get('schema')!=SCHEMA:raise ValueError('Unsupported combat policy feature schema')
        expected=list(NEURAL_CHANNELS)+list(GAME_FEATURES)
        if metadata.get('features')!=expected:raise ValueError('Combat policy feature layout mismatch')
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        expected_digest=metadata.get('checkpoint_sha256',metadata.get('sha256'))
        if expected_digest!=digest:raise ValueError('Combat policy checksum mismatch')
        self.model=PPO.load(str(path),device='cpu')
        self.metadata={'schema':SCHEMA,'algorithm':'Stable-Baselines3 PPO','male_cns_required':bool(metadata.get('male_cns_required',metadata.get('training_stage')=='malecns'))}
    def act(self,observation):
        action,_=self.model.predict(np.asarray(observation,dtype=np.float32),deterministic=True)
        return np.asarray(action,dtype=float),None

class NonNeuralAdapter:
    """Frozen linear adapter whose schema forbids neural features."""
    FEATURE_SCHEMA='game_proprioception_v1'
    def __init__(self,path):
        with np.load(path,allow_pickle=False) as data:
            self.weights=np.asarray(data['weights'],dtype=float)
            self.metadata=json.loads(str(data['metadata']))
        if self.metadata.get('feature_schema')!=self.FEATURE_SCHEMA or self.weights.shape!=(23,6):
            raise ValueError('Non-neural checkpoint must use 22 game/proprioception features and a 23x6 readout')
        if self.metadata.get('training_seeds') is None or not self.metadata.get('training_samples'):
            raise ValueError('Non-neural checkpoint is missing training provenance')
        self.weights.flags.writeable=False
    @staticmethod
    def inputs(observation):
        proprio=np.asarray(observation.get('proprio',[]),dtype=float)
        task=np.asarray(observation.get('rl_task',[]),dtype=float)
        if proprio.shape!=(6,) or task.shape!=(16,):raise ValueError('Non-neural input schema mismatch')
        return np.concatenate([proprio,task])
    def predict(self,values):
        x=np.asarray(values,dtype=float)
        if x.shape!=(22,):raise ValueError('Non-neural policy input must contain 22 non-neural features')
        return np.clip(np.append(x,1.)@self.weights,-1.,1.)

def combat_features(trace,observation):
    from flyswarm.training.combat import NEURAL_CHANNELS
    neural=np.log1p(np.maximum(0,np.asarray(trace,dtype=float)))/5
    proprio=np.asarray(observation.get('proprio',[0.]*6),dtype=float)
    rl=np.asarray(observation.get('rl_task',[0.]*14),dtype=float)
    turret=float(observation.get('turret_angle_rad',float(proprio[3])*np.pi))
    target_bearing=float(observation.get('bearing',0.0))+turret
    turret_error=float(observation.get('bearing',0.0))
    game=np.asarray([
        float(proprio[0]),min(float(observation.get('target_distance_m',0.0))/500.0,2.0),
        np.sin(target_bearing),np.cos(target_bearing),np.sin(target_bearing),np.cos(target_bearing),
        np.sin(turret_error),np.cos(turret_error),float(observation.get('gun_angle_rad',proprio[4]))/.5,
        float(proprio[2]),float(rl[2]) if rl.size>2 else 1.0,
        float(observation.get('target_health_observed',1.0)),float(bool(observation.get('visible',False))),
        0.0,0.0,0.0,
    ],dtype=float)
    return np.concatenate([neural,game])

def load_policy(path):
    """Load either the ridge readout or any supported shared PPO adapter."""
    path=Path(path)
    if path.suffix.lower()=='.zip':
        metadata_path=path.parent/'metadata.json'
        if not metadata_path.exists():metadata_path=path.with_suffix('.json')
        if not metadata_path.exists():raise ValueError('Combat PPO metadata.json sidecar is missing')
        return CombatPPOPolicy(path,json.loads(metadata_path.read_text(encoding='utf-8')))
    with np.load(path,allow_pickle=False) as data:
        if "value" in data and data["weights"].ndim==2 and data["weights"].shape[1]==6:
            return SharedPPOPolicy.load(path)
    return Readout.load(path)

def ppo_features(policy,trace,observation):
    """Build current inputs and retain compatibility with 20/28-value checkpoints."""
    neural=np.log1p(np.maximum(0,np.asarray(trace,dtype=float)))/5
    task=np.asarray(observation.get('rl_task',[0.]*14),dtype=float)
    legacy=np.concatenate([neural,task[:14]])
    current=np.concatenate([neural,task[:16]])
    expected=int(policy.weights.shape[0]-1)
    if expected==current.size:return current
    if expected==legacy.size:return legacy
    conditioned=np.concatenate([current,role_features(str(observation['vehicle']))])
    if expected==conditioned.size:return conditioned
    legacy_conditioned=np.concatenate([legacy,role_features(str(observation['vehicle']))])
    if expected==legacy_conditioned.size:return legacy_conditioned
    raise ValueError(f"PPO observation size mismatch: checkpoint expects {expected}, runtime provides {current.size} current or {legacy.size} legacy features, with role-conditioned variants")

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,default=8765);p.add_argument('--seed',type=int,default=204)
    p.add_argument('--policy');p.add_argument('--collect');p.add_argument('--once',action='store_true')
    p.add_argument('--feature-mode',choices=['connectome_only','connectome_plus_proprioception'],default='connectome_only')
    p.add_argument('--status-file');p.add_argument('--parent-pid',type=int)
    p.add_argument('--blue-controller',default='brain');p.add_argument('--red-controller',default='brain')
    p.add_argument('--blue-policy');p.add_argument('--red-policy')
    p.add_argument('--demo',action='store_true',help='Run one real MaleCNS batch=1 opponent for the isolated 1v1 demo')
    p.add_argument('--check-data',action='store_true',help='Validate an existing MaleCNS dataset directory and exit')
    p.add_argument('--data-dir',type=Path,help='Dataset folder containing brain.npz and weights.npz')
    p.add_argument('--condition',choices=['MALECNS_REAL','MALECNS_ABLATED','MALECNS_SHUFFLED','NON_NEURAL_TRAINED','RULE_BASED'],default='MALECNS_REAL')
    p.add_argument('--ablate-channels',default='DNp09_L,DNp09_R,DNa02_L,DNa02_R,DNp01')
    p.add_argument('--research-log',type=Path)
    p.add_argument('--experiment-id',default='')
    p.add_argument('--run-id',default='')
    p.add_argument('--non-neural-policy',type=Path)
    p.add_argument('--collect-nonneural',type=Path)
    a=p.parse_args()
    if a.check_data:
        from flybrain.data import FILES,has_data
        data_dir=a.data_dir or Path(os.environ.get('FLY_DATA',Path.home()/'fly-data'))
        if not has_data(data_dir):
            print(json.dumps({'ready':False,'path':str(data_dir),'error':'Required files brain.npz and weights.npz were not found'}))
            return 1
        for name,expected in FILES.items():
            digest=hashlib.sha256()
            with (data_dir/name).open('rb') as source:
                for block in iter(lambda:source.read(1<<20),b''):digest.update(block)
            actual=digest.hexdigest()
            if actual!=expected:
                print(json.dumps({'ready':False,'path':str(data_dir),'error':f'{name} checksum does not match the FlyBrain release'}))
                return 1
        print(json.dumps({'ready':True,'path':str(data_dir),'files':list(FILES)}))
        return 0
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
    try:brain=DemoBrain(a.seed,status=status) if a.demo else DualBrain(a.seed,status=status)
    except Exception as exc:
        status('ERROR',str(exc));return 1

    policies={}
    policy_hashes={}
    if a.policy:
        path=Path(a.policy)
        if path.is_dir():policies={f.parent.name:load_policy(f) for f in path.glob('*/policy.npz')}
        else:policies={'shared':load_policy(path)}
        files=path.glob('*/policy.npz') if path.is_dir() else [path]
        policy_hashes={f.parent.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    if a.collect and a.policy:raise ValueError('Do not collect training data during policy evaluation')
    team_policies={}
    for team in ['blue','red']:
        file=getattr(a,team+'_policy')
        if file:
            try:team_policies[team]=load_policy(file)
            except Exception as exc:status('ERROR',str(exc));return
    non_neural_policy=None
    if a.condition=='NON_NEURAL_TRAINED':
        if not a.non_neural_policy:
            print('NON_NEURAL_TRAINED requires a separately trained non-neural checkpoint',file=sys.stderr);return 2
        try:non_neural_policy=NonNeuralAdapter(a.non_neural_policy)
        except Exception as exc:status('ERROR',str(exc));return 2
        if a.seed in set(non_neural_policy.metadata.get('training_seeds',[])) | set(non_neural_policy.metadata.get('validation_seeds',[])):
            print('Evaluation seed overlaps non-neural training/validation data',file=sys.stderr);return 2
    xs=[];ys=[];vehicles=[];seeds=[]
    shared_brain_arrays=[name for name,value in vars(brain.brains[0]).items()
                         if len(brain.brains)>1 and isinstance(value,np.ndarray)
                         and isinstance(getattr(brain.brains[1],name,None),np.ndarray)
                         and np.shares_memory(value,getattr(brain.brains[1],name))]
    metadata={'brain_seeds':[a.seed] if a.demo else [a.seed,a.seed+1000],'neuron_count':sum(b.n*b.batch for b in brain.brains),'feature_mode':a.feature_mode,'mode':'imitation' if a.collect else 'evaluation','runtime':'single_agent_demo' if a.demo else 'dual_8v8','controllers':{'blue':a.blue_controller,'red':a.red_controller},'policy_ids':{key:value.metadata for key,value in policies.items()},'policy_sha256':policy_hashes,'team_policy_ids':{key:value.metadata for key,value in team_policies.items()},'team_policy_sha256':{team:hashlib.sha256(Path(getattr(a,team+'_policy')).read_bytes()).hexdigest() for team in team_policies}}
    dataset_path=Path(os.environ.get('FLY_DATA',Path.home()/'fly-data'))
    from flybrain.data import FILES
    dataset_hashes={}
    for name in FILES:
        digest=hashlib.sha256()
        with (dataset_path/name).open('rb') as source:
            for block in iter(lambda:source.read(1<<20),b''):digest.update(block)
        dataset_hashes[name]=digest.hexdigest()
    try:commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[3],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception:commit=None
    metadata['shared_array_names']=shared_brain_arrays
    if non_neural_policy:
        metadata['non_neural_policy']=non_neural_policy.metadata
        metadata['non_neural_checkpoint_sha256']=hashlib.sha256(a.non_neural_policy.read_bytes()).hexdigest()
    metadata.update({'neurons_per_instance':[int(b.n) for b in brain.brains],
        'instance_count':len(brain.brains),'instance_batches':[int(b.batch) for b in brain.brains],
        'instances_independent':len(brain.brains)==2 and brain.brains[0] is not brain.brains[1] and not shared_brain_arrays,
        'neural_timestep_s':float(brain.brains[0].dt),'flybrain_version':importlib.metadata.version('flybrain'),
        'dataset_sha256':dataset_hashes,'dataset_path':str(dataset_path),'python_version':platform.python_version(),
        'platform':platform.platform(),'git_commit':commit,'condition':a.condition,
        'ablate_channels':a.ablate_channels.split(',') if a.condition=='MALECNS_ABLATED' else [],
        'shuffle_procedure':'fixed one-agent cyclic signal reassignment within each team; exact six-channel signal multiset preserved per team and neural step' if a.condition=='MALECNS_SHUFFLED' else None,
        'experiment_id':a.experiment_id,'run_id':a.run_id})
    channel_ids={'DNp09_L':0,'DNp09_R':1,'DNa02_L':2,'DNa02_R':3,'DNp01':4,'wing':5}
    try:ablate_indices=[channel_ids[name.strip()] for name in a.ablate_channels.split(',') if name.strip()]
    except KeyError as exc:raise SystemExit(f'Unknown ablation channel: {exc}')
    shuffle_source=[(i+1)%8 for i in range(8)]+[8+(i+1)%8 for i in range(8)]
    research_stream=None
    if a.research_log:
        a.research_log.parent.mkdir(parents=True,exist_ok=True)
        research_stream=a.research_log.open('x',encoding='utf-8',buffering=1)
    nn_x=[];nn_y=[];nn_seed=[]
    if a.collect_nonneural and a.collect_nonneural.exists():
        raise FileExistsError(a.collect_nonneural)
    with socket.socket() as server:
        server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        server.bind(('127.0.0.1',a.port));server.listen(1)
        status('READY')
        print('READY 1 x FlyBrain(batch=1)' if a.demo else 'READY 2 x FlyBrain(batch=8)',json.dumps(metadata),flush=True)
        while True:
            connection,_=server.accept()
            try:
                with connection,connection.makefile('rb') as stream:
                    last=0
                    while (packet:=read(stream)) is not None:
                        if packet['seq']<=last:raise ValueError('Non-monotonic sequence')
                        last=packet['seq'];obs=packet['observations']
                        traces,heard,ms=brain.step(obs,packet['audio'])
                        neural_traces=np.asarray(traces,dtype=float)
                        effective_traces=neural_traces.copy()
                        if a.condition=='MALECNS_ABLATED':effective_traces[:8,ablate_indices]=0.0
                        if a.condition=='MALECNS_SHUFFLED':effective_traces[:8]=neural_traces[shuffle_source[:8]]
                        actions=[];control_layers=[]
                        for agent_index,(o,t) in enumerate(zip(obs,effective_traces)):
                            team='blue' if o['id']<8 else 'red'
                            is_non_neural=(a.condition=='NON_NEURAL_TRAINED' and agent_index<8)
                            policy=non_neural_policy if is_non_neural else team_policies.get(team,policies.get(o['vehicle'],policies.get('shared')))
                            if policies and policy is None:raise ValueError(f"No policy for {o['vehicle']}")
                            is_combat_ppo=isinstance(policy,CombatPPOPolicy)
                            is_ppo=isinstance(policy,SharedPPOPolicy)
                            is_non_neural=isinstance(policy,NonNeuralAdapter)
                            mode=policy.mode if policy and hasattr(policy,'mode') else a.feature_mode
                            x=NonNeuralAdapter.inputs(o) if is_non_neural else (combat_features(t,o) if is_combat_ppo else (ppo_features(policy,t,o) if is_ppo else features(t,o['proprio'],mode)))
                            decoded=brain.baseline(t)
                            raw_neural=np.asarray(neural_traces[agent_index],dtype=float)
                            objective_aux=np.zeros(6);gunnery_aux=np.zeros(6)
                            adapter_action=None
                            if a.collect_nonneural:
                                nn_x.append(NonNeuralAdapter.inputs(o));nn_y.append(np.asarray(o['teacher'],dtype=float));nn_seed.append(a.seed)
                            if a.collect:
                                xs.append(x);ys.append(o['teacher']);vehicles.append(o['vehicle']);seeds.append(a.seed)
                                action=np.array(o['teacher'])
                            elif getattr(a,team+'_controller')=='rule':
                                action=np.array(o['teacher']);decoded=None
                            elif policy:
                                action=policy.act(x,deterministic=True)[0] if is_ppo else (policy.act(x)[0] if is_combat_ppo else policy.predict(x));adapter_action=action.copy()
                            else:
                                action=decoded.copy()

                                # Explicit locomotion/search auxiliary.
                                # When no enemy is visible the visual encoder
                                # injects no LC9 pursuit stimulus. Without a
                                # floor the tank can remain indefinitely at
                                # spawn. This auxiliary knows no waypoint,
                                # objective coordinate, enemy coordinate or
                                # vehicle role.
                                if not o['visible']:
                                    previous=float(action[0]);action[0]=max(previous,.18)
                                    objective_aux[0]=float(action[0])-previous

                                # Explicit rule-based fire/elevation auxiliary baseline.
                                previous=action.copy()
                                action[4]=np.clip(o['elevation']*6,-1,1)
                                action[5]=float(o['visible'] and abs(o['bearing'])<.015 and abs(o['elevation'])<.012)
                                gunnery_aux=action-previous
                            if not o['alive']:action=np.zeros(6)
                            actions.append(action.tolist())
                            control_layers.append({
                                'raw_neural_action':raw_neural.tolist(),
                                'raw_neural_trace':raw_neural.tolist(),
                                'effective_neural_trace':np.asarray(t,dtype=float).tolist(),
                                'neural_source_agent':shuffle_source[agent_index] if a.condition=='MALECNS_SHUFFLED' and agent_index<8 else agent_index,
                                'decoder_action':None if decoded is None else decoded.tolist(),
                                'objective_aux_action':objective_aux.tolist(),
                                'gunnery_aux_action':gunnery_aux.tolist(),
                                'adapter_action':None if adapter_action is None else adapter_action.tolist(),
                                'final_action':action.tolist(),
                            })
                        result=dict(version=1,seq=last,actions=actions,control_layers=control_layers,traces=neural_traces.tolist(),effective_traces=effective_traces.tolist(),heard=heard.tolist(),tick_ms=ms,dt=float(brain.brains[0].dt),mode='IMITATION_TEACHER' if a.collect else ('TRAINED_ADAPTER' if policies or team_policies else 'BIOLOGICAL_BASELINE'),metadata=metadata,communication=brain.last_communication,observations=[{k:v for k,v in o.items() if k!='teacher'} for o in obs],sensory_inputs=getattr(brain,'last_sensory_inputs',{}),simulation_time_s=float(packet.get('simulation_time_s',0.0)),physics_step_id=int(packet.get('physics_step_id',0)))
                        if research_stream:
                            record={'schema':'flyswarm.godot_malecns.neural_step.v1','experiment_id':a.experiment_id,'run_id':a.run_id,'condition':a.condition,'seed':a.seed,'neural_step_id':last,'simulation_time_s':result['simulation_time_s'],'neural_time_s':float((last-1)*result['dt']),'physics_step_id':result['physics_step_id'],'wall_time_unix_s':time.time(),'wall_time_monotonic_s':time.monotonic(),'dt_s':result['dt'],'sensory_inputs':result['sensory_inputs'],'observations':result['observations'],'neural_traces':neural_traces.tolist(),'effective_traces':effective_traces.tolist(),'heard':heard.tolist(),'control_layers':control_layers,'actions':actions,'tick_ms':ms,'metadata':metadata}
                            research_stream.write(json.dumps(record,separators=(',',':'),allow_nan=False)+'\n')
                        connection.sendall(encode(result))
            except (ConnectionError,ValueError) as e:print(type(e).__name__,str(e),flush=True)
            finally:
                if a.collect and xs:
                    path=Path(a.collect);path.parent.mkdir(parents=True,exist_ok=True)
                    np.savez(path,x=xs,y=ys,vehicle=vehicles,seed=seeds,mode=a.feature_mode,metadata=json.dumps(metadata))
                    print('SAVED',len(xs),'imitation samples',a.collect,flush=True)
                if a.collect_nonneural and nn_x:
                    path=a.collect_nonneural;path.parent.mkdir(parents=True,exist_ok=True)
                    np.savez(path,x=np.asarray(nn_x,dtype=float),y=np.asarray(nn_y,dtype=float),seed=np.asarray(nn_seed,dtype=int),feature_schema=NonNeuralAdapter.FEATURE_SCHEMA)
                    print('SAVED',len(nn_x),'non-neural samples',path,flush=True)
            if a.once:break
            brain.reset(a.seed)
    if research_stream:research_stream.close()
if __name__=='__main__':raise SystemExit(main() or 0)
