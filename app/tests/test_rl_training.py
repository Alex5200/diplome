#!/usr/bin/env python3
"""
TDD тесты для RL Training Module.

Покрытие:
    - Функции наград (BaseReward, DistanceReward, SmoothMotionReward,
                       PickPlaceReward, VisionReward, CompositeReward)
    - Среда RobotArmEnv (reset, step, obs shape, reward)
    - ReplayBuffer
    - Базовый агент BaseRLAgent (через stub)
    - DQNAgent (без PyTorch — через mock)
    - PPOAgent (без PyTorch — через mock)
    - RLTrainingService (setup, start, stop, status, curriculum)

Запуск:
    python -m pytest app/tests/test_rl_training.py -v --tb=short
"""

from __future__ import annotations

import unittest
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import numpy as np

# ═══════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════


def _fake_state(
    ee_pos=None,
    target_pos=None,
    joint_angles=None,
    prev_joint_angles=None,
    gripper_state=True,
    object_grasped=False,
    object_pos=None,
    detection=None,
):
    return {
        "ee_pos": np.array(ee_pos or [0.0, 0.0, 100.0]),
        "target_pos": np.array(target_pos or [150.0, 0.0, 150.0]),
        "joint_angles": np.array(joint_angles or [0.0] * 6),
        "prev_joint_angles": np.array(prev_joint_angles or [0.0] * 6),
        "gripper_state": gripper_state,
        "object_grasped": object_grasped,
        "object_pos": np.array(object_pos or [100.0, 50.0, 0.0]),
        "detection": detection,
    }


# ═══════════════════════════════════════════════
#  TestDistanceReward
# ═══════════════════════════════════════════════


class TestDistanceReward(unittest.TestCase):
    def setUp(self):
        from app.models.rl.rewards import DistanceReward

        self.r = DistanceReward(scale=1.0, success_bonus=10.0, success_threshold_mm=20.0)

    def test_zero_distance_max_reward(self):
        state = _fake_state(ee_pos=[150, 0, 150], target_pos=[150, 0, 150])
        reward = self.r.compute(state)
        self.assertGreater(reward, 10.0)  # scale + success_bonus

    def test_far_distance_low_reward(self):
        state = _fake_state(ee_pos=[0, 0, 0], target_pos=[300, 0, 300])
        reward = self.r.compute(state)
        self.assertLess(reward, 1.0)

    def test_closer_is_better(self):
        far_state = _fake_state(ee_pos=[0, 0, 0], target_pos=[150, 0, 150])
        near_state = _fake_state(ee_pos=[140, 0, 145], target_pos=[150, 0, 150])
        r_far = self.r.compute(far_state)
        r_near = self.r.compute(near_state)
        self.assertGreater(r_near, r_far)

    def test_workspace_penalty(self):
        from app.models.rl.rewards import DistanceReward

        r = DistanceReward(workspace_radius_mm=100.0, workspace_penalty=-5.0)
        state = _fake_state(ee_pos=[500, 0, 0], target_pos=[0, 0, 100])
        reward = r.compute(state)
        self.assertLess(reward, 0.0)

    def test_is_success_true_when_close(self):
        state = _fake_state(ee_pos=[151, 0, 150], target_pos=[150, 0, 150])
        self.assertTrue(self.r.is_success(state))

    def test_is_success_false_when_far(self):
        state = _fake_state(ee_pos=[0, 0, 0], target_pos=[150, 0, 150])
        self.assertFalse(self.r.is_success(state))


# ═══════════════════════════════════════════════
#  TestSmoothMotionReward
# ═══════════════════════════════════════════════


class TestSmoothMotionReward(unittest.TestCase):
    def setUp(self):
        from app.models.rl.rewards import SmoothMotionReward

        self.r = SmoothMotionReward(smoothness_weight=0.1)

    def test_no_movement_zero_penalty(self):
        state = _fake_state(joint_angles=[0] * 6, prev_joint_angles=[0] * 6)
        reward = self.r.compute(state)
        self.assertAlmostEqual(reward, 0.0, places=5)

    def test_large_movement_negative(self):
        state = _fake_state(joint_angles=[30] * 6, prev_joint_angles=[0] * 6)
        reward = self.r.compute(state)
        self.assertLess(reward, 0.0)

    def test_larger_movement_worse(self):
        small = _fake_state(joint_angles=[5] * 6, prev_joint_angles=[0] * 6)
        large = _fake_state(joint_angles=[30] * 6, prev_joint_angles=[0] * 6)
        self.assertGreater(self.r.compute(small), self.r.compute(large))

    def test_joint_limit_penalty(self):
        from app.models.rl.rewards import SmoothMotionReward

        r = SmoothMotionReward(joint_limit_deg=50.0, joint_limit_penalty=-2.0)
        state = _fake_state(joint_angles=[100] * 6, prev_joint_angles=[0] * 6)
        reward = r.compute(state)
        self.assertLess(reward, -10.0)


