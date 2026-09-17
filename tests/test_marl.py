import tempfile
import unittest
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from pettingzoo.test import parallel_api_test
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy
from flyswarm.marl.roles import ROLE_FEATURE_DIM,role_features,vehicle_profile
from flyswarm.bridge.server import load_policy,ppo_features

class MarlTests(unittest.TestCase):
    def test_parallel_api(self):parallel_api_test(FlySwarmParallelEnv(max_steps=5),num_cycles=8)
    def test_reproducible_and_six_actions(self):
        a=FlySwarmParallelEnv(max_steps=3);b=FlySwarmParallelEnv(max_steps=3)
        oa,_=a.reset(seed=12);ob,_=b.reset(seed=12)
        self.assertEqual(list(oa),[f"blue_{i}" for i in range(8)]+[f"red_{i}" for i in range(8)])
        self.assertEqual(a.action_space("blue_0").shape,(6,));np.testing.assert_array_equal(oa["red_7"],ob["red_7"])
        self.assertEqual(oa["blue_0"].shape,(20+ROLE_FEATURE_DIM,))
        zero={agent:np.zeros(6,np.float32) for agent in a.agents};_,rewards,_,trunc,infos=a.step(zero)
        self.assertEqual(set(rewards),set(a.possible_agents));self.assertIn("reward_components",infos["blue_0"])
        self.assertIn("role_shaping",infos["blue_0"]["reward_components"])
        for _ in range(2):_,_,_,trunc,_=a.step(zero)
        self.assertTrue(all(trunc.values()))
    def test_vehicle_role_profiles(self):
        self.assertEqual(vehicle_profile("tiger_i")["tactical_role"],"heavy_anchor")
        self.assertEqual(vehicle_profile("su100")["tactical_role"],"td_support")
        self.assertEqual(vehicle_profile("t34_85")["nation"],"ussr")
        self.assertEqual(role_features("panther_g").shape,(ROLE_FEATURE_DIM,))
        self.assertFalse(np.array_equal(role_features("panther_g"),role_features("t34_85")))
    def test_checkpoint_reload(self):
        policy=SharedPPOPolicy(seed=3);obs=np.zeros(20);before=policy.act(obs,deterministic=True)[0]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"policy.npz";policy.save(path);loaded=load_policy(path);after=loaded.act(obs,deterministic=True)[0]
            self.assertIsInstance(loaded,SharedPPOPolicy)
        np.testing.assert_array_equal(before,after)
    def test_role_conditioned_checkpoint_and_live_features(self):
        env=FlySwarmParallelEnv(max_steps=1,role_conditioning=True);obs,_=env.reset(seed=1)
        dim=env.observation_space("blue_0").shape[0];policy=SharedPPOPolicy(obs_dim=dim,seed=4)
        self.assertEqual(dim,20+ROLE_FEATURE_DIM)
        fake_observation={"vehicle":"panther_g","rl_task":[0.0]*14}
        x=ppo_features(policy,np.zeros(6),fake_observation)
        self.assertEqual(x.shape,(dim,))
        policy.act(obs["blue_0"],deterministic=True)
if __name__=="__main__":unittest.main()
