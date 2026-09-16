import io,json,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flyswarm.catalog import DATA,vehicle,ammunition
from flyswarm.bridge import encode,read,MAX_LINE
from flyswarm.sensory import audio_signal,visual
from flyswarm.policy import Readout,features
from flyswarm.training import TRAIN_SEEDS,TEST_SEEDS

class SimulatorTests(unittest.TestCase):
    def test_six_data_models(self):
        files=[p for p in (DATA/'vehicles').glob('*/*.json') if not p.name.startswith('._')]
        self.assertEqual(len(files),6)
        for f in files:
            obj=vehicle(f.stem);p=obj['parameters']
            gun=json.loads((DATA/'guns'/f"{p['gun']}.json").read_text())
            self.assertEqual(len(ammunition(gun['ammo'])['penetration_mm']),5)
            self.assertEqual(p['turreted'],f.stem not in ['jagdpanther','su100'])
    def test_team_mapping(self):
        scenario=json.loads((DATA/'scenarios/krasny_valley.json').read_text())
        self.assertEqual(len(scenario['blue']),8);self.assertEqual(len(scenario['red']),8)
        self.assertEqual(scenario['blue'].count('panther_g'),4)
        self.assertEqual(scenario['red'].count('su100'),2)
    def test_protocol_roundtrip(self):
        obs=[dict(id=i,position=[0,0,0],proprio=[0]*6,teacher=[0]*6,bearing=0,elevation=0,looming=0,angular_size=0) for i in range(16)]
        p=dict(version=1,seq=1,observations=obs)
        self.assertEqual(read(io.BytesIO(encode(p))),p)
        p['observations'][8]['id']=0
        with self.assertRaises(ValueError):read(io.BytesIO(encode(p)))
    def test_protocol_bounds(self):
        with self.assertRaises(ValueError):read(io.BytesIO(b'x'*(MAX_LINE+1)))
        with self.assertRaises(ValueError):encode({'x':float('nan')})
    def test_audio_and_death(self):
        positions=np.zeros((16,3));live=np.ones(16,dtype=bool)
        np.testing.assert_allclose(audio_signal(np.ones(16),positions,live,'team_audio'),.56)
        np.testing.assert_allclose(audio_signal(np.ones(16),positions,live,'all_audio'),.8)
        live[0]=False
        self.assertEqual(audio_signal(np.ones(16),positions,live,'all_audio')[0],0)
        with self.assertRaises(ValueError):audio_signal(np.ones(16),positions,live,'bad')
    def test_encoder_does_not_use_role_or_xyz(self):
        obs=[dict(bearing=.1,alive=True,visible=True,looming=.01,position=[0,0,0],role='heavy') for _ in range(16)]
        before=visual(obs)
        for o in obs:o['position']=[999,999,999];o['role']='medium'
        after=visual(obs)
        for k in before:np.testing.assert_array_equal(before[k],after[k])
    def test_feature_modes_and_frozen_head(self):
        import tempfile
        self.assertEqual(len(features(np.ones(6),np.zeros(6),'connectome_only')),6)
        self.assertEqual(len(features(np.ones(6),np.zeros(6),'connectome_plus_proprioception')),12)
        rng=np.random.default_rng(1);x=rng.normal(size=(60,6));y=np.tanh(x)
        model=Readout.fit(x,y,'connectome_only',{'seed':100})
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'policy.npz';model.save(path);m=Readout.load(path)
            np.testing.assert_array_equal(model.predict(x[0]),m.predict(x[0]))
            with self.assertRaises(ValueError):m.weights[0,0]=9
    def test_train_test_disjoint(self):self.assertFalse(set(TRAIN_SEEDS)&set(TEST_SEEDS))
if __name__=='__main__':unittest.main()