# ═══════════════════════════════════════════════
#  TestPickPlaceReward
# ═══════════════════════════════════════════════


class TestPickPlaceReward(unittest.TestCase):
    def setUp(self):
        from app.models.rl.rewards import PickPlaceReward

        self.r = PickPlaceReward(place_bonus=20.0)

    def test_not_grasped_approach_reward(self):
        state = _fake_state(ee_pos=[105, 50, 10], object_pos=[100, 50, 0], object_grasped=False)
        reward = self.r.compute(state)
        self.assertGreater(reward, 0.0)

    def test_grasped_and_at_target_gets_place_bonus(self):
        state = _fake_state(
            ee_pos=[10, 100, 5],
            object_pos=[10, 100, 5],
            target_pos=[10, 100, 0],
            object_grasped=True,
            gripper_state=False,
        )
        reward = self.r.compute(state)
        self.assertGreater(reward, 5.0)

    def test_reset_clears_state(self):
        self.r._prev_grasped = True
        self.r.reset()
        self.assertFalse(self.r._prev_grasped)


# ═══════════════════════════════════════════════
#  TestVisionReward
# ═══════════════════════════════════════════════


class TestVisionReward(unittest.TestCase):
    def setUp(self):
        from app.models.rl.rewards import VisionReward

        self.r = VisionReward(center_reward=1.0, no_detection_penalty=-0.5)

    def _make_detection(self, found, cx=0.5, cy=0.5):
        det = MagicMock()
        det.found = found
        det.cx = cx
        det.cy = cy
        return det

    def test_no_detection_penalty(self):
        state = _fake_state(detection=None)
        reward = self.r.compute(state)
        self.assertAlmostEqual(reward, -0.5)

    def test_detection_not_found_penalty(self):
        state = _fake_state(detection=self._make_detection(False))
        reward = self.r.compute(state)
        self.assertAlmostEqual(reward, -0.5)

    def test_centered_detection_high_reward(self):
        state = _fake_state(detection=self._make_detection(True, cx=0.5, cy=0.5))
        reward = self.r.compute(state)
        self.assertGreater(reward, 1.0)

    def test_off_center_lower_reward(self):
        center = _fake_state(detection=self._make_detection(True, cx=0.5, cy=0.5))
        off = _fake_state(detection=self._make_detection(True, cx=0.8, cy=0.2))
        self.assertGreater(self.r.compute(center), self.r.compute(off))


# ═══════════════════════════════════════════════
#  TestCompositeReward
# ═══════════════════════════════════════════════


class TestCompositeReward(unittest.TestCase):
    def test_empty_composite_zero(self):
        from app.models.rl.rewards import CompositeReward

        r = CompositeReward()
        self.assertAlmostEqual(r.compute(_fake_state()), 0.0)

    def test_single_component(self):
        from app.models.rl.rewards import CompositeReward, DistanceReward

        r = CompositeReward([(2.0, DistanceReward(scale=1.0, success_bonus=0.0))])
        base = DistanceReward(scale=1.0, success_bonus=0.0)
        state = _fake_state()
        self.assertAlmostEqual(r.compute(state), 2.0 * base.compute(state), places=5)

    def test_add_component(self):
        from app.models.rl.rewards import CompositeReward, DistanceReward, SmoothMotionReward

        r = CompositeReward()
        r.add(DistanceReward(), 1.0)
        r.add(SmoothMotionReward(), 0.1)
        self.assertEqual(len(r._components), 2)

    def test_reset_calls_stateful(self):
        from app.models.rl.rewards import CompositeReward, PickPlaceReward

        pp = PickPlaceReward()
        pp._prev_grasped = True
        r = CompositeReward([(1.0, pp)])
        r.reset()
        self.assertFalse(pp._prev_grasped)


# ═══════════════════════════════════════════════
#  TestRobotArmEnv
# ═══════════════════════════════════════════════


