"""Paired side-swap controls, bounded default duration, isolated result folders."""
import argparse,json,os,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--godot',required=True);p.add_argument('--seconds',type=float,default=30)
p.add_argument('--seed',type=int,default=200);p.add_argument('--normalized',action='store_true');p.add_argument('--mirror');a=p.parse_args()
root=ROOT/'results/raw/3d'/time.strftime('paired-%Y%m%d-%H%M%S');root.mkdir(parents=True,exist_ok=False)
rows=[]
for swap in [False,True]:
    dest=root/('north' if swap else 'south')
    args=[a.godot,'--headless','--path',str(ROOT/'frontend/godot'),'--','--seconds',str(a.seconds),'--seed',str(a.seed),'--quit','--record',str(dest)]
    if swap:args+=['--swap']
    if a.normalized:args+=['--normalized']
    if a.mirror:args+=['--mirror',a.mirror]
    subprocess.run(args,check=True,timeout=max(90,a.seconds*4))
    rows.append(json.loads((dest/'summary.json').read_text()))
summary={'seed':a.seed,'controller':'RULE_BASED_CONTROL','normalized':a.normalized,'mirror':a.mirror,'paired_mean_ticket_difference':sum(r['tickets'][0]-r['tickets'][1] for r in rows)/2,'runs':[str(root/'south'),str(root/'north')]}
(root/'paired.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
