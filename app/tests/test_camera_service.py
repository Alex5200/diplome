#!/usr/bin/env python3
"""
TDD тесты для CameraService.

Запуск:
    python -m pytest app/tests/test_camera_service.py -v --tb=short

Примечание: тесты не открывают реальную камеру (используют mock).
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, PropertyMock, patch

import numpy as np

# ══════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════


def _make_cap(opened=True, frame=None):
    """Создать mock VideoCapture."""
    cap = MagicMock()
    cap.isOpened.return_value = opened
    cap.get.side_effect = lambda prop: {
        3: 640.0,  # CAP_PROP_FRAME_WIDTH
        4: 480.0,  # CAP_PROP_FRAME_HEIGHT
        5: 30.0,  # CAP_PROP_FPS
    }.get(prop, 0.0)

    if frame is None:
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cap.read.return_value = (True, frame)
    return cap


# ══════════════════════════════════════════════
#  Test: _select_backend
# ══════════════════════════════════════════════


class TestSelectBackend(unittest.TestCase):
    def test_returns_int(self):
        from app.services.camera_service import _select_backend

        backend = _select_backend()
        self.assertIsInstance(backend, int)

    def test_darwin_returns_avfoundation(self):
        import cv2

        from app.services.camera_service import _select_backend

        with patch("sys.platform", "darwin"):
            b = _select_backend()
        self.assertEqual(b, cv2.CAP_AVFOUNDATION)

    def test_win32_returns_dshow(self):
        import cv2

        from app.services.camera_service import _select_backend

        with patch("sys.platform", "win32"):
            b = _select_backend()
        self.assertEqual(b, cv2.CAP_DSHOW)

    def test_linux_returns_v4l2(self):
        import cv2

        from app.services.camera_service import _select_backend

        with patch("sys.platform", "linux"):
            b = _select_backend()
        self.assertEqual(b, cv2.CAP_V4L2)

    def test_unknown_returns_cap_any(self):
        import cv2

        from app.services.camera_service import _select_backend

        with patch("sys.platform", "freebsd"):
            b = _select_backend()
        self.assertEqual(b, cv2.CAP_ANY)


# ══════════════════════════════════════════════
#  Test: CameraInfo
# ══════════════════════════════════════════════


class TestCameraInfo(unittest.TestCase):
    def test_label_with_resolution(self):
        from app.services.camera_service import CameraInfo

        info = CameraInfo(id=0, name="FaceTime", width=640, height=480)
        self.assertIn("640", info.label)
        self.assertIn("480", info.label)
        self.assertIn("0", info.label)

    def test_label_without_resolution(self):
        from app.services.camera_service import CameraInfo

        info = CameraInfo(id=1, name="Camera 1")
        self.assertIn("1", info.label)

    def test_str_same_as_label(self):
        from app.services.camera_service import CameraInfo

        info = CameraInfo(id=0, name="Test", width=1280, height=720)
        self.assertEqual(str(info), info.label)


# ══════════════════════════════════════════════
#  Test: scan_cameras (mocked)
# ══════════════════════════════════════════════


class TestScanCameras(unittest.TestCase):
    @patch("cv2.VideoCapture")
    def test_no_cameras_returns_fallback(self, mock_vc):
        """Если нет камер — возвращает fallback Camera 0."""
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=False)
        cameras = CameraService.scan_cameras(max_index=3)
        self.assertGreater(len(cameras), 0)
        self.assertEqual(cameras[0].id, 0)

    @patch("cv2.VideoCapture")
    def test_one_camera_found(self, mock_vc):
        from app.services.camera_service import CameraService

        def side_effect(i, *args, **kwargs):
            cap = _make_cap(opened=(i == 0))
            return cap

        mock_vc.side_effect = side_effect
        cameras = CameraService.scan_cameras(max_index=3)
        # Должна быть хотя бы одна камера
        self.assertGreater(len(cameras), 0)

    @patch("cv2.VideoCapture")
    def test_scan_labels_returns_strings(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=False)
        labels = CameraService.scan_cameras_labels(max_index=2)
        self.assertIsInstance(labels, list)
        for label in labels:
            self.assertIsInstance(label, str)


# ══════════════════════════════════════════════
#  Test: CameraService init & config
# ══════════════════════════════════════════════


class TestCameraServiceInit(unittest.TestCase):
    def test_initial_state(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        self.assertFalse(cam.is_running)
        self.assertEqual(cam.camera_id, -1)
        self.assertIsNone(cam.get_frame())

    def test_set_resolution(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        cam.set_resolution(1280, 720)
        self.assertEqual(cam._width, 1280)
        self.assertEqual(cam._height, 720)

    def test_set_fps(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        cam.set_fps(60.0)
        self.assertAlmostEqual(cam._fps, 60.0)

    def test_set_frame_callback(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        cb = MagicMock()
        cam.set_frame_callback(cb)
        self.assertIs(cam._frame_callback, cb)

    def test_set_error_callback(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        cb = MagicMock()
        cam.set_error_callback(cb)
        self.assertIs(cam._error_callback, cb)

    def test_repr_stopped(self):
        from app.services.camera_service import CameraService

        cam = CameraService()
        self.assertIn("stopped", repr(cam))

    def test_get_actual_resolution_before_open(self):
        from app.services.camera_service import CameraService

        cam = CameraService(width=320, height=240)
        w, h = cam.get_actual_resolution()
        self.assertEqual(w, 320)
        self.assertEqual(h, 240)


# ══════════════════════════════════════════════
#  Test: start / stop (mocked VideoCapture)
# ══════════════════════════════════════════════


class TestCameraServiceStartStop(unittest.TestCase):
    @patch("cv2.VideoCapture")
    def test_start_success(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=True)
        cam = CameraService()
        ok = cam.start(0)
        cam.stop()
        self.assertTrue(ok)

    @patch("cv2.VideoCapture")
    def test_start_failure_when_camera_unavailable(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=False)
        cam = CameraService()
        ok = cam.start(99)
        self.assertFalse(ok)
        self.assertFalse(cam.is_running)

    @patch("cv2.VideoCapture")
    def test_stop_when_not_running(self, mock_vc):
        from app.services.camera_service import CameraService

        cam = CameraService()
        cam.stop()  # не должно бросить исключение
        self.assertFalse(cam.is_running)

    @patch("cv2.VideoCapture")
    def test_start_twice_same_camera(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=True)
        cam = CameraService()
        ok1 = cam.start(0)
        ok2 = cam.start(0)  # повторный старт той же камеры
        cam.stop()
        self.assertTrue(ok1)
        self.assertTrue(ok2)

    @patch("cv2.VideoCapture")
    def test_error_callback_on_open_failure(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=False)
        cam = CameraService()
        errors = []
        cam.set_error_callback(lambda e: errors.append(e))
        cam.start(99)
        self.assertGreater(len(errors), 0)


# ══════════════════════════════════════════════
#  Test: frame delivery
# ══════════════════════════════════════════════


class TestCameraServiceFrames(unittest.TestCase):
    @patch("cv2.VideoCapture")
    @patch("cv2.cvtColor")
    def test_frame_callback_called(self, mock_cvt, mock_vc):
        """Callback вызывается когда кадр захвачен."""
        import time

        from app.services.camera_service import CameraService

        # Подготовить mock кадр
        fake_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_vc.return_value = _make_cap(opened=True)
        mock_cvt.return_value = fake_rgb

        received = []
        cam = CameraService()
        cam.set_fps(100)  # быстрый FPS для теста
        cam.set_frame_callback(lambda f: received.append(f))

        cam.start(0)
        time.sleep(0.15)  # дать потоку время сработать
        cam.stop()

        self.assertGreater(len(received), 0)

    @patch("cv2.VideoCapture")
    @patch("cv2.cvtColor")
    def test_get_frame_after_capture(self, mock_cvt, mock_vc):
        """get_frame() возвращает numpy array после захвата."""
        import time

        from app.services.camera_service import CameraService

        fake_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_vc.return_value = _make_cap(opened=True)
        mock_cvt.return_value = fake_rgb

        cam = CameraService()
        cam.set_fps(100)
        cam.start(0)
        time.sleep(0.15)
        frame = cam.get_frame()
        cam.stop()

        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))

    @patch("cv2.VideoCapture")
    def test_get_frame_returns_none_before_start(self, mock_vc):
        from app.services.camera_service import CameraService

        cam = CameraService()
        self.assertIsNone(cam.get_frame())

    @patch("cv2.VideoCapture")
    @patch("cv2.cvtColor")
    def test_get_frame_returns_copy(self, mock_cvt, mock_vc):
        """get_frame() возвращает копию, не ссылку."""
        import time

        from app.services.camera_service import CameraService

        fake_rgb = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_vc.return_value = _make_cap(opened=True)
        mock_cvt.return_value = fake_rgb

        cam = CameraService()
        cam.set_fps(100)
        cam.start(0)
        time.sleep(0.15)
        f1 = cam.get_frame()
        f2 = cam.get_frame()
        cam.stop()

        # Разные объекты (копии)
        if f1 is not None and f2 is not None:
            self.assertIsNot(f1, f2)


# ══════════════════════════════════════════════
#  Test: get_actual_resolution
# ══════════════════════════════════════════════


class TestCameraServiceResolution(unittest.TestCase):
    @patch("cv2.VideoCapture")
    def test_actual_resolution_after_open(self, mock_vc):
        from app.services.camera_service import CameraService

        mock_vc.return_value = _make_cap(opened=True)
        cam = CameraService()
        cam.start(0)
        w, h = cam.get_actual_resolution()
        cam.stop()
        self.assertEqual(w, 640)
        self.assertEqual(h, 480)


if __name__ == "__main__":
    unittest.main(verbosity=2)