class TestRobotArmEnv(unittest.TestCase):
    def setUp(self):
        from app.models.rl.environment import RobotArmEnv

        self.env = RobotArmEnv()

    def test_reset_returns_correct_obs_shape(self):
        obs, info = self.env.reset()
        self.assertEqual(obs.shape, (18,))
        self.assertIsInstance(info, dict)

    def test_obs_dtype_float32(self):
        obs, _ = self.env.reset()
        self.assertEqual(obs.dtype, np.float32)

    def test_obs_values_normalized(self):
        obs, _ = self.env.reset()
        # Все значения должны быть разумными (не inf/nan)
        self.assertTrue(np.all(np.isfinite(obs)))

    def test_step_returns_5_tuple(self):
        self.env.reset()
        action = np.zeros(7)
        result = self.env.step(action)
        self.assertEqual(len(result), 5)

    def test_step_obs_shape(self):
        self.env.reset()
        obs, reward, terminated, truncated, info = self.env.step(np.zeros(7))
        self.assertEqual(obs.shape, (18,))

    def test_step_reward_is_float(self):
        self.env.reset()
        _, reward, _, _, _ = self.env.step(np.zeros(7))
        self.assertIsInstance(reward, float)

    def test_step_info_has_distance(self):
        self.env.reset()
        _, _, _, _, info = self.env.step(np.zeros(7))
        self.assertIn("distance_mm", info)
        self.assertIn("success", info)
        self.assertIn("steps", info)

    def test_action_clipped_to_valid_range(self):
        self.env.reset()
        big_action = np.full(7, 100.0)
        obs, _, _, _, _ = self.env.step(big_action)
        self.assertTrue(np.all(np.isfinite(obs)))

    def test_multiple_resets(self):
        for _ in range(5):
            obs, _ = self.env.reset()
            self.assertEqual(obs.shape, (18,))

    def test_steps_increment(self):
        self.env.reset()
        for i in range(5):
            _, _, _, _, info = self.env.step(np.zeros(7))
        self.assertEqual(info["steps"], 5)

    def test_truncated_after_max_steps(self):
        from app.models.rl.environment import RobotArmConfig, RobotArmEnv

        env = RobotArmEnv(config=RobotArmConfig(max_steps=3, randomize_target=False))
        env.reset()
        for _ in range(3):
            _, _, terminated, truncated, _ = env.step(np.zeros(7))
        self.assertTrue(truncated)

    def test_obs_dim_property(self):
        self.assertEqual(self.env.obs_dim, 18)

    def test_action_dim_property(self):
        self.assertEqual(self.env.action_dim, 7)

    def test_render_returns_string(self):
        self.env.reset()
        s = self.env.render()
        self.assertIsInstance(s, str)
        self.assertIn("EE=", s)

    def test_forward_kinematics_home(self):
        angles = np.zeros(6)
        ee = self.env._forward_kinematics(angles)
        self.assertEqual(ee.shape, (3,))
        self.assertTrue(np.all(np.isfinite(ee)))


# ═══════════════════════════════════════════════
#  TestReplayBuffer
# ═══════════════════════════════════════════════


class TestReplayBuffer(unittest.TestCase):
    def setUp(self):
        from app.models.rl.base_agent import ReplayBuffer, Transition

        self.buf = ReplayBuffer(capacity=100)
        self.Transition = Transition

    def _make_transition(self, r=0.0):
        return self.Transition(
            obs=np.zeros(18),
            action=np.zeros(7),
            reward=r,
            next_obs=np.zeros(18),
            done=False,
        )

    def test_empty_buffer(self):
        self.assertEqual(len(self.buf), 0)

    def test_push_adds_element(self):
        self.buf.push(self._make_transition())
        self.assertEqual(len(self.buf), 1)

    def test_push_respects_capacity(self):
        for _ in range(150):
            self.buf.push(self._make_transition())
        self.assertEqual(len(self.buf), 100)

    def test_sample_returns_correct_size(self):
        for _ in range(50):
            self.buf.push(self._make_transition())
        batch = self.buf.sample(10)
        self.assertEqual(len(batch), 10)

    def test_is_ready_after_push(self):
        self.buf.push(self._make_transition())
        self.assertTrue(self.buf.is_ready)

    def test_circular_overwrite(self):
        for i in range(150):
            self.buf.push(self._make_transition(r=float(i)))
        self.assertEqual(len(self.buf), 100)


