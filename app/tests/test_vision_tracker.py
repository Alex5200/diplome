#!/usr/bin/env python3
"""
TDD тесты для VisionTrackerService и ML Model Manager.

Запуск:
    python -m pytest app/tests/test_vision_tracker.py -v
    python -m pytest app/tests/test_vision_tracker.py -v --tb=short
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

import numpy as np

# ═══════════════════════════════════════════════
#  Helpers / Stubs
# ═══════════════════════════════════════════════


def _fake_frame(w: int = 64, h: int = 48) -> np.ndarray:
    """Создать тестовый RGB-кадр."""
    return np.zeros((h, w, 3), dtype=np.uint8)


def _make_robot_service(connected: bool = True):
    robot = MagicMock()
    robot.is_connected = connected
    robot.get_joint_angles.return_value = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    robot.move_joints.return_value = True
    return robot


def _make_kin_service():
    kin = MagicMock()
    kin.solve_ik.return_value = [0.0] * 6
    return kin


def _make_ai_provider(found: bool = True, cx: float = 0.5, cy: float = 0.5):
    from app.services.ai_provider import AIProvider

    provider = MagicMock(spec=AIProvider)
    provider.is_available.return_value = True

    response = MagicMock()
    response.success = True
    response.latency = 0.1
    response.content = '{"found": true, "bbox": [0.4, 0.4, 0.6, 0.6]}'
    response.json_data = (
        {
            "found": found,
            "bbox": [cx - 0.1, cy - 0.1, cx + 0.1, cy + 0.1],
        }
        if found
        else {"found": False}
    )
    provider.chat_json.return_value = response

    return provider


# ═══════════════════════════════════════════════
#  SimplePID Tests
# ═══════════════════════════════════════════════


class TestSimplePID(unittest.TestCase):
    def setUp(self):
        from app.services.vision_tracker_service import SimplePID

        self.pid = SimplePID(kp=1.0, ki=0.0, kd=0.0, output_limit=100.0)

    def test_zero_error_returns_zero(self):
        """Нулевая ошибка → нулевой выход."""
        out = self.pid.update(0.0)
        self.assertAlmostEqual(out, 0.0, places=5)

    def test_proportional_term(self):
        """Kp=1, ki=kd=0: выход ≈ ошибка."""
        out = self.pid.update(10.0)
        self.assertAlmostEqual(out, 10.0, delta=1.0)

    def test_output_limited(self):
        """Выход ограничен output_limit."""
        from app.services.vision_tracker_service import SimplePID

        pid = SimplePID(kp=1.0, ki=0.0, kd=0.0, output_limit=5.0)
        out = pid.update(100.0)
        self.assertLessEqual(out, 5.0)

    def test_negative_output_limited(self):
        """Отрицательный выход ограничен -output_limit."""
        from app.services.vision_tracker_service import SimplePID

        pid = SimplePID(kp=1.0, ki=0.0, kd=0.0, output_limit=5.0)
        out = pid.update(-100.0)
        self.assertGreaterEqual(out, -5.0)

    def test_reset_clears_integral(self):
        """После reset интеграл обнуляется."""
        from app.services.vision_tracker_service import SimplePID

        pid = SimplePID(kp=1.0, ki=1.0, kd=0.0, output_limit=100.0)
        pid.update(5.0)
        pid.update(5.0)
        pid.reset()
        # После reset интеграл = 0, следующий update только пропорциональный
        out = pid.update(1.0)
        self.assertAlmostEqual(out, 1.0, delta=0.5)

    def test_integral_accumulates(self):
        """Интеграл накапливается при ki > 0."""
        from app.services.vision_tracker_service import SimplePID

        pid = SimplePID(kp=0.0, ki=1.0, kd=0.0, output_limit=100.0)
        out1 = pid.update(1.0)
        out2 = pid.update(1.0)
        self.assertGreater(abs(out2), abs(out1))


# ═══════════════════════════════════════════════
#  TrackingTarget Tests
# ═══════════════════════════════════════════════


class TestTrackingTarget(unittest.TestCase):
    def test_default_not_found(self):
        from app.services.vision_tracker_service import TrackingTarget

        t = TrackingTarget()
        self.assertFalse(t.found)
        self.assertEqual(t.cx, 0.5)
        self.assertEqual(t.cy, 0.5)

    def test_found_with_coords(self):
        from app.services.vision_tracker_service import TrackingTarget

        t = TrackingTarget(found=True, cx=0.7, cy=0.3, label="ball")
        self.assertTrue(t.found)
        self.assertEqual(t.label, "ball")
        self.assertAlmostEqual(t.cx, 0.7)
        self.assertAlmostEqual(t.cy, 0.3)


# ═══════════════════════════════════════════════
#  TrackerState Tests
# ═══════════════════════════════════════════════


class TestTrackerState(unittest.TestCase):
    def test_default_state(self):
        from app.services.vision_tracker_service import TrackerState

        s = TrackerState()
        self.assertFalse(s.is_tracking)
        self.assertEqual(s.target_label, "red ball")
        self.assertEqual(len(s.current_angles), 6)

    def test_state_is_mutable(self):
        from app.services.vision_tracker_service import TrackerState

        s = TrackerState()
        s.is_tracking = True
        s.target_label = "cup"
        self.assertTrue(s.is_tracking)
        self.assertEqual(s.target_label, "cup")


# ═══════════════════════════════════════════════
#  VisionTrackerService Tests
# ═══════════════════════════════════════════════


class TestVisionTrackerServiceInit(unittest.TestCase):
    def setUp(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.robot = _make_robot_service()
        self.kin = _make_kin_service()
        self.ai = _make_ai_provider()
        self.svc = VisionTrackerService(self.robot, self.kin, self.ai)

    def test_initial_state_not_tracking(self):
        state = self.svc.get_tracker_state()
        self.assertFalse(state.is_tracking)

    def test_default_target_label(self):
        state = self.svc.get_tracker_state()
        self.assertEqual(state.target_label, "red ball")

    def test_configure_changes_target(self):
        self.svc.configure(target_label="blue cube")
        state = self.svc.get_tracker_state()
        self.assertEqual(state.target_label, "blue cube")

    def test_configure_changes_camera_id(self):
        self.svc.configure(camera_id=1)
        self.assertEqual(self.svc._camera_id, 1)

    def test_set_ai_provider(self):
        new_ai = _make_ai_provider(found=False)
        self.svc.set_ai_provider(new_ai)
        self.assertIs(self.svc.ai, new_ai)

    def test_set_target_updates_label(self):
        self.svc.set_target("red apple")
        state = self.svc.get_tracker_state()
        self.assertEqual(state.target_label, "red apple")

    def test_frame_callback_setter(self):
        cb = MagicMock()
        self.svc.set_frame_callback(cb)
        self.assertIs(self.svc._frame_callback, cb)

    def test_state_callback_setter(self):
        cb = MagicMock()
        self.svc.set_state_callback(cb)
        self.assertIs(self.svc._state_callback, cb)


class TestVisionTrackerServiceDetect(unittest.TestCase):
    def setUp(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.robot = _make_robot_service()
        self.kin = _make_kin_service()
        self.ai = _make_ai_provider(found=True, cx=0.7, cy=0.3)
        self.svc = VisionTrackerService(self.robot, self.kin, self.ai)

    def test_detect_object_returns_found(self):
        frame = _fake_frame()
        result = self.svc._detect_object(frame)
        self.assertTrue(result.found)

    def test_detect_object_cx_correct(self):
        frame = _fake_frame()
        result = self.svc._detect_object(frame)
        self.assertAlmostEqual(result.cx, 0.7, delta=0.05)

    def test_detect_object_not_found(self):
        from app.services.vision_tracker_service import VisionTrackerService

        ai = _make_ai_provider(found=False)
        svc = VisionTrackerService(self.robot, self.kin, ai)
        result = svc._detect_object(_fake_frame())
        self.assertFalse(result.found)

    def test_detect_ai_error_returns_not_found(self):
        from app.services.vision_tracker_service import VisionTrackerService

        ai = MagicMock()
        ai.is_available.return_value = True
        resp = MagicMock()
        resp.success = False
        resp.error = "timeout"
        ai.chat_json.return_value = resp
        svc = VisionTrackerService(self.robot, self.kin, ai)
        result = svc._detect_object(_fake_frame())
        self.assertFalse(result.found)


class TestVisionTrackerServiceClamp(unittest.TestCase):
    def test_clamp_within_range(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.assertEqual(VisionTrackerService._clamp(50.0), 50.0)

    def test_clamp_above_limit(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.assertEqual(VisionTrackerService._clamp(200.0), 150.0)

    def test_clamp_below_limit(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.assertEqual(VisionTrackerService._clamp(-200.0), -150.0)

    def test_clamp_custom_limit(self):
        from app.services.vision_tracker_service import VisionTrackerService

        self.assertEqual(VisionTrackerService._clamp(50.0, limit=30.0), 30.0)


# ═══════════════════════════════════════════════
#  ML Model Manager Tests
# ═══════════════════════════════════════════════


class TestDetectionResult(unittest.TestCase):
    def test_not_found_factory(self):
        from app.models.ml_model_manager import DetectionResult

        r = DetectionResult.not_found("test_model")
        self.assertFalse(r.found)
        self.assertEqual(r.model_name, "test_model")

    def test_to_dict_keys(self):
        from app.models.ml_model_manager import DetectionResult

        r = DetectionResult(found=True, label="ball", confidence=0.9, cx=0.5, cy=0.5)
        d = r.to_dict()
        for key in ("found", "label", "confidence", "cx", "cy", "model_name"):
            self.assertIn(key, d)

    def test_found_result(self):
        from app.models.ml_model_manager import DetectionResult

        r = DetectionResult(found=True, label="cup", confidence=0.87, cx=0.6, cy=0.4)
        self.assertTrue(r.found)
        self.assertEqual(r.label, "cup")
        self.assertAlmostEqual(r.confidence, 0.87)


class TestRobotCommand(unittest.TestCase):
    def test_idle_factory(self):
        from app.models.ml_model_manager import RobotCommand

        cmd = RobotCommand.idle()
        self.assertEqual(cmd.description, "idle")
        self.assertEqual(cmd.joint_deltas, [0.0] * 6)

    def test_to_dict_keys(self):
        from app.models.ml_model_manager import RobotCommand

        cmd = RobotCommand(joint_deltas=[1, 2, 3, 4, 5, 6], description="test")
        d = cmd.to_dict()
        self.assertIn("joint_deltas", d)
        self.assertIn("description", d)
        self.assertIn("gripper_open", d)


class TestVisionModelManager(unittest.TestCase):
    def setUp(self):
        from app.models.ml_model_manager import VisionModelManager

        self.manager = VisionModelManager()

    def test_empty_manager(self):
        self.assertEqual(len(self.manager), 0)
        self.assertIsNone(self.manager.active_model)

    def test_register_model(self):
        from app.models.ml_model_manager import BaseMLModel, DetectionResult

        class FakeModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult.not_found(self.name)

        model = FakeModel("test")
        self.manager.register(model)
        self.assertEqual(len(self.manager), 1)

    def test_set_active_loads_model(self):
        from app.models.ml_model_manager import BaseMLModel, DetectionResult

        class FakeModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult.not_found(self.name)

        model = FakeModel("my_model")
        self.manager.register(model)
        ok = self.manager.set_active("my_model")
        self.assertTrue(ok)
        self.assertIsNotNone(self.manager.active_model)

    def test_set_active_nonexistent_fails(self):
        ok = self.manager.set_active("ghost_model")
        self.assertFalse(ok)

    def test_predict_without_active_returns_not_found(self):
        frame = _fake_frame()
        result = self.manager.predict(frame)
        self.assertFalse(result.found)

    def test_predict_with_active_model(self):
        from app.models.ml_model_manager import BaseMLModel, DetectionResult

        class AlwaysFoundModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult(
                    found=True, label="ball", confidence=0.95, cx=0.5, cy=0.5, model_name=self.name
                )

        model = AlwaysFoundModel("finder")
        self.manager.register(model)
        self.manager.set_active("finder")
        result = self.manager.predict(_fake_frame())
        self.assertTrue(result.found)
        self.assertEqual(result.label, "ball")

    def test_unregister_model(self):
        from app.models.ml_model_manager import BaseMLModel, DetectionResult

        class FakeModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult.not_found(self.name)

        self.manager.register(FakeModel("tmp"))
        ok = self.manager.unregister("tmp")
        self.assertTrue(ok)
        self.assertEqual(len(self.manager), 0)

    def test_list_models_structure(self):
        from app.models.ml_model_manager import BaseMLModel, DetectionResult

        class FakeModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult.not_found(self.name)

        self.manager.register(FakeModel("m1"))
        models = self.manager.list_models()
        self.assertEqual(len(models), 1)
        self.assertIn("name", models[0])
        self.assertIn("type", models[0])
        self.assertIn("loaded", models[0])
        self.assertIn("active", models[0])


# ═══════════════════════════════════════════════
#  AIRobotController Tests
# ═══════════════════════════════════════════════


class TestAIRobotController(unittest.TestCase):
    def _make_manager_with_model(self, found: bool, cx: float = 0.5, cy: float = 0.5):
        from app.models.ml_model_manager import (
            AIRobotController,
            BaseMLModel,
            DetectionResult,
            VisionModelManager,
        )

        class MockModel(BaseMLModel):
            def __init__(self, f, x, y):
                super().__init__("mock")
                self._f, self._x, self._y = f, x, y

            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                if self._f:
                    return DetectionResult(
                        found=True,
                        label="obj",
                        confidence=0.9,
                        cx=self._x,
                        cy=self._y,
                        bbox=[self._x - 0.1, self._y - 0.1, self._x + 0.1, self._y + 0.1],
                        width=0.2,
                        height=0.2,
                        model_name=self.name,
                    )
                return DetectionResult.not_found(self.name)

        mgr = VisionModelManager()
        mgr.register(MockModel(found, cx, cy))
        mgr.set_active("mock")
        ctrl = AIRobotController(mgr)
        return ctrl

    def test_process_frame_not_found_returns_idle(self):
        ctrl = self._make_manager_with_model(found=False)
        cmd = ctrl.process_frame(_fake_frame())
        self.assertEqual(cmd.description, "idle")

    def test_process_frame_found_centered_no_movement(self):
        """Объект по центру → никакого движения."""
        ctrl = self._make_manager_with_model(found=True, cx=0.5, cy=0.5)
        cmd = ctrl.process_frame(_fake_frame())
        # Либо "centered" либо маленькие дельты
        total_delta = sum(abs(d) for d in cmd.joint_deltas)
        self.assertLess(total_delta, 1.0)

    def test_process_frame_found_off_center_has_deltas(self):
        """Объект не по центру → ненулевые дельты суставов."""
        ctrl = self._make_manager_with_model(found=True, cx=0.9, cy=0.5)
        cmd = ctrl.process_frame(_fake_frame())
        # J1 (pan) должен иметь ненулевую дельту
        self.assertNotEqual(cmd.joint_deltas[0], 0.0)

    def test_process_frame_large_object_triggers_grip(self):
        """Большой объект (близко) → команда grip."""
        from app.models.ml_model_manager import (
            AIRobotController,
            BaseMLModel,
            DetectionResult,
            VisionModelManager,
        )

        class BigObjectModel(BaseMLModel):
            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                return DetectionResult(
                    found=True,
                    label="obj",
                    confidence=0.95,
                    cx=0.5,
                    cy=0.5,
                    bbox=[0.3, 0.3, 0.7, 0.7],
                    width=0.4,
                    height=0.4,
                    model_name=self.name,
                )

        mgr = VisionModelManager()
        mgr.register(BigObjectModel("big"))
        mgr.set_active("big")
        ctrl = AIRobotController(mgr)
        cmd = ctrl.process_frame(_fake_frame())
        self.assertFalse(cmd.gripper_open)

    def test_last_detection_updated(self):
        ctrl = self._make_manager_with_model(found=True, cx=0.6, cy=0.4)
        self.assertIsNone(ctrl.last_detection)
        ctrl.process_frame(_fake_frame())
        self.assertIsNotNone(ctrl.last_detection)

    def test_get_status_structure(self):
        ctrl = self._make_manager_with_model(found=False)
        status = ctrl.get_status()
        self.assertIn("active_model", status)
        self.assertIn("models", status)


# ═══════════════════════════════════════════════
#  MLTrackingService Tests
# ═══════════════════════════════════════════════


class TestMLTrackingServiceInit(unittest.TestCase):
    def _make_service(self, found: bool = False):
        from app.models.ml_model_manager import (
            AIRobotController,
            BaseMLModel,
            DetectionResult,
            VisionModelManager,
        )
        from app.services.ml_tracking_service import MLTrackingService

        class FakeModel(BaseMLModel):
            def __init__(self, f):
                super().__init__("fake")
                self._f = f

            def load(self):
                self._loaded = True
                return True

            def predict(self, frame):
                if self._f:
                    return DetectionResult(
                        found=True,
                        label="obj",
                        confidence=0.9,
                        cx=0.5,
                        cy=0.5,
                        model_name=self.name,
                    )
                return DetectionResult.not_found(self.name)

        mgr = VisionModelManager()
        mgr.register(FakeModel(found))
        mgr.set_active("fake")

        ctrl = AIRobotController(mgr)
        robot = _make_robot_service()
        svc = MLTrackingService(robot, ctrl, auto_control=False)
        return svc

    def test_initial_state_not_running(self):
        svc = self._make_service()
        state = svc.get_state()
        self.assertFalse(state.is_running)

    def test_configure_camera_id(self):
        svc = self._make_service()
        svc.configure(camera_id=2)
        self.assertEqual(svc._camera_id, 2)

    def test_configure_auto_control(self):
        svc = self._make_service()
        svc.configure(auto_control=True)
        self.assertTrue(svc._auto_control)

    def test_set_frame_callback(self):
        svc = self._make_service()
        cb = MagicMock()
        svc.set_frame_callback(cb)
        self.assertIs(svc._frame_callback, cb)

    def test_set_state_callback(self):
        svc = self._make_service()
        cb = MagicMock()
        svc.set_state_callback(cb)
        self.assertIs(svc._state_callback, cb)

    def test_set_command_callback(self):
        svc = self._make_service()
        cb = MagicMock()
        svc.set_command_callback(cb)
        self.assertIs(svc._command_callback, cb)

    def test_set_auto_control(self):
        svc = self._make_service()
        svc.set_auto_control(True)
        self.assertTrue(svc._auto_control)
        svc.set_auto_control(False)
        self.assertFalse(svc._auto_control)


if __name__ == "__main__":
    unittest.main(verbosity=2)
