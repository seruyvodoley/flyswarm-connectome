import io,json,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from flyswarm.catalog import DATA,vehicle,ammunition
from flyswarm.bridge import encode,read,MAX_LINE
from flyswarm.sensory import audio_signal,audio_frame,visual
from flyswarm.policy import Readout,features
from flyswarm.training import TRAIN_SEEDS,TEST_SEEDS

class SimulatorTests(unittest.TestCase):
    def test_audio_orientation_cap_and_topology(self):
        positions=np.zeros((16,3));positions[1,0]=250
        live=np.ones(16,dtype=bool);song=np.zeros(16);song[0]=2
        h,c,d=audio_frame(song,positions,live,'all_audio')
        self.assertAlmostEqual(c[1,0],.08)
        self.assertEqual(c[0,1],0)
        self.assertEqual(d[1,0],250)
        for mode in ['no_audio','team_audio','all_audio']:
            for signal in [song,np.full(16,100.)]:
                h,c,d=audio_frame(signal,positions,live,mode)
                np.testing.assert_allclose(c.sum(axis=1),h)
                np.testing.assert_allclose(np.diag(c),0)
                self.assertTrue(np.all(h<=.8+1e-12))
                if mode=='no_audio':self.assertFalse(c.any())
                if mode=='team_audio':self.assertFalse(c[:8,8:].any())
        live[0]=False
        h,c,d=audio_frame(np.ones(16),positions,live,'all_audio')
        self.assertFalse(c[0,:].any());self.assertFalse(c[:,0].any())
        h,c,d=audio_frame(np.full(16,100.),np.zeros((16,3)),np.ones(16,bool),'all_audio')
        np.testing.assert_allclose(c[1:,0],.8/15)

    def test_previous_song_telemetry_causality(self):
        from flyswarm.brain import DualBrain
        class SilentBrain:
            dt=.02
            def step(self, inject):return [np.array([],dtype=int) for _ in range(8)]
        brain=DualBrain.__new__(DualBrain)
        brain.brains=[SilentBrain(),SilentBrain()]
        group={key:np.array([1]) for key in ['lc10_l','lc10_r','lc9_l','lc9_r','loom','ear']}
        group['outputs']=[np.array([1]) for _ in range(6)]
        brain.groups=[group,group];brain.song=np.ones(16);brain.trace=np.zeros((16,6));brain.ticks=9
        obs=[dict(alive=True,position=[0,0,0],bearing=0,visible=False,looming=0) for _ in range(16)]
        _,heard,_=brain.step(obs,'team_audio')
        np.testing.assert_allclose(brain.last_communication['song_out'],1)
        np.testing.assert_allclose(brain.last_communication['heard_total'],heard)
        np.testing.assert_allclose(brain.song,0)
        sample=brain.last_communication['sample']
        brain.step(obs,'team_audio')
        self.assertEqual(brain.last_communication['sample'],sample)
        payload=encode(dict(version=1,seq=10,actions=[[0]*6]*16,communication=brain.last_communication))
        self.assertLess(len(payload),MAX_LINE)
        print('Communication result packet fixture bytes:',len(payload))

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
        heard,contribution,distance=audio_frame(np.ones(16),positions,live,'team_audio')
        self.assertEqual(contribution.shape,(16,16))
        self.assertEqual(distance.shape,(16,16))
        np.testing.assert_allclose(contribution.sum(axis=1),heard)
        np.testing.assert_allclose(np.diag(contribution),0)
        self.assertAlmostEqual(contribution[0,1],.08)
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
