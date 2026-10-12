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
from flyswarm.marl.experiments import TeamGymnasiumEnv, run_random_baseline
import json

class MarlTests(unittest.TestCase):
    def test_parallel_api(self):parallel_api_test(FlySwarmParallelEnv(max_steps=5),num_cycles=8)
    def test_reproducible_and_six_actions(self):
        a=FlySwarmParallelEnv(max_steps=3);b=FlySwarmParallelEnv(max_steps=3)
        oa,_=a.reset(seed=12);ob,_=b.reset(seed=12)
        self.assertEqual(list(oa),[f"blue_{i}" for i in range(8)]+[f"red_{i}" for i in range(8)])
        self.assertEqual(a.action_space("blue_0").shape,(6,));np.testing.assert_array_equal(oa["red_7"],ob["red_7"])
        self.assertEqual(oa["blue_0"].shape,(22+ROLE_FEATURE_DIM,))
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
        self.assertEqual(dim,22+ROLE_FEATURE_DIM)
        fake_observation={"vehicle":"panther_g","rl_task":[0.0]*16}
        x=ppo_features(policy,np.zeros(6),fake_observation)
        self.assertEqual(x.shape,(dim,))
        legacy=SharedPPOPolicy(obs_dim=28,seed=5)
        old_x=ppo_features(legacy,np.zeros(6),{"vehicle":"panther_g","rl_task":[0.0]*14})
        self.assertEqual(old_x.shape,(28,))
        policy.act(obs["blue_0"],deterministic=True)
    def test_team_gymnasium_adapter_uses_authoritative_rewards(self):
        env=TeamGymnasiumEnv(seed=8,max_steps=2)
        observation,_=env.reset(seed=8)
        self.assertEqual(observation.shape,(8*env.env.obs_dim,))
        self.assertEqual(env.action_space.shape,(8,6))
        next_observation,reward,terminated,truncated,info=env.step(np.zeros((8,6),np.float32))
        self.assertAlmostEqual(reward,sum(info["snapshot"]["agents"][i]["reward"] for i in range(8)))
        self.assertEqual(info["backend"],"analytical_training")
        self.assertEqual(len(info["snapshot"]["agents"]),16)
        self.assertFalse(terminated);self.assertFalse(truncated)
        env.close()
    def test_analytical_fire_requires_line_of_sight_aim_and_records_turret(self):
        env=FlySwarmParallelEnv(max_steps=5,role_conditioning=False);env.reset(seed=13)
        env.pos[0]=[0.,0.];env.heading[0]=0.
        env.pos[8]=[100.,0.];env.heading[8]=np.pi
        actions={agent:np.zeros(6,np.float32) for agent in env.agents}
        actions["blue_0"][3]=1.
        env.step(actions)
        self.assertGreater(env.turret_heading[0],0.)
        self.assertEqual(env.health[8],1.)
        env.turret_heading[0]=.3
        actions["blue_0"][3]=0.;actions["blue_0"][5]=1.
        _,_,_,_,_=env.step(actions)
        shot=next(event for event in env.last_events if event["type"]=="shot" and event["agent_id"]=="blue_0")
        self.assertFalse(shot["hit"])
        self.assertIsNone(shot["impact_location"])
        self.assertEqual(env.health[8],1.)
        env.reset(seed=14);env.pos[0]=[0.,0.];env.heading[0]=0.;env.turret_heading[0]=0.
        env.pos[8]=[100.,0.]
        actions={agent:np.zeros(6,np.float32) for agent in env.agents};actions["blue_0"][5]=1.
        env.step(actions)
        hit=next(event for event in env.last_events if event["type"]=="shot" and event["agent_id"]=="blue_0")
        self.assertTrue(hit["hit"]);self.assertGreater(hit["damage"],0.);self.assertLess(env.health[8],1.)
        env.close()
    def test_random_baseline_writes_replay_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/"trial"
            result=run_random_baseline(root,episodes=1,seed=31,max_steps=2)
            self.assertEqual(result["runs"][0]["episode_steps"],2)
            replay=Path(result["experiment_dir"])/"replays"/"random-seed-31.jsonl"
            frames=[json.loads(line) for line in replay.read_text().splitlines()]
            self.assertEqual([frame["kind"] for frame in frames],["header","frame","frame","frame"])
            self.assertEqual(len(frames[-1]["agents"]),16)
            self.assertEqual([frame["sim_time_s"] for frame in frames[1:]],[0.,.1,.2])
            self.assertEqual([frames[-1]["agents"][i]["team"] for i in (0,7,8,15)],["blue","blue","red","red"])
            self.assertEqual([zone["zone_id"] for zone in frames[-1]["zones"]],["A","B","C"])
            self.assertAlmostEqual(frames[-1]["sim_time_s"],.2)
            self.assertEqual(frames[-1]["state_authority"],"FlySwarmParallelEnv")
            final_state=json.loads(replay.with_suffix(".final_state.json").read_text())
            self.assertEqual(final_state["agents"],frames[-1]["agents"])
            self.assertEqual(final_state["tickets"],frames[-1]["tickets"])
            self.assertTrue((root/"baseline.csv").is_file())
            self.assertTrue((root/"summary.json").is_file())
if __name__=="__main__":unittest.main()
