import subprocess,os,json,tempfile,time
from pathlib import Path
root=Path.cwd();out=Path(tempfile.mkdtemp(prefix='flyswarm-cancel-'))
c=dict(mode='research',output=str(out),godot=str(Path.home()/'Applications/Godot.app/Contents/MacOS/Godot'),parent_pid=os.getpid(),blue_controller='rule',red_controller='rule',blue_policy='',red_policy='',render_mode='headless',map_seed=1944,battle_seed=200,seconds=30,audio_mode='no_audio',record=False,physics_mode='historical',swap=False,vehicle_composition='mixed_1944',training_vehicle='tiger_i',target_vehicle='t34_85',research_experiment='side_swap',seed_count=1)
p=out/'job.json';p.write_text(json.dumps(c));worker=subprocess.Popen([str(root/'.venv/bin/python'),str(root/'tools/app_job.py'),str(p)])
try:
 deadline=time.monotonic()+20;status={}
 while time.monotonic()<deadline:
  if (out/'progress.json').exists():status=json.loads((out/'progress.json').read_text())
  if status.get('owned_pids'):break
  time.sleep(.1)
 assert status.get('owned_pids'),status
 (out/'cancel').write_text('cancel');worker.wait(timeout=15)
 assert json.loads((out/'progress.json').read_text())['state']=='cancelled'
 for pid in status['owned_pids']:
  try:os.kill(pid,0)
  except ProcessLookupError:continue
  raise AssertionError(f'Child {pid} survived cancellation')
 print('PASS: cancel stopped and reaped all owned child processes')
finally:
 if worker.poll() is None:worker.terminate();worker.wait(timeout=10)
