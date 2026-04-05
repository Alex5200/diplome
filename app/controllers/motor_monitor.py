#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Motor Monitor Module
Handles asynchronous monitoring of motor data
"""

import threading
import time
from typing import Optional, Dict, List, Callable

from ..config.constants import MONITOR_INTERVAL
from ..models.motor_data import MotorData
from .motor_controller import MotorController


class MotorMonitor:
    def __init__(self, motor_controller: MotorController, update_callback: Optional[Callable] = None):
        self.motor_controller = motor_controller
        self.update_callback = update_callback
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.motor_data: Dict[int, MotorData] = {}
        self.lock = threading.Lock()

    def start(self, motor_ids: List[int]):
        if self.running:
            return
        with self.lock:
            for mid in motor_ids:
                if mid not in self.motor_data:
                    self.motor_data[mid] = MotorData(motor_id=mid)
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"🔍 Мониторинг запущен для {len(motor_ids)} моторов")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
        print("🛑 Мониторинг остановлен")

    def _monitor_loop(self):
        while self.running:
            start_time = time.time()
            try:
                motor_ids = list(self.motor_data.keys())
                for motor_id in motor_ids:
                    if not self.running:
                        break
                    with self.lock:
                        data = self.motor_data.get(motor_id)
                        if data:
                            self._update_motor_data(motor_id, data)
            except Exception as e:
                print(f"❌ Ошибка мониторинга: {e}")
            elapsed = time.time() - start_time
            sleep_time = max(0, MONITOR_INTERVAL - elapsed)
            time.sleep(sleep_time)

    def _update_motor_data(self, motor_id: int, data: MotorData):
        if not self.motor_controller or not self.motor_controller.connected:
            return
        try:
            motor_data = self.motor_controller.read_motor_data(motor_id)
            data.position = motor_data.get('position')
            data.temperature = motor_data.get('temperature')
            data.voltage = motor_data.get('voltage')
            data.current = motor_data.get('current')
            data.load = motor_data.get('load')
            data.mode = motor_data.get('mode')
            data.moving = motor_data.get('moving')
            data.last_update = time.time()
            data.torque_enabled = self.motor_controller.get_torque_state(motor_id)
            if data.position is not None:
                data.error_count = 0
            else:
                data.error_count += 1
                if data.error_count > 5:
                    print(f"⚠️ Мотор {motor_id}: много ошибок чтения ({data.error_count})")
        except Exception as e:
            data.error_count += 1
            print(f"⚠️ Ошибка обновления мотора {motor_id}: {e}")

    def get_data(self, motor_id: int) -> Optional[MotorData]:
        with self.lock:
            return self.motor_data.get(motor_id)

    def get_all_data(self) -> Dict[int, MotorData]:
        with self.lock:
            return self.motor_data.copy()