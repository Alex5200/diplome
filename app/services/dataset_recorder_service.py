#!/usr/bin/env python3
"""
Dataset Recorder Service — запись эпизодов в VAMOS и LeRobot форматы.

VAMOS (custom):
  vamos/episode_{idx:06d}/
    metadata.json   — эпизод, задача, FPS, кол-во кадров
    command.txt     — текст команды (если задана)
    states.json     — per-frame: joint_angles, tool_pose, motor_load, motor_temp
    frames/         — frame_{:06d}.png  (кадры с камеры)

LeRobot (v2.1 compatible, JSON вместо parquet):
  lerobot/
    meta/
      info.json     — fps, robot_type, features schema
      tasks.jsonl   — задача на эпизод
    episodes/
      episode_000000.json   — per-step: obs.state, action, timestamp, done
    videos/
      observation.images.main/
        episode_000000.mp4
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np


class DatasetRecorderService:
    """Сервис записи датасетов в VAMOS и/или LeRobot форматах."""

    VAMOS_DIR = "vamos"
    LEROBOT_DIR = "lerobot"

    def __init__(
        self,
        robot_service,
        camera_service,
        kinematics_service,
        base_path: str = "datasets",
        log_callback: Callable[[str, str], None] | None = None,
    ):
        self.robot = robot_service
        self.camera = camera_service
        self.kinematics = kinematics_service
        self.base_path = Path(base_path)
        self.log = log_callback

        self._recording = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._stop_flag = False
        self._lock = threading.Lock()

        self._current_episode: dict[str, Any] = {}
        self._frames_buffer: list[np.ndarray] = []
        self._states_buffer: list[dict] = []
        self._episode_count = 0
        self._format_vamos = True
        self._format_lerobot = True
        self._fps = 30
        self._task_name = ""
        self._command_text = ""
        self._frame_count = 0
        self._joint_names = ["J1_Base", "J2_Shoulder", "J3_Elbow", "J4_Wrist1", "J5_Wrist2", "J6_Wrist3"]

        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.VAMOS_DIR, self.LEROBOT_DIR]:
            (self.base_path / d).mkdir(parents=True, exist_ok=True)

    def configure(
        self,
        format_vamos: bool = True,
        format_lerobot: bool = True,
        fps: int = 30,
    ):
        self._format_vamos = format_vamos
        self._format_lerobot = format_lerobot
        self._fps = fps

    # ── Recording lifecycle ────────────────────────────────────────────────

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @property
    def episode_count(self) -> int:
        return self._episode_count

    def _log(self, msg: str, level: str = "info"):
        if self.log:
            self.log(msg, level)

    def start_episode(self, task_name: str = "", command_text: str = ""):
        if self._recording:
            self._log("Already recording", "warning")
            return False

        self._task_name = task_name
        self._command_text = command_text
        self._frame_count = 0
        self._frames_buffer = []
        self._states_buffer = []
        self._stop_flag = False
        self._paused = False

        self._current_episode = {
            "episode_index": self._episode_count,
            "task": task_name,
            "command": command_text,
            "fps": self._fps,
            "joint_names": self._joint_names,
            "start_time": time.time(),
            "frames": [],
        }

        self._recording = True
        self._thread = threading.Thread(target=self._record_loop, daemon=True)
        self._thread.start()
        self._log(f"Recording episode {self._episode_count} started [{task_name}]", "success")
        return True

    def pause_episode(self):
        if not self._recording:
            return
        self._paused = not self._paused
        self._log("Recording paused" if self._paused else "Recording resumed", "info")

    def stop_episode(self):
        if not self._recording:
            return False
        self._stop_flag = True
        if self._thread:
            self._thread.join(timeout=5)
        self._recording = False
        self._paused = False

        self._current_episode["duration"] = time.time() - self._current_episode["start_time"]
        self._current_episode["num_frames"] = self._frame_count

        # Save frames
        if self._format_vamos:
            self._save_vamos_episode()
        if self._format_lerobot:
            self._save_lerobot_episode()

        self._episode_count += 1
        self._log(f"Episode saved — {self._frame_count} frames", "success")
        return True

    def _record_loop(self):
        interval = 1.0 / max(self._fps, 1)
        while not self._stop_flag:
            if self._paused:
                time.sleep(0.05)
                continue

            start = time.time()

            with self._lock:
                self._record_frame()

            elapsed = time.time() - start
            sleep = max(0, interval - elapsed)
            time.sleep(sleep)

    def _record_frame(self):
        joint_angles = self._read_joint_angles()
        tool_pose = self._read_tool_pose()
        motor_data = self._read_motor_data()
        frame = self._read_camera_frame()

        state = {
            "timestamp": time.time(),
            "frame_index": self._frame_count,
            "joint_angles": joint_angles,
            "tool_pose": tool_pose,
            "motor_load": motor_data.get("load", [0.0] * 6),
            "motor_temp": motor_data.get("temperature", [0.0] * 6),
            "motor_position_raw": motor_data.get("position_raw", [0] * 6),
        }

        self._states_buffer.append(state)
        if frame is not None:
            self._frames_buffer.append(frame)

        self._frame_count += 1

    # ── Readers ─────────────────────────────────────────────────────────────

    def _read_joint_angles(self) -> list[float]:
        angles = []
        for j in range(6):
            mid = getattr(self.robot, "get_motor_id_for_joint", lambda i: i + 1)(j)
            pos = self.robot.joint_positions.get(mid, 2048)
            angles.append(round((pos / 4095) * 360 - 180, 2))
        return angles

    def _read_tool_pose(self) -> list[float]:
        try:
            angles = self._read_joint_angles()
            pos = self.kinematics.get_end_effector_position(angles)
            return [round(pos[0], 2), round(pos[1], 2), round(pos[2], 2)]
        except Exception:
            return [0.0, 0.0, 0.0]

    def _read_motor_data(self) -> dict:
        data: dict[str, list] = {"load": [], "temperature": [], "position_raw": []}
        try:
            for j in range(6):
                mid = getattr(self.robot, "get_motor_id_for_joint", lambda i: i + 1)(j)
                md = getattr(self.robot, "motor_data", {}).get(mid, {})
                data["load"].append(getattr(md, "load", 0.0) if not isinstance(md, dict) else md.get("load", 0.0))
                data["temperature"].append(getattr(md, "temperature", 0.0) if not isinstance(md, dict) else md.get("temperature", 0.0))
                data["position_raw"].append(getattr(md, "position_raw", 0) if not isinstance(md, dict) else md.get("position_raw", 0))
        except Exception:
            data = {"load": [0.0]*6, "temperature": [0.0]*6, "position_raw": [0]*6}
        return data

    def _read_camera_frame(self):
        try:
            frame = self.camera.get_frame()
            if frame is not None and isinstance(frame, np.ndarray):
                return frame
        except Exception:
            pass
        return None

    # ── VAMOS format ────────────────────────────────────────────────────────

    def _save_vamos_episode(self):
        ep_idx = self._current_episode["episode_index"]
        ep_dir = self.base_path / self.VAMOS_DIR / f"episode_{ep_idx:06d}"
        ep_dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "episode_index": ep_idx,
            "task": self._task_name,
            "command": self._command_text,
            "fps": self._fps,
            "num_frames": self._frame_count,
            "duration_s": round(self._current_episode["duration"], 3),
            "start_time": self._current_episode["start_time"],
            "joint_names": self._joint_names,
            "format": "VAMOS_v1",
        }
        with open(ep_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        if self._command_text.strip():
            with open(ep_dir / "command.txt", "w", encoding="utf-8") as f:
                f.write(self._command_text)

        with open(ep_dir / "states.json", "w", encoding="utf-8") as f:
            json.dump(self._states_buffer, f, indent=2)

        frames_dir = ep_dir / "frames"
        frames_dir.mkdir(exist_ok=True)
        for i, frame in enumerate(self._frames_buffer):
            path = frames_dir / f"frame_{i:06d}.png"
            cv2.imwrite(str(path), cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))

        self._log(f"VAMOS: episode_{ep_idx:06d} saved ({len(self._frames_buffer)} frames)", "info")

    # ── LeRobot format (v2.1 compatible, JSON instead of parquet) ──────────

    def _save_lerobot_episode(self):
        ep_idx = self._current_episode["episode_index"]
        lerobot_dir = self.base_path / self.LEROBOT_DIR
        lerobot_dir.mkdir(parents=True, exist_ok=True)

        # Meta dirs
        meta_dir = lerobot_dir / "meta"
        episodes_dir = lerobot_dir / "episodes"
        videos_dir = lerobot_dir / "videos" / "observation.images.main"
        meta_dir.mkdir(parents=True, exist_ok=True)
        episodes_dir.mkdir(parents=True, exist_ok=True)
        videos_dir.mkdir(parents=True, exist_ok=True)

        # Save per-episode data as JSON
        episode_data = []
        for s in self._states_buffer:
            row = {
                "episode_index": ep_idx,
                "frame_index": s["frame_index"],
                "timestamp": s["timestamp"],
                "observation.state": s["joint_angles"],
                "observation.tool_pose": s["tool_pose"],
                "observation.motor_load": s["motor_load"],
                "observation.motor_temp": s["motor_temp"],
                "action": s["joint_angles"],
                "next.done": False,
            }
            episode_data.append(row)
        if episode_data:
            episode_data[-1]["next.done"] = True

        ep_file = episodes_dir / f"episode_{ep_idx:06d}.json"
        with open(ep_file, "w", encoding="utf-8") as f:
            json.dump(episode_data, f, indent=2)

        # Save video from frames buffer
        if self._frames_buffer:
            h, w = self._frames_buffer[0].shape[:2]
            video_path = videos_dir / f"episode_{ep_idx:06d}.mp4"
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            out = cv2.VideoWriter(str(video_path), fourcc, self._fps, (w, h))
            for frame in self._frames_buffer:
                out.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
            out.release()

        # Write/update meta/info.json
        info_path = meta_dir / "info.json"
        if info_path.exists():
            with open(info_path, encoding="utf-8") as f:
                info = json.load(f)
        else:
            info = {
                "codebase_version": "v2.1",
                "fps": self._fps,
                "robot_type": "custom_6dof",
                "total_episodes": 0,
                "total_frames": 0,
                "features": {
                    "observation.state": {
                        "dtype": "float32",
                        "shape": (6,),
                        "names": self._joint_names,
                    },
                    "observation.tool_pose": {
                        "dtype": "float32",
                        "shape": (3,),
                    },
                    "observation.motor_load": {
                        "dtype": "float32",
                        "shape": (6,),
                    },
                    "observation.motor_temp": {
                        "dtype": "float32",
                        "shape": (6,),
                    },
                    "observation.images.main": {
                        "dtype": "video",
                        "shape": (480, 640, 3),
                        "names": ["height", "width", "channel"],
                    },
                    "action": {
                        "dtype": "float32",
                        "shape": (6,),
                        "names": self._joint_names,
                    },
                },
                "data_path": "episodes/episode_{episode_index:06d}.json",
                "video_path": "videos/observation.images.main/episode_{episode_index:06d}.mp4",
            }

        info["total_episodes"] = max(info.get("total_episodes", 0), ep_idx + 1)
        info["total_frames"] = info.get("total_frames", 0) + self._frame_count
        with open(info_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)

        # Append to tasks.jsonl
        tasks_path = meta_dir / "tasks.jsonl"
        with open(tasks_path, "a", encoding="utf-8") as f:
            entry = {"episode_index": ep_idx, "task": self._task_name}
            if self._command_text:
                entry["command"] = self._command_text
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        self._log(f"LeRobot: episode_{ep_idx:06d} saved", "info")
