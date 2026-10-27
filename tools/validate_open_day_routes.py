"""Drive every vehicle through all three Open Day corridors using real Godot physics.

Fixtures and logs stay under ignored build/validation; no project copy is made.
Run from any directory: python tools/validate_open_day_routes.py /path/to/Godot
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'build' / 'validation'
OUTPUT.mkdir(parents=True, exist_ok=True)
engine = sys.argv[1]
source = (ROOT / 'frontend/godot/scripts/app/open_day_map_checks.gd').read_text()
results = []
for index, name in enumerate(('west', 'village', 'east')):
    fixture = OUTPUT / f'route-{name}-checks.gd'
    fixture.write_text(source.replace('Layout.ROUTES[0]', f'Layout.ROUTES[{index}]')
                       .replace('western route', f'{name} route'))
    wrapper = OUTPUT / f'route-{name}-entry.gd'
    wrapper.write_text('extends SceneTree\nfunc _initialize():call_deferred("run")\n'
                       f'func run():root.add_child(load({json.dumps(str(fixture))}).new())\n')
    with (OUTPUT / f'route-{name}.log').open('w') as log:
        completed = subprocess.run(
            ['nice', '-n', '10', engine, '--headless', '--fixed-fps', '120',
             '--path', str(ROOT / 'frontend/godot'), '--script', str(wrapper)],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=300,
        )
    result = json.loads((OUTPUT / 'map-checks.json').read_text())
    result['corridor'] = name
    (OUTPUT / f'route-{name}.json').write_text(json.dumps(result, indent=2)+'\n')
    results.append(result)
    print(name, 'exit', completed.returncode, 'failures', result['failures'], flush=True)
    if completed.returncode:
        raise SystemExit(completed.returncode)
(OUTPUT / 'all-routes.json').write_text(json.dumps(results, indent=2)+'\n')
