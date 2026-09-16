import argparse,json
from pathlib import Path
import numpy as np
from flyswarm.policy import Readout
from flyswarm.training import TRAIN_SEEDS,TEST_SEEDS

def main():
    p=argparse.ArgumentParser();p.add_argument('dataset');p.add_argument('output');p.add_argument('--vehicle',default='shared');p.add_argument('--evaluate');a=p.parse_args()
    with np.load(a.dataset,allow_pickle=False) as d:
        x,y,ids,seeds=d['x'],d['y'],d['vehicle'],d['seed'];mode=str(d['mode'])
    if set(seeds.tolist())&set(TEST_SEEDS):raise ValueError('Test seeds may not enter training')
    if not set(seeds.tolist())<=set(TRAIN_SEEDS):raise ValueError('Use declared training seeds')
    mask=np.ones(len(x),dtype=bool) if a.vehicle=='shared' else ids==a.vehicle
    if not np.any(mask):raise ValueError('No samples for requested vehicle')
    model=Readout.fit(x[mask],y[mask],mode,{'vehicle':a.vehicle,'method':'ridge imitation','train_seeds':sorted(set(seeds.tolist())),'samples':int(mask.sum()),'stage':3})
    model.save(a.output);restored=Readout.load(a.output)
    report={'training_mse':float(np.mean((np.array([restored.predict(v) for v in x[mask]])-y[mask])**2)),'samples':int(mask.sum()),'policy':a.output,'stage':3,'method':'imitation; not emergence'}
    if a.evaluate:
        with np.load(a.evaluate,allow_pickle=False) as d:
            if set(d['seed'].tolist())&set(seeds.tolist()):raise ValueError('Train/test seed leakage')
            if str(d['mode'])!=mode:raise ValueError('Feature mismatch')
            report['heldout_imitation_mse']=float(np.mean((np.array([restored.predict(v) for v in d['x']])-d['y'])**2))
    Path(a.output).with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
