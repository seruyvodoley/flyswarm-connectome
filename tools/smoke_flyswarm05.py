"""Import a shortened temporary copy with real 2 x FlyBrain(batch=8).

Runs in a subprocess with a 180 s wall timeout. Never overwrites research output.
"""
import ast
import csv
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'experiments/swarm/flyswarm_05_two_brains_8v8.py'


def main():
    from flybrain.data import DATA, has_data
    if not has_data():
        raise SystemExit(f'MaleCNS data missing at {DATA}; smoke test will not download it.')
    tree = ast.parse(SOURCE.read_text())
    patches = {'SIM_DURATION': 0.2, 'WARMUP_STEPS': 25, 'REST_STEPS': 5,
               'CALIBRATION_SEEDS': [200], 'TEST_SEEDS': [204, 205]}
    replaced = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], 'id', None)
            if name in patches:
                node.value = ast.parse(repr(patches[name]), mode='eval').body
                replaced.add(name)
    assert replaced == patches.keys()
    ast.fix_missing_locations(tree)
    with tempfile.TemporaryDirectory(prefix='flyswarm05-smoke-') as tmp:
        path = Path(tmp)
        (path / 'short_experiment.py').write_text(ast.unparse(tree) + '\n')
        check = '''import short_experiment as m
import numpy as np
assert m.blue.brain is not m.red.brain
assert m.blue.brain.batch == m.red.brain.batch == 8
assert m.blue.brain.device == m.red.brain.device == 'cpu'
assert not np.shares_memory(m.blue.brain.weights, m.red.brain.weights)
assert not np.shares_memory(m.blue.brain.v, m.red.brain.v)
assert len(m.results) == 6
assert {r['condition'] for r in m.results} == {'no_audio', 'team_audio', 'all_audio'}
assert all(0 < r['sim_time'] <= 0.23 for r in m.results)
print('PASS: temporary import; two independent CPU brains and all three modes')
'''
        subprocess.run([sys.executable, '-u', '-c', check], cwd=tmp,
                       env={**os.environ, 'PYTHONUNBUFFERED': '1'}, check=True, timeout=180)
        for name, expected in [('raw', 6), ('summary', 3)]:
            with (path / 'results' / f'flyswarm_05_two_brains_8v8_{name}.csv').open() as f:
                assert len(list(csv.DictReader(f))) == expected
        print('PASS: raw=6 rows; summary=3 rows; temporary outputs discarded')


if __name__ == '__main__':
    main()