# ═══════════════════════════════════════════════
#  TestDQNAgent (без PyTorch)
# ═══════════════════════════════════════════════


class TestDQNAgent(unittest.TestCase):
    def setUp(self):
        from app.models.rl.dqn_agent import N_ACTIONS, DQNAgent, _action_to_continuous

        self.DQNAgent = DQNAgent
        self.N_ACTIONS = N_ACTIONS
        self._action_to_continuous = _action_to_continuous

    def test_n_actions_correct(self):
        self.assertEqual(self.N_ACTIONS, 32)

    def test_action_to_continuous_shape(self):
        for i in range(self.N_ACTIONS):
            vec = self._action_to_continuous(i)
            self.assertEqual(vec.shape, (7,))

    def test_action_to_continuous_range(self):
        for i in range(self.N_ACTIONS):
            vec = self._action_to_continuous(i)
            self.assertTrue(np.all(np.abs(vec) <= 1.01))

    def test_gripper_actions(self):
        # Последние 2 действия — gripper
        open_vec = self._action_to_continuous(30)
        close_vec = self._action_to_continuous(31)
        self.assertNotEqual(open_vec[6], close_vec[6])

    def test_agent_init(self):
        from app.models.rl.base_agent import TrainingConfig

        agent = self.DQNAgent(obs_dim=18, config=TrainingConfig(max_episodes=10))
        self.assertEqual(agent.obs_dim, 18)
        self.assertEqual(agent.action_dim, self.N_ACTIONS)

    def test_select_action_without_torch_returns_array(self):
        from app.models.rl.base_agent import TrainingConfig

        agent = self.DQNAgent(obs_dim=18, config=TrainingConfig())
        obs = np.zeros(18)
        action = agent.select_action(obs, explore=True)
        self.assertEqual(action.shape, (7,))

    def test_update_without_buffer_returns_zero(self):
        from app.models.rl.base_agent import TrainingConfig

        agent = self.DQNAgent(obs_dim=18, config=TrainingConfig())
        loss = agent.update()
        self.assertEqual(loss, 0.0)

    def test_epsilon_starts_at_one(self):
        from app.models.rl.base_agent import TrainingConfig

        agent = self.DQNAgent(obs_dim=18, config=TrainingConfig(epsilon_start=1.0))
        self.assertAlmostEqual(agent.epsilon, 1.0)

    def test_epsilon_decreases_with_steps(self):
        from app.models.rl.base_agent import TrainingConfig

        agent = self.DQNAgent(
            obs_dim=18, config=TrainingConfig(epsilon_start=1.0, epsilon_end=0.0, epsilon_decay=100)
        )
        agent._total_steps = 50
        self.assertLess(agent.epsilon, 1.0)
        agent._total_steps = 100
        self.assertAlmostEqual(agent.epsilon, 0.0)


# ═══════════════════════════════════════════════
#  TestPPOAgent (без PyTorch)
# ═══════════════════════════════════════════════


class TestPPOAgent(unittest.TestCase):
    def test_agent_init(self):
        from app.models.rl.base_agent import TrainingConfig
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7, config=TrainingConfig())
        self.assertEqual(agent.obs_dim, 18)
        self.assertEqual(agent.action_dim, 7)
        self.assertEqual(agent.name, "PPOAgent")

    def test_select_action_returns_correct_shape(self):
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7)
        obs = np.zeros(18)
        action = agent.select_action(obs, explore=True)
        self.assertEqual(action.shape, (7,))

    def test_update_empty_rollout_returns_zero(self):
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7)
        loss = agent.update()
        self.assertEqual(loss, 0.0)

    def test_rollout_buffer_accumulates(self):
        from app.models.rl.base_agent import TrainingConfig, Transition
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7, config=TrainingConfig(n_steps=100))
        obs = np.zeros(18)
        action = agent.select_action(obs)
        t = Transition(obs, action, 1.0, np.zeros(18), False)
        agent._observe(t)
        self.assertEqual(len(agent._rollout), 1)

    def test_compute_gae_shape(self):
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7)
        rewards = np.array([1.0, 2.0, 3.0, 0.0])
        values = np.array([0.5, 1.0, 1.5, 0.0])
        dones = np.array([0.0, 0.0, 0.0, 1.0])
        adv = agent._compute_gae(rewards, values, dones)
        self.assertEqual(adv.shape, (4,))
        self.assertTrue(np.all(np.isfinite(adv)))

    def test_stop_training(self):
        from app.models.rl.ppo_agent import PPOAgent

        agent = PPOAgent(obs_dim=18, action_dim=7)
        agent.stop_training()
        self.assertTrue(agent._stop_requested)


