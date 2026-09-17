import tempfile
import unittest
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from pettingzoo.test import parallel_api_test
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy
from flyswarm.bridge.server import load_policy

class MarlTests(unittest.TestCase):
    def test_parallel_api(self):parallel_api_test(FlySwarmParallelEnv(max_steps=5),num_cycles=8)
    def test_reproducible_and_six_actions(self):
        a=FlySwarmParallelEnv(max_steps=3);b=FlySwarmParallelEnv(max_steps=3)
        oa,_=a.reset(seed=12);ob,_=b.reset(seed=12)
        self.assertEqual(list(oa),[f"blue_{i}" for i in range(8)]+[f"red_{i}" for i in range(8)])
        self.assertEqual(a.action_space("blue_0").shape,(6,));np.testing.assert_array_equal(oa["red_7"],ob["red_7"])
        zero={agent:np.zeros(6,np.float32) for agent in a.agents};_,rewards,_,trunc,infos=a.step(zero)
        self.assertEqual(set(rewards),set(a.possible_agents));self.assertIn("reward_components",infos["blue_0"])
        for _ in range(2):_,_,_,trunc,_=a.step(zero)
        self.assertTrue(all(trunc.values()))
    def test_checkpoint_reload(self):
        policy=SharedPPOPolicy(seed=3);obs=np.zeros(20);before=policy.act(obs,deterministic=True)[0]
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"policy.npz";policy.save(path);loaded=load_policy(path);after=loaded.act(obs,deterministic=True)[0]
            self.assertIsInstance(loaded,SharedPPOPolicy)
        np.testing.assert_array_equal(before,after)
if __name__=="__main__":unittest.main()
