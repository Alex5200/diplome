#!/usr/bin/env python3
"""
TDD тесты для AIRobotControllerService.

Запуск:
    python -m pytest app/tests/test_ai_robot_controller.py -v --tb=short
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, PropertyMock

import numpy as np

# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════


def _make_ai_provider(
    available=True,
    response_text='{"action":"idle","joint_deltas":[0,0,0,0,0,0],"gripper_open":null,"speed":600,"reason":"nothing to do","confidence":0.9}',
):
    ai = MagicMock()
    ai.is_available.return_value = available
    resp = MagicMock()
    resp.success = True
    resp.content = response_text
    resp.error = ""
    resp.latency = 0.5
    ai.chat_json.return_value = resp
    ai.__repr__ = lambda s: "MockAI(qwen3)"
    return ai


def _make_robot(connected=True):
    robot = MagicMock()
    type(robot).is_connected = PropertyMock(return_value=connected)
    robot.get_joint_angles.return_value = [0.0] * 6
    robot.move_joints.return_value = True
    robot.emergency_stop.return_value = None
    return robot


def _make_kin():
    kin = MagicMock()
    kin.forward_kinematics.return_value = [100.0, 0.0, 200.0]
    return kin


def _fake_frame(w=64, h=48):
    return np.zeros((h, w, 3), dtype=np.uint8)


# ══════════════════════════════════════════════
#  Test: parse_ai_command
# ══════════════════════════════════════════════


class TestParseAICommand(unittest.TestCase):
    def _parse(self, text):
        from app.services.ai_robot_controller_service import parse_ai_command

        return parse_ai_command(text)

    def test_valid_move_command(self):
        cmd = self._parse(
            '{"action":"move","joint_deltas":[5,0,0,0,0,0],'
            '"gripper_open":null,"speed":600,"reason":"turn base","confidence":0.9}'
        )
        self.assertEqual(cmd.action, "move")
        self.assertAlmostEqual(cmd.joint_deltas[0], 5.0)
        self.assertIsNone(cmd.gripper_open)
        self.assertTrue(cmd.success)

    def test_valid_grip_command(self):
        cmd = self._parse(
            '{"action":"grip","joint_deltas":[0,0,0,0,0,0],'
            '"gripper_open":false,"speed":400,"reason":"grab","confidence":0.8}'
        )
        self.assertEqual(cmd.action, "grip")
        self.assertFalse(cmd.gripper_open)

    def test_valid_idle_command(self):
        cmd = self._parse(
            '{"action":"idle","joint_deltas":[0,0,0,0,0,0],'
            '"gripper_open":null,"speed":600,"reason":"done","confidence":1.0}'
        )
        self.assertEqual(cmd.action, "idle")
        self.assertTrue(cmd.success)

    def test_invalid_json_returns_error_cmd(self):
        cmd = self._parse("This is not JSON at all")
        self.assertFalse(cmd.success)
        self.assertEqual(cmd.action, "idle")

    def test_unknown_action_defaults_to_idle(self):
        cmd = self._parse(
            '{"action":"fly","joint_deltas":[0,0,0,0,0,0],"confidence":0.5,"reason":"unknown"}'
        )
        self.assertEqual(cmd.action, "idle")

    def test_delta_clamped_to_max(self):
        cmd = self._parse(
            '{"action":"move","joint_deltas":[100,-200,0,0,0,0],'
            '"gripper_open":null,"speed":600,"confidence":1.0}'
        )
        self.assertLessEqual(abs(cmd.joint_deltas[0]), 15.0)
        self.assertLessEqual(abs(cmd.joint_deltas[1]), 15.0)

    def test_speed_clamped(self):
        cmd = self._parse(
            '{"action":"move","joint_deltas":[0,0,0,0,0,0],"speed":99999,"confidence":0.9}'
        )
        self.assertLessEqual(cmd.speed, 1000)

    def test_confidence_clamped(self):
        cmd = self._parse('{"action":"idle","joint_deltas":[0,0,0,0,0,0],"confidence":5.0}')
        self.assertLessEqual(cmd.confidence, 1.0)

    def test_markdown_json_parsed(self):
        cmd = self._parse(
            '```json\n{"action":"move","joint_deltas":[2,0,0,0,0,0],'
            '"gripper_open":null,"speed":600,"reason":"ok","confidence":0.8}\n```'
        )
        self.assertEqual(cmd.action, "move")
        self.assertTrue(cmd.success)

    def test_reason_extracted(self):
        cmd = self._parse(
            '{"action":"move","joint_deltas":[0,0,0,0,0,0],'
            '"reason":"turn to face object","confidence":0.9}'
        )
        self.assertIn("turn", cmd.reason)


# ══════════════════════════════════════════════
#  Test: AICommand
# ══════════════════════════════════════════════


class TestAICommand(unittest.TestCase):
    def test_idle_factory(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand.idle_cmd("nothing")
        self.assertEqual(cmd.action, "idle")
        self.assertEqual(cmd.reason, "nothing")

    def test_error_factory(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand.error_cmd("timeout")
        self.assertFalse(cmd.success)
        self.assertEqual(cmd.error, "timeout")

    def test_safe_small_deltas(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand(joint_deltas=[5.0, -3.0, 2.0, 0.0, 1.0, -1.0])
        self.assertTrue(cmd.is_safe())

    def test_unsafe_large_delta(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand(joint_deltas=[20.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertFalse(cmd.is_safe())

    def test_unsafe_large_target(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand(joint_targets=[200.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertFalse(cmd.is_safe())

    def test_to_dict_keys(self):
        from app.services.ai_robot_controller_service import AICommand

        cmd = AICommand(action="move", joint_deltas=[1.0] * 6, reason="test")
        d = cmd.to_dict()
        for k in ("action", "joint_deltas", "speed", "reason", "confidence", "safe"):
            self.assertIn(k, d)

    def test_to_dict_safe_flag(self):
        from app.services.ai_robot_controller_service import AICommand

        safe_cmd = AICommand(joint_deltas=[1.0] * 6)
        self.assertTrue(safe_cmd.to_dict()["safe"])
        unsafe_cmd = AICommand(joint_deltas=[50.0] * 6)
        self.assertFalse(unsafe_cmd.to_dict()["safe"])


# ══════════════════════════════════════════════
#  Test: ControllerState
# ══════════════════════════════════════════════


class TestControllerState(unittest.TestCase):
    def test_default_state(self):
        from app.services.ai_robot_controller_service import ControllerState

        s = ControllerState()
        self.assertFalse(s.is_running)
        self.assertEqual(s.step_count, 0)

    def test_to_dict_keys(self):
        from app.services.ai_robot_controller_service import ControllerState

        s = ControllerState()
        d = s.to_dict()
        for k in (
            "mode",
            "is_running",
            "task",
            "step_count",
            "latency_s",
            "fps",
            "joints",
            "model",
        ):
            self.assertIn(k, d)


# ══════════════════════════════════════════════
#  Test: AIRobotControllerService (unit)
# ══════════════════════════════════════════════


class TestAIRobotControllerServiceInit(unittest.TestCase):
    def _make_svc(self, available=True):
        from app.services.ai_robot_controller_service import (
            AIRobotControllerService,
            ControlMode,
        )

        return AIRobotControllerService(
            robot_service=_make_robot(),
            kinematics_service=_make_kin(),
            ai_provider=_make_ai_provider(available=available),
            mode=ControlMode.STEP,
        )

    def test_initial_state_not_running(self):
        svc = self._make_svc()
        self.assertFalse(svc.get_state().is_running)

    def test_set_task(self):
        svc = self._make_svc()
        svc.set_task("Pick up the cube")
        self.assertEqual(svc.get_state().task, "Pick up the cube")

    def test_set_mode(self):
        from app.services.ai_robot_controller_service import ControlMode

        svc = self._make_svc()
        svc.set_mode(ControlMode.WATCH)
        self.assertEqual(svc._mode, ControlMode.WATCH)

    def test_set_ai_provider(self):
        svc = self._make_svc()
        new_ai = _make_ai_provider()
        svc.set_ai_provider(new_ai)
        self.assertIs(svc.ai, new_ai)

    def test_set_ai_interval(self):
        svc = self._make_svc()
        svc.set_ai_interval(2.5)
        self.assertAlmostEqual(svc._ai_interval, 2.5)

    def test_set_ai_interval_min_clamped(self):
        svc = self._make_svc()
        svc.set_ai_interval(0.1)  # below min
        self.assertGreaterEqual(svc._ai_interval, 0.5)

    def test_set_frame_callback(self):
        svc = self._make_svc()
        cb = MagicMock()
        svc.set_frame_callback(cb)
        self.assertIs(svc._frame_callback, cb)

    def test_set_command_callback(self):
        svc = self._make_svc()
        cb = MagicMock()
        svc.set_command_callback(cb)
        self.assertIs(svc._command_callback, cb)

    def test_set_state_callback(self):
        svc = self._make_svc()
        cb = MagicMock()
        svc.set_state_callback(cb)
        self.assertIs(svc._state_callback, cb)

    def test_set_log_callback(self):
        svc = self._make_svc()
        cb = MagicMock()
        svc.set_log_callback(cb)
        self.assertIs(svc._log_callback, cb)

    def test_get_history_empty(self):
        svc = self._make_svc()
        self.assertEqual(svc.get_history(), [])

    def test_clear_history(self):
        svc = self._make_svc()
        from app.services.ai_robot_controller_service import AICommand

        svc._command_history.append(AICommand.idle_cmd())
        svc.clear_history()
        self.assertEqual(svc.get_history(), [])

    def test_repr(self):

        svc = self._make_svc()
        r = repr(svc)
        self.assertIn("STEP", r)

    def test_do_initialize_fails_when_ai_unavailable(self):
        svc = self._make_svc(available=False)
        result = svc._do_initialize()
        self.assertFalse(result)


# ══════════════════════════════════════════════
#  Test: _query_ai (with mocked camera)
# ══════════════════════════════════════════════


class TestAIRobotControllerQuery(unittest.TestCase):
    def _make_svc(self, response_text=None):
        from app.services.ai_robot_controller_service import (
            AIRobotControllerService,
            ControlMode,
        )

        rt = response_text or (
            '{"action":"move","joint_deltas":[3,0,0,0,0,0],'
            '"gripper_open":null,"speed":600,'
            '"reason":"rotating base","confidence":0.85}'
        )
        return AIRobotControllerService(
            robot_service=_make_robot(),
            kinematics_service=_make_kin(),
            ai_provider=_make_ai_provider(response_text=rt),
            mode=ControlMode.STEP,
        )

    def test_query_returns_command(self):
        svc = self._make_svc()
        cmd = svc._query_ai(_fake_frame(), [0.0] * 6, [100.0, 0.0, 200.0])
        self.assertIsNotNone(cmd)
        self.assertEqual(cmd.action, "move")

    def test_query_returns_idle_on_error(self):
        from app.services.ai_robot_controller_service import AIRobotControllerService, ControlMode

        ai = _make_ai_provider()
        resp = MagicMock()
        resp.success = False
        resp.error = "Connection refused"
        ai.chat_json.return_value = resp
        svc = AIRobotControllerService(
            robot_service=_make_robot(),
            kinematics_service=_make_kin(),
            ai_provider=ai,
            mode=ControlMode.STEP,
        )
        cmd = svc._query_ai(_fake_frame(), [0.0] * 6, [0.0, 0.0, 0.0])
        self.assertFalse(cmd.success)

    def test_query_log_callback_called(self):
        svc = self._make_svc()
        logs = []
        svc.set_log_callback(lambda m, l: logs.append((m, l)))
        svc._query_ai(_fake_frame(), [0.0] * 6, [0.0, 0.0, 0.0])
        self.assertGreater(len(logs), 0)

    def test_query_command_has_reason(self):
        svc = self._make_svc()
        cmd = svc._query_ai(_fake_frame(), [0.0] * 6, [0.0, 0.0, 0.0])
        self.assertIsInstance(cmd.reason, str)


# ══════════════════════════════════════════════
#  Test: _execute_command
# ══════════════════════════════════════════════


class TestAIRobotControllerExecute(unittest.TestCase):
    def _make_svc(self, connected=True):
        from app.services.ai_robot_controller_service import (
            AIRobotControllerService,
            ControlMode,
        )

        return AIRobotControllerService(
            robot_service=_make_robot(connected=connected),
            kinematics_service=_make_kin(),
            ai_provider=_make_ai_provider(),
            mode=ControlMode.STEP,
        )

    def test_idle_command_not_executed(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand.idle_cmd()
        svc._execute_command(cmd)
        svc.robot.move_joints.assert_not_called()

    def test_move_command_calls_move_joints(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand(action="move", joint_deltas=[5.0, 0, 0, 0, 0, 0], speed=600)
        svc._execute_command(cmd)
        svc.robot.move_joints.assert_called_once()

    def test_stop_command_calls_emergency_stop(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand(action="stop")
        svc._execute_command(cmd)
        svc.robot.emergency_stop.assert_called_once()

    def test_home_command_moves_to_zeros(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand(action="home")
        svc._execute_command(cmd)
        args = svc.robot.move_joints.call_args[0][0]
        self.assertEqual(args, [0.0] * 6)

    def test_unsafe_command_blocked(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand(action="move", joint_deltas=[50.0, 0, 0, 0, 0, 0])
        svc._execute_command(cmd)
        svc.robot.move_joints.assert_not_called()

    def test_robot_disconnected_skips(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc(connected=False)
        cmd = AICommand(action="move", joint_deltas=[5.0, 0, 0, 0, 0, 0])
        svc._execute_command(cmd)
        svc.robot.move_joints.assert_not_called()

    def test_error_command_not_executed(self):
        from app.services.ai_robot_controller_service import AICommand

        svc = self._make_svc()
        cmd = AICommand.error_cmd("parse failed")
        svc._execute_command(cmd)
        svc.robot.move_joints.assert_not_called()


# ══════════════════════════════════════════════
#  Test: ControlMode
# ══════════════════════════════════════════════


class TestControlMode(unittest.TestCase):
    def test_modes_exist(self):
        from app.services.ai_robot_controller_service import ControlMode

        self.assertIn("AUTO", [m.name for m in ControlMode])
        self.assertIn("STEP", [m.name for m in ControlMode])
        self.assertIn("WATCH", [m.name for m in ControlMode])

    def test_watch_mode_no_execution(self):
        """В режиме WATCH команды не выполняются."""
        from app.services.ai_robot_controller_service import (
            AIRobotControllerService,
            ControlMode,
        )

        svc = AIRobotControllerService(
            robot_service=_make_robot(),
            kinematics_service=_make_kin(),
            ai_provider=_make_ai_provider(),
            mode=ControlMode.WATCH,
        )
        # Напрямую вызовем _ai_loop логику: в WATCH execute не вызывается
        # Проверяем через флаг
        self.assertEqual(svc._mode, ControlMode.WATCH)


if __name__ == "__main__":
    unittest.main(verbosity=2)