# ═══════════════════════════════════════════════
#  TestRLTrainingService
# ═══════════════════════════════════════════════


class TestRLTrainingService(unittest.TestCase):
    def setUp(self):
        from app.services.rl_training_service import RLTrainingService

        self.svc = RLTrainingService(checkpoint_dir="/tmp/test_rl_checkpoints")

    def test_initial_status_not_training(self):
        status = self.svc.get_status()
        self.assertFalse(status.is_training)

    def test_initial_status_no_agent(self):
        status = self.svc.get_status()
        self.assertEqual(status.agent_type, "")

    def test_setup_dqn_sets_agent_type(self):
        self.svc.setup_dqn()
        status = self.svc.get_status()
        self.assertEqual(status.agent_type, "DQN")

    def test_setup_ppo_sets_agent_type(self):
        self.svc.setup_ppo()
        status = self.svc.get_status()
        self.assertEqual(status.agent_type, "PPO")

    def test_setup_dqn_creates_env(self):
        self.svc.setup_dqn()
        self.assertIsNotNone(self.svc._env)

    def test_setup_ppo_creates_env(self):
        self.svc.setup_ppo()
        self.assertIsNotNone(self.svc._env)

    def test_start_without_setup_returns_false(self):
        from app.services.rl_training_service import RLTrainingService

        svc = RLTrainingService(checkpoint_dir="/tmp/test_rl2")
        result = svc.start_training()
        self.assertFalse(result)

    def test_setup_chaining(self):
        result = self.svc.setup_ppo()
        self.assertIs(result, self.svc)

    def test_setup_dqn_chaining(self):
        result = self.svc.setup_dqn()
        self.assertIs(result, self.svc)

    def test_stop_when_not_running(self):
        self.svc.setup_dqn()
        self.svc.stop_training()  # Should not raise
        self.assertFalse(self.svc.get_status().is_training)

    def test_reward_preset_reach(self):
        from app.services.rl_training_service import RewardPreset, TrainingMode

        self.svc.setup_with_reward_preset(RewardPreset.REACH, TrainingMode.DQN)
        self.assertIsNotNone(self.svc._env)

    def test_reward_preset_pick_place(self):
        from app.services.rl_training_service import RewardPreset, TrainingMode

        self.svc.setup_with_reward_preset(RewardPreset.PICK_PLACE, TrainingMode.PPO)
        self.assertIsNotNone(self.svc._agent)

    def test_curriculum_setup(self):
        from app.services.rl_training_service import CurriculumStage

        stages = [
            CurriculumStage("easy", 10.0, 80.0, 40.0, 10),
            CurriculumStage("hard", 10.0, 200.0, 20.0, 10),
        ]
        self.svc.setup_curriculum(stages)
        self.assertEqual(len(self.svc._curriculum_stages), 2)

    def test_on_episode_callback(self):
        cb = MagicMock()
        self.svc.on_episode(cb)
        self.assertIs(self.svc._on_episode, cb)

    def test_on_complete_callback(self):
        cb = MagicMock()
        self.svc.on_complete(cb)
        self.assertIs(self.svc._on_complete, cb)

    def test_get_status_to_dict(self):
        self.svc.setup_ppo()
        d = self.svc.get_status().to_dict()
        for key in ("mode", "agent_type", "episode", "is_training", "best_reward"):
            self.assertIn(key, d)

    def test_save_checkpoint_without_agent_returns_empty(self):
        from app.services.rl_training_service import RLTrainingService

        svc = RLTrainingService(checkpoint_dir="/tmp/test_rl3")
        result = svc.save_checkpoint()
        self.assertEqual(result, "")

    def test_load_checkpoint_nonexistent_returns_false(self):
        self.svc.setup_dqn()
        result = self.svc.load_checkpoint("/nonexistent/path.pt")
        self.assertFalse(result)

    def test_run_demo_without_agent_returns_empty(self):
        from app.services.rl_training_service import RLTrainingService

        svc = RLTrainingService(checkpoint_dir="/tmp/test_rl4")
        result = svc.run_demo(episodes=1)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
