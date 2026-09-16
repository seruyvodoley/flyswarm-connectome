"""Stage a self-contained Godot frontend. Python/MaleCNS are NOT bundled."""
import argparse,shutil,subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--godot',default=str(Path.home()/'Applications/Godot.app/Contents/MacOS/Godot'));p.add_argument('--export',action='store_true');a=p.parse_args()
 dest=Path(tempfile.mkdtemp(prefix='flyswarm-export-'))
 shutil.copytree(ROOT/'frontend/godot',dest/'godot',ignore=shutil.ignore_patterns('.godot','._*'))
 shutil.copytree(ROOT/'data',dest/'godot/data',ignore=shutil.ignore_patterns('local','._*'))
 print('Frontend staged:',dest/'godot')
 if a.export:
  output=ROOT/'build/FlySwarm.zip';output.parent.mkdir(exist_ok=True)
  subprocess.run([a.godot,'--headless','--editor','--path',str(dest/'godot'),'--import'],check=True)
  result=subprocess.run([a.godot,'--headless','--path',str(dest/'godot'),'--export-release','macOS Local Frontend',str(output)])
  if result.returncode:raise SystemExit('Export failed. Install matching Godot macOS export templates; no completed application bundle is claimed.')
  print('Unsigned frontend export:',output)
 else:print('Preparation only. Use --export after installing matching Godot export templates.')
if __name__=='__main__':main()
