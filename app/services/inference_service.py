#!/usr/bin/env python3
"""
Inference Service — загрузка и запуск LeRobot-моделей на GPU.
Поддерживает: ACT, Diffusion, SmolVLA, pi0, pi0.5.
Опционально: Ray для параллельной预处理 / ensemble инференса.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import torch


class InferenceService:
    """Сервис инференса LeRobot-моделей (ACT, Diffusion, pi0, pi0.5, SmolVLA)."""

    # Типы моделей
    MODELS_CATALOG = {
        "act": [
            "lerobot/act_aloha_sim_transfer_cube_human",
            "lerobot/act_aloha_mobile_cabinet",
            "lerobot/act_so100_pick_cup",
        ],
        "diffusion": [
            "lerobot/diffusion_pusht",
            "lerobot/diffusion_policy-grasp",
        ],
        "vla": [
            "lerobot/pi0_base",
            "lerobot/pi0_libero",
            "lerobot/pi05_base",
            "lerobot/pi05_libero",
        ],
        "smolvla": [
            "lerobot/smolvla-aloha",
        ],
    }

    def __init__(
        self,
        robot_service,
        camera_service,
        kinematics_service,
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.robot = robot_service
        self.camera = camera_service
        self.kinematics = kinematics_service
        self.log = log_callback

        self.policy = None
        self.preprocessor = None
        self.postprocessor = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_flag = False
        self.model_name = ""
        self.model_type = ""
        self._lock = threading.Lock()

        self._action_queue: list[np.ndarray] = []
        self._fps = 0.0
        self._latency_ms = 0.0
        self._frame_count = 0

        # Ray (optional)
        self.ray_available = False
        self._ray_init = False
        self._ray_workers = []
        self._use_ray = False
        self._try_init_ray()

    def _try_init_ray(self):
        try:
            import ray
            if not ray.is_initialized():
                ray.init(ignore_reinit_error=True, include_dashboard=False)
                self._ray_init = True
            self.ray_available = True
            self._log_msg("Ray available for parallel processing", "info")
        except Exception:
            self.ray_available = False

    def _log_msg(self, msg: str, level: str = "info"):
        if self.log:
            self.log(msg, level)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {"fps": self._fps, "latency_ms": self._latency_ms, "frames": self._frame_count}

    @property
    def use_ray(self) -> bool:
        return self._use_ray

    @use_ray.setter
    def use_ray(self, val: bool):
        self._use_ray = val and self.ray_available
        self._log_msg(
            f"Ray {'enabled' if self._use_ray else 'disabled'}" +
            ("" if self.ray_available else " (not available)"),
            "info",
        )

    def load_model(self, model_name: str) -> bool:
        """Load any LeRobot model."""
        try:
            self._log_msg(f"Loading model: {model_name} on {self.device}...", "info")

            # Detect model type from name
            ml = model_name.lower()
            if "pi0" in ml:
                self.model_type = "pi0" if "pi05" not in ml else "pi05"
            elif "smolvla" in ml:
                self.model_type = "smolvla"
            elif "diffusion" in ml:
                self.model_type = "diffusion"
            else:
                self.model_type = "act"

            if self.model_type in ("pi0", "pi05"):
                ok = self._load_pi0(model_name)
            elif self.model_type == "smolvla":
                ok = self._load_smolvla(model_name)
            else:
                ok = self._load_standard(model_name)

            if ok:
                self.model_name = model_name
                torch.set_grad_enabled(False)
                if self.device == "cuda":
                    torch.backends.cuda.matmul.allow_tf32 = True
                    torch.backends.cudnn.allow_tf32 = True
                    torch.backends.cudnn.benchmark = True
                self._log_msg(f"Model loaded: {model_name}", "success")
            return ok

        except Exception as e:
            self._log_msg(f"Failed to load model: {e}", "error")
            return False

    def _load_standard(self, model_name: str) -> bool:
        """Load ACT / Diffusion via make_policy."""
        from lerobot.policies import make_policy
        from lerobot.common.policies.factory import make_pre_post_processors

        self.policy = make_policy(pretrained=model_name)
        self.policy = self.policy.to(self.device)
        self.policy.eval()
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            policy_cfg=self.policy.config, pretrained=model_name,
        )
        return True

    def _load_pi0(self, model_name: str) -> bool:
        """Load pi0 or pi0.5 model."""
        from lerobot.common.policies.pi0 import PI0Policy
        from lerobot.common.policies.pi05 import PI05Policy

        cls = PI05Policy if self.model_type == "pi05" else PI0Policy
        self.policy = cls.from_pretrained(model_name)
        self.policy = self.policy.to(self.device).eval()

        cfg = self.policy.config
        if hasattr(cfg, "pi0") and hasattr(cfg.pi0, "dataset_stats"):
            self.preprocessor = lambda x: x
            self.postprocessor = lambda a: a.cpu() if torch.is_tensor(a) else torch.tensor(a)
        else:
            from lerobot.common.policies.factory import make_pre_post_processors
            self.preprocessor, self.postprocessor = make_pre_post_processors(
                policy_cfg=cfg, pretrained=model_name,
            )
        return True

    def _load_smolvla(self, model_name: str) -> bool:
        """Load SmolVLA model."""
        from lerobot.common.policies.smolvla import SmolVLAPolicy

        self.policy = SmolVLAPolicy.from_pretrained(model_name)
        self.policy = self.policy.to(self.device).eval()

        from lerobot.common.policies.factory import make_pre_post_processors
        self.preprocessor, self.postprocessor = make_pre_post_processors(
            policy_cfg=self.policy.config, pretrained=model_name,
        )
        return True

    def unload_model(self):
        self.policy = None
        self.preprocessor = None
        self.postprocessor = None
        self.model_name = ""
        self.model_type = ""
        torch.cuda.empty_cache()
        self._log_msg("Model unloaded", "info")

    def start_inference(self):
        if self._running or self.policy is None:
            return False
        self._stop_flag = False
        self._running = True
        self._action_queue = []
        self._frame_count = 0
        self._thread = threading.Thread(target=self._inference_loop, daemon=True)
        self._thread.start()
        self._log_msg("Inference started", "success")
        return True

    def stop_inference(self):
        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=5)
        self._running = False
        self._log_msg("Inference stopped", "info")

    def _inference_loop(self):
        timestep = 0
        while not self._stop_flag:
            start = time.time()

            try:
                joint_angles = self._read_joint_angles()
                frame = self._read_camera_frame()
                if frame is None:
                    time.sleep(0.01)
                    continue

                obs = {
                    "observation.state": torch.tensor(
                        joint_angles, dtype=torch.float32, device=self.device
                    ),
                }

                if frame is not None:
                    img_t = torch.from_numpy(frame).permute(2, 0, 1).float().to(self.device) / 255.0
                    obs["observation.images.top"] = img_t

                with torch.no_grad():
                    action = self.policy.select_action(obs)

                if self.postprocessor:
                    action_t = self.postprocessor(action)
                else:
                    action_t = action.cpu() if torch.is_tensor(action) else torch.tensor(action)

                action_np = action_t.numpy().flatten()
                self._execute_action(action_np)

                self._frame_count += 1
                timestep += 1

            except Exception as e:
                self._log_msg(f"Inference error: {e}", "error")

            elapsed = time.time() - start
            self._latency_ms = round(elapsed * 1000, 1)
            self._fps = round(1.0 / max(elapsed, 0.001), 1)

            sleep = max(0, 1.0 / 30 - elapsed)
            time.sleep(sleep)

    def _read_joint_angles(self) -> list[float]:
        angles = []
        for j in range(6):
            mid = getattr(self.robot, "get_motor_id_for_joint", lambda i: i + 1)(j)
            pos = self.robot.joint_positions.get(mid, 2048)
            angles.append(float((pos / 4095) * 360 - 180))
        return angles

    def _read_camera_frame(self):
        try:
            frame = self.camera.get_frame()
            if frame is not None and isinstance(frame, np.ndarray):
                return frame
        except Exception:
            pass
        return None

    def _execute_action(self, action: np.ndarray):
        try:
            for j in range(min(len(action), 6)):
                angle = float(action[j])
                position = max(0, min(4095, int((angle + 180) / 360 * 4095)))
                mid = getattr(self.robot, "get_motor_id_for_joint", lambda i: i + 1)(j)
                self.robot.move_to_position(mid, position)
        except Exception as e:
            self._log_msg(f"Action execution error: {e}", "error")
