import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
import sys
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from pettingzoo.test import parallel_api_test
from flyswarm.marl import FlySwarmParallelEnv
from flyswarm.marl.policy import SharedPPOPolicy
from flyswarm.marl.roles import ROLE_FEATURE_DIM,role_features,vehicle_profile
from flyswarm.bridge.server import load_policy,ppo_features
from flyswarm.marl.experiments import TeamGymnasiumEnv, SharedAgentVecEnv, run_random_baseline, train_sb3_ppo
from flyswarm.marl.experiments import run_student_agent
from flyswarm.marl.student_code import AGENT_TEMPLATE, REWARD_TEMPLATE, ManagedStudentAgent, load_agent, load_reward
from flyswarm.marl.exporter import export_practical
import zipfile
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
    def test_team_reward_components_are_not_multiplied_by_agent_count(self):
        env=FlySwarmParallelEnv(max_steps=4);env.reset(seed=28)
        env.zones_owner[0]=0;env.tickets[1]=250.
        actions={agent:np.zeros(6,np.float32) for agent in env.agents}
        _,rewards,_,_,infos=env.step(actions)
        ticket_delta=sum(infos[f"blue_{i}"]["reward_components"]["ticket_delta"] for i in range(8))
        self.assertAlmostEqual(ticket_delta,.02)
        self.assertAlmostEqual(sum(rewards[f"blue_{i}"] for i in range(8)),
            sum(infos[f"blue_{i}"]["standard_evaluation_reward"] for i in range(8)))
        env.close()
    def test_role_shaping_is_small_signed_distance_delta_and_cannot_reward_idling(self):
        env=FlySwarmParallelEnv(max_steps=2,curriculum_tier="C");env.reset(seed=81)
        env.zones[0]=np.array([0.,0.]);previous=env.pos.copy();previous[0]=[100.,0.]
        env.pos[0]=[90.,0.]
        toward=env._role_shaping(0,previous,np.zeros(6,np.float32))
        self.assertAlmostEqual(toward,float(env.profiles[0]["objective_bias"])*.01)
        previous[0]=env.pos[0].copy()
        self.assertEqual(env._role_shaping(0,previous,np.zeros(6,np.float32)),0.)
        env.pos[0]=[100.,0.]
        self.assertLess(env._role_shaping(0,previous,np.zeros(6,np.float32)),0.)
        self.assertLessEqual(abs(toward),.05)
        env.close()
    def test_objective_approach_gives_dense_bounded_signed_learning_signal(self):
        env=FlySwarmParallelEnv(max_steps=2,curriculum_tier="A");env.reset(seed=82)
        env.zones[0]=np.array([0.,0.]);previous=env.pos.copy();previous[0]=[-100.,0.]
        env.pos[0]=[-99.,0.]
        self.assertAlmostEqual(env._objective_approach(0,previous),.01)
        previous[0]=env.pos[0].copy()
        self.assertEqual(env._objective_approach(0,previous),0.)
        env.pos[0]=[-100.,0.]
        self.assertAlmostEqual(env._objective_approach(0,previous),-.01)
        env.pos[0]=[0.,0.]
        self.assertAlmostEqual(env._objective_approach(0,previous),.05)
        env.close()
    def test_terminal_rewards_follow_resolved_outcome(self):
        env=FlySwarmParallelEnv(max_steps=3);env.reset(seed=30)
        env.health[8:]=0.
        actions={agent:np.zeros(6,np.float32) for agent in env.agents}
        _,rewards,terms,truncs,infos=env.step(actions)
        self.assertEqual(env.last_outcome["winner"],"blue")
        self.assertAlmostEqual(sum(infos[f"blue_{i}"]["reward_components"]["battle_win"] for i in range(8)),1.)
        self.assertAlmostEqual(sum(infos[f"red_{i}"]["reward_components"]["battle_loss"] for i in range(8)),1.)
        self.assertTrue(all(terms.values()));self.assertFalse(any(truncs.values()))
        env.reset(seed=31);env.health[:]=0.
        actions={agent:np.zeros(6,np.float32) for agent in env.agents}
        _,_,_,_,infos=env.step(actions)
        self.assertIsNone(env.last_outcome["winner"])
        self.assertAlmostEqual(sum(infos[f"blue_{i}"]["reward_components"]["battle_draw"] for i in range(8)),1.)
        env.close()
    def test_battle_outcome_elimination_tickets_timeout_and_draw(self):
        env=FlySwarmParallelEnv(max_steps=2);env.reset(seed=29)
        self.assertEqual(env._resolve_outcome(True,False,False,False),(0,"opponent_eliminated"))
        self.assertEqual(env._resolve_outcome(False,False,False,False),(None,"simultaneous_elimination"))
        env.tickets=np.array([300.,0.])
        self.assertEqual(env._resolve_outcome(True,True,True,False),(0,"enemy_tickets_exhausted"))
        env.tickets=np.array([0.,0.])
        self.assertEqual(env._resolve_outcome(True,True,True,False),(None,"simultaneous_ticket_exhaustion"))
        env.tickets=np.array([100.,100.]);env.zones_owner=np.array([0,0,1])
        self.assertEqual(env._resolve_outcome(True,True,False,True),(0,"timeout_objectives"))
        env.zones_owner=np.array([0,1,-1])
        self.assertEqual(env._resolve_outcome(True,True,False,True),(None,"timeout_draw"))
        env.close()
    def test_curriculum_a_keeps_same_spaces_and_disables_combat(self):
        env=FlySwarmParallelEnv(max_steps=3,curriculum_tier="A")
        obs,_=env.reset(seed=5)
        self.assertEqual(len(obs),16);self.assertEqual(obs["blue_0"].shape,obs["blue_7"].shape)
        self.assertEqual(np.count_nonzero(env.health[:8]),1);self.assertEqual(np.count_nonzero(env.health[8:]),1)
        actions={agent:np.zeros(6,np.float32) for agent in env.agents};actions["blue_0"][5]=1.
        env.pos[0]=[0.,0.];env.pos[8]=[50.,0.]
        env.step(actions)
        self.assertEqual(env.health[8],1.)
        env.close()
    def test_curriculum_a_seed_changes_small_start_jitter_reproducibly(self):
        first=FlySwarmParallelEnv(curriculum_tier="A");second=FlySwarmParallelEnv(curriculum_tier="A");other=FlySwarmParallelEnv(curriculum_tier="A")
        first.reset(seed=81);second.reset(seed=81);other.reset(seed=82)
        np.testing.assert_array_equal(first.pos[[0,8]],second.pos[[0,8]])
        self.assertFalse(np.array_equal(first.pos[[0,8]],other.pos[[0,8]]))
        first.close();second.close();other.close()
    def test_parameter_sharing_vecenv_synchronizes_multiple_agents(self):
        env=SharedAgentVecEnv(seed=19,max_steps=2,curriculum_tier="B")
        observations=env.reset()
        self.assertEqual(observations.shape,(4,env.observation_space.shape[0]))
        obs,rewards,dones,infos=env.step(np.zeros((4,6),np.float32))
        self.assertEqual(rewards.shape,(4,));self.assertFalse(dones.any())
        obs,rewards,dones,infos=env.step(np.zeros((4,6),np.float32))
        self.assertTrue(dones.all());self.assertEqual(sum("episode" in item for item in infos),1)
        self.assertEqual(obs.shape,(4,env.observation_space.shape[0]))
        env.close()
    def test_student_python_api_runs_strategy_and_snapshots_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);agent_file=root/"agent.py";reward_file=root/"reward.py"
            agent_file.write_text(AGENT_TEMPLATE,encoding="utf-8")
            reward_file.write_text(REWARD_TEMPLATE,encoding="utf-8")
            action=load_agent(agent_file)(np.zeros(30,np.float32),{"agent_id":"blue_0"})
            self.assertEqual(action.shape,(6,));self.assertEqual(action[0],.5)
            self.assertTrue(np.isfinite(load_reward(reward_file)({"objective_capture":1.0,"damage_dealt":0.0,"own_death":0.0})))
            output=root/"student-run"
            result=run_student_agent(output,agent_file,episodes=1,seed=71,max_steps=2,reward_file=reward_file)
            self.assertEqual(result["runs"][0]["episode_steps"],2)
            self.assertTrue((output/"student_code/agent.py").is_file())
            self.assertTrue((output/"student_code/reward.py").is_file())
            self.assertTrue((output/"replays/student-seed-71.jsonl").is_file())
            self.assertTrue((output/"manifest.json").is_file())
    def test_student_code_rejects_bad_contract_and_nonfinite_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            bad=root/"bad.py";bad.write_text("def act(obs): return [0, 0]\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"exactly 6"):
                load_agent(bad)(np.zeros(30,np.float32),{})
            bad.write_text("def act(obs): return [float('nan')] * 6\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"NaN"):
                load_agent(bad)(np.zeros(30,np.float32),{})
            bad.write_text("def act(obs): return [2, 0, 0, 0, 0, 0]\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"range"):
                load_agent(bad)(np.zeros(30,np.float32),{})
            bad.write_text("def act(obs):\n !!!",encoding="utf-8")
            with self.assertRaises(SyntaxError):load_agent(bad)
    def test_managed_student_worker_runs_and_reports_exceptions(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"agent.py"
            source.write_text("def act(obs, context=None):\n    return [context['team_index']/8, 0, 0, 0, 0, 0]\n",encoding="utf-8")
            with ManagedStudentAgent(source,timeout_seconds=4) as worker:
                actions=worker.act_team([np.zeros(30,np.float32),np.ones(30,np.float32)],
                    [{"team_index":0},{"team_index":4}])
                self.assertEqual([float(x[0]) for x in actions],[0.,.5])
                self.assertTrue(worker.process.is_alive())
            self.assertFalse(worker.process.is_alive())
            source.write_text("def act(obs):\n    raise RuntimeError('student failure')\n",encoding="utf-8")
            with ManagedStudentAgent(source,timeout_seconds=4) as worker:
                with self.assertRaisesRegex(RuntimeError,"student failure"):
                    worker.act_team([np.zeros(30,np.float32)],[{}])
    def test_managed_student_worker_times_out_and_terminates(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"agent.py"
            source.write_text("def act(obs):\n    while True: pass\n",encoding="utf-8")
            with ManagedStudentAgent(source,timeout_seconds=.2,startup_timeout_seconds=4) as worker:
                with self.assertRaisesRegex(TimeoutError,"timed out"):
                    worker.act_team([np.zeros(30,np.float32)],[{}])
                self.assertFalse(worker.process.is_alive())
    def test_custom_reward_rejects_missing_function_and_nonfinite_result(self):
        with tempfile.TemporaryDirectory() as directory:
            source=Path(directory)/"reward.py";source.write_text("VALUE = 2\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"calculate_reward"):
                load_reward(source)
            source.write_text("def calculate_reward(c): return float('inf')\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"NaN or infinity"):
                load_reward(source)({})
    def test_practical_export_only_contains_real_session_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);workspace=root/"workspace";sessions=root/"sessions";session=sessions/"run-1"
            workspace.mkdir();session.mkdir(parents=True)
            (workspace/"agent.py").write_text("def act(o): return [0]*6\n",encoding="utf-8")
            (session/"manifest.json").write_text(json.dumps({"experiment":"student"}),encoding="utf-8")
            (session/"evaluation.csv").write_text("seed,score\n1,2\n",encoding="utf-8")
            (session/"progress.json").write_text("{}",encoding="utf-8")
            outside=root/"private.txt";outside.write_text("must not export",encoding="utf-8")
            (session/"linked-private.txt").symlink_to(outside)
            destination=root/"submission.zip"
            result=export_practical(workspace,sessions,destination)
            self.assertEqual(result["sessions"],1)
            with zipfile.ZipFile(destination) as archive:
                names=set(archive.namelist())
                self.assertIn("FlySwarm_Practical/agent.py",names)
                self.assertIn("FlySwarm_Practical/results/run-1/evaluation.csv",names)
                self.assertNotIn("FlySwarm_Practical/results/run-1/progress.json",names)
                self.assertFalse(any("linked-private" in name for name in names))
    def test_custom_reward_is_used_inside_ppo_environment(self):
        env=TeamGymnasiumEnv(seed=9,max_steps=1,reward_function=lambda components: 2.0)
        env.reset(seed=9)
        _,reward,_,_,info=env.step(np.zeros((8,6),np.float32))
        self.assertEqual(reward,16.0)
        self.assertNotEqual(reward,info["standard_evaluation_reward"])
        self.assertEqual(info["backend"],"analytical_training")
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
    def test_ppo_progress_reports_finalization_until_chart_is_ready(self):
        from flyswarm.marl import experiments
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/"ppo"
            progress=output/"progress.json"
            observed=[]
            def render_chart(csv_path,png_path):
                state=json.loads(progress.read_text())
                observed.append(state["state"])
                self.assertEqual(state["phase"],"artifacts")
                self.assertTrue(csv_path.is_file())
            with patch.object(experiments,"_plot_learning_curve",side_effect=render_chart):
                result=train_sb3_ppo(output,timesteps=16,seed=41,max_steps=2,progress_path=progress)
            state=json.loads(progress.read_text())
            self.assertEqual(observed,["finalizing"])
            self.assertEqual(state["state"],"complete")
            self.assertEqual(state["timesteps"],16)
            self.assertTrue(Path(result["checkpoint"]).is_file())
            metadata=output/"checkpoint"/"ppo_team.metadata.json"
            self.assertTrue(metadata.is_file())
            saved=json.loads(metadata.read_text())
            self.assertEqual(saved["checkpoint_schema"],"flyswarm.sb3_ppo.v2")
            self.assertEqual(saved["num_timesteps"],16)
            continued=Path(directory)/"continued"
            with patch.object(experiments,"_plot_learning_curve",return_value=None):
                result2=train_sb3_ppo(continued,timesteps=16,seed=41,max_steps=2,
                    continue_from=Path(result["checkpoint"]))
            self.assertEqual(result2["initial_timesteps"],16)
            self.assertEqual(result2["timesteps"],32)
            self.assertEqual(json.loads((continued/"manifest.json").read_text())["continued_from"],str(Path(result["checkpoint"]).resolve()))
            shared=Path(directory)/"shared"
            with patch.object(experiments,"_plot_learning_curve",return_value=None):
                shared_result=train_sb3_ppo(shared,timesteps=16,seed=42,max_steps=2,
                    curriculum_tier="B",ppo_architecture="parameter_sharing")
            shared_manifest=json.loads((shared/"manifest.json").read_text())
            self.assertEqual(shared_manifest["architecture"],"parameter-sharing PPO with local critic; not MAPPO")
            self.assertEqual(shared_result["timesteps"],16)
if __name__=="__main__":unittest.main()
