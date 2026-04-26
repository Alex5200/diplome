#!/usr/bin/env python3

"""
Mock Tests for Motor Controller Module
Tests for motor_controller.py and motor_monitor.py
"""

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Добавляем родительскую директорию в path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


class TestMotorController(unittest.TestCase):
    """Tests for MotorController class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock the ST3215 class before importing MotorController
        self.st3215_patcher = patch("app.controllers.motor_controller.ST3215")
        self.mock_st3215_class = self.st3215_patcher.start()
        self.mock_motor_instance = MagicMock()
        self.mock_st3215_class.return_value = self.mock_motor_instance

        from app.controllers.motor_controller import MotorController

        self.controller = MotorController(device="COM3")

    def tearDown(self):
        """Clean up"""
        self.st3215_patcher.stop()

    def test_init_default_values(self):
        """Test controller initialization with default values"""
        self.assertEqual(self.controller.device, "COM3")
        self.assertFalse(self.controller.connected)
        self.assertEqual(self.controller.found_servos, [])
        self.assertIsNone(self.controller.current_id)
        self.assertEqual(self.controller.torque_states, {})
        self.assertIsInstance(self.controller.joint_positions, dict)
        self.assertEqual(len(self.controller.joint_positions), 6)

    def test_connect_success(self):
        """Test successful connection to motor"""
        result = self.controller.connect()

        self.assertTrue(result)
        self.assertTrue(self.controller.connected)
        self.assertIsNotNone(self.controller.motor)
        self.mock_st3215_class.assert_called_once_with(device="COM3")

    def test_connect_failure(self):
        """Test connection failure handling"""
        self.mock_st3215_class.side_effect = Exception("Connection failed")

        result = self.controller.connect()

        self.assertFalse(result)
        self.assertFalse(self.controller.connected)
        self.assertIsNone(self.controller.motor)

    def test_disconnect(self):
        """Test disconnecting from motor"""
        self.controller.connect()
        self.controller.portHandler = MagicMock()

        self.controller.disconnect()

        self.assertFalse(self.controller.connected)
        self.assertIsNone(self.controller.motor)

    def test_scan_servos_success(self):
        """Test scanning for servos"""
        self.controller.connect()
        self.mock_motor_instance.ListServos.return_value = [1, 2, 3, 4, 5, 6]

        result = self.controller.scan_servos()

        self.assertEqual(result, [1, 2, 3, 4, 5, 6])
        self.assertEqual(self.controller.found_servos, [1, 2, 3, 4, 5, 6])
        self.mock_motor_instance.ListServos.assert_called_once()

    def test_scan_servos_not_connected(self):
        """Test scanning when not connected"""
        result = self.controller.scan_servos()

        self.assertEqual(result, [])

    def test_scan_servos_error(self):
        """Test scanning error handling"""
        self.controller.connect()
        self.mock_motor_instance.ListServos.side_effect = Exception("Scan failed")

        result = self.controller.scan_servos()

        self.assertEqual(result, [])

    def test_get_motor_id_for_joint_default(self):
        """Test getting motor ID for joint with default mapping"""
        for joint_index in range(6):
            motor_id = self.controller.get_motor_id_for_joint(joint_index)
            self.assertEqual(motor_id, joint_index + 1)

    def test_get_motor_id_for_joint_custom(self):
        """Test getting motor ID for joint with custom mapping"""
        self.controller.update_motor_mapping(0, 10, "Custom Base")

        motor_id = self.controller.get_motor_id_for_joint(0)

        self.assertEqual(motor_id, 10)

    def test_get_joint_name_default(self):
        """Test getting joint name with default mapping"""
        # Default mapping uses names from DEFAULT_MOTOR_MAPPING
        names = ["База", "Плечо 1", "Плечо 2", "Локоть", "Кисть 1", "Кисть 2"]

        for i, expected_name in enumerate(names):
            name = self.controller.get_joint_name(i)
            self.assertEqual(name, expected_name)

    def test_get_joint_name_custom(self):
        """Test getting joint name with custom mapping"""
        self.controller.update_motor_mapping(0, 1, "My Custom Joint")

        name = self.controller.get_joint_name(0)

        self.assertEqual(name, "My Custom Joint")

    def test_move_to_position_success(self):
        """Test moving motor to position"""
        self.controller.connect()
        self.mock_motor_instance.MoveTo.return_value = True

        result = self.controller.move_to_position(1, 2048, speed=3000)

        self.assertTrue(result)
        self.mock_motor_instance.MoveTo.assert_called_once_with(1, 2048, speed=3000, acc=50)

    def test_move_to_position_invalid_position_low(self):
        """Test moving motor with position below minimum"""
        result = self.controller.move_to_position(1, -1)

        self.assertFalse(result)
        self.mock_motor_instance.MoveTo.assert_not_called()

    def test_move_to_position_invalid_position_high(self):
        """Test moving motor with position above maximum"""
        result = self.controller.move_to_position(1, 5000)

        self.assertFalse(result)
        self.mock_motor_instance.MoveTo.assert_not_called()

    def test_move_to_position_not_connected(self):
        """Test moving motor when not connected"""
        result = self.controller.move_to_position(1, 2048)

        self.assertFalse(result)

    def test_move_to_position_error(self):
        """Test moving motor error handling"""
        self.controller.connect()
        self.mock_motor_instance.MoveTo.side_effect = Exception("Move failed")

        result = self.controller.move_to_position(1, 2048)

        self.assertFalse(result)

    def test_move_joint(self):
        """Test moving a specific joint"""
        self.controller.connect()
        self.mock_motor_instance.MoveTo.return_value = True

        result = self.controller.move_joint(0, 1024)

        self.assertTrue(result)
        self.mock_motor_instance.MoveTo.assert_called_once_with(1, 1024, speed=2400, acc=50)

    def test_move_all_joints(self):
        """Test moving all joints"""
        self.controller.connect()
        self.mock_motor_instance.MoveTo.return_value = True
        positions = [100, 200, 300, 400, 500, 600]

        result = self.controller.move_all_joints(positions)

        self.assertTrue(result)
        self.assertEqual(self.mock_motor_instance.MoveTo.call_count, 6)

    def test_toggle_torque_enable(self):
        """Test enabling torque"""
        self.controller.connect()
        self.mock_motor_instance.StartServo.return_value = True

        result = self.controller.toggle_torque(1, enable=True)

        self.assertTrue(result)
        self.assertTrue(self.controller.torque_states[1])
        self.mock_motor_instance.StartServo.assert_called_once_with(1)

    def test_toggle_torque_disable(self):
        """Test disabling torque"""
        self.controller.connect()
        self.mock_motor_instance.StopServo.return_value = True

        result = self.controller.toggle_torque(1, enable=False)

        self.assertTrue(result)
        self.assertFalse(self.controller.torque_states[1])
        self.mock_motor_instance.StopServo.assert_called_once_with(1)

    def test_toggle_torque_not_connected(self):
        """Test toggling torque when not connected"""
        result = self.controller.toggle_torque(1, enable=True)

        self.assertFalse(result)

    def test_toggle_torque_error(self):
        """Test torque toggle error handling"""
        self.controller.connect()
        self.mock_motor_instance.StartServo.side_effect = Exception("Torque failed")

        result = self.controller.toggle_torque(1, enable=True)

        self.assertFalse(result)

    def test_get_torque_state(self):
        """Test getting torque state"""
        self.controller.torque_states[1] = True
        self.controller.torque_states[2] = False

        self.assertTrue(self.controller.get_torque_state(1))
        self.assertFalse(self.controller.get_torque_state(2))
        self.assertFalse(self.controller.get_torque_state(99))

    def test_emergency_stop_all(self):
        """Test emergency stop of all motors"""
        self.controller.connect()
        self.controller.found_servos = [1, 2, 3]
        self.mock_motor_instance.StopServo.return_value = True

        self.controller.emergency_stop_all()

        self.assertEqual(self.mock_motor_instance.StopServo.call_count, 3)
        self.assertFalse(self.controller.torque_states[1])
        self.assertFalse(self.controller.torque_states[2])
        self.assertFalse(self.controller.torque_states[3])

    def test_get_joint_positions(self):
        """Test getting joint positions"""
        self.controller.joint_positions = {1: 100.0, 2: 200.0, 3: 300.0}

        result = self.controller.get_joint_positions()

        self.assertEqual(result, {1: 100.0, 2: 200.0, 3: 300.0})
        self.assertIsNot(result, self.controller.joint_positions)  # Returns copy

    def test_read_motor_data_success(self):
        """Test reading motor data"""
        self.controller.connect()
        self.mock_motor_instance.ReadPosition.return_value = 2048
        self.mock_motor_instance.ReadTemperature.return_value = 45.5
        self.mock_motor_instance.ReadVoltage.return_value = 12.0
        self.mock_motor_instance.ReadCurrent.return_value = 0.5
        self.mock_motor_instance.ReadLoad.return_value = 30.0
        self.mock_motor_instance.ReadMode.return_value = 0
        self.mock_motor_instance.IsMoving.return_value = False

        result = self.controller.read_motor_data(1)

        self.assertEqual(result["position"], 2048)
        self.assertEqual(result["temperature"], 45.5)
        self.assertEqual(result["voltage"], 12.0)
        self.assertEqual(result["current"], 0.5)
        self.assertEqual(result["load"], 30.0)
        self.assertEqual(result["mode"], 0)
        self.assertFalse(result["moving"])

    def test_read_motor_data_not_connected(self):
        """Test reading motor data when not connected"""
        result = self.controller.read_motor_data(1)

        self.assertEqual(result, {})

    def test_read_motor_data_error(self):
        """Test reading motor data error handling"""
        self.controller.connect()
        self.mock_motor_instance.ReadPosition.side_effect = Exception("Read failed")

        result = self.controller.read_motor_data(1)

        self.assertEqual(result["position"], None)

    def test_set_manual_speed(self):
        """Test setting manual speed"""
        self.controller.set_manual_speed(5000)

        self.assertEqual(self.controller.get_manual_speed(), 5000)

    def test_set_manual_speed_bounds(self):
        """Test manual speed bounds clamping"""
        self.controller.set_manual_speed(-100)
        self.assertEqual(self.controller.get_manual_speed(), 0)

        self.controller.set_manual_speed(20000)
        self.assertEqual(self.controller.get_manual_speed(), 10000)

    def test_update_motor_mapping(self):
        """Test updating motor mapping"""
        self.controller.update_motor_mapping(0, 10, "New Base")

        self.assertEqual(self.controller.motor_mapping["joint_0"]["motor_id"], 10)
        self.assertEqual(self.controller.motor_mapping["joint_0"]["name"], "New Base")

    def test_update_motor_mapping_default_name(self):
        """Test updating motor mapping with default name"""
        self.controller.update_motor_mapping(0, 10)

        self.assertEqual(self.controller.motor_mapping["joint_0"]["name"], "🏗️ База")

    def test_get_motor_mapping(self):
        """Test getting motor mapping"""
        result = self.controller.get_motor_mapping()

        self.assertIsInstance(result, dict)
        self.assertIsNot(result, self.controller.motor_mapping)  # Returns copy

    def test_update_motor_config(self):
        """Test updating motor configuration"""
        self.controller.update_motor_config(1, 100, 4000, "Configured Motor")

        self.assertEqual(self.controller.motor_config["motor_1"]["min_pos"], 100)
        self.assertEqual(self.controller.motor_config["motor_1"]["max_pos"], 4000)
        self.assertEqual(self.controller.motor_config["motor_1"]["name"], "Configured Motor")

    def test_get_motor_config(self):
        """Test getting motor configuration"""
        config = self.controller.get_motor_config(1)

        self.assertIn("min_pos", config)
        self.assertIn("max_pos", config)
        self.assertIn("name", config)

    def test_get_motor_config_not_found(self):
        """Test getting non-existent motor configuration"""
        config = self.controller.get_motor_config(999)

        self.assertEqual(config["min_pos"], 0)
        self.assertEqual(config["max_pos"], 4095)
        self.assertEqual(config["name"], "Мотор 999")

    @patch("app.controllers.motor_controller.open")
    @patch("app.controllers.motor_controller.json.dump")
    def test_save_config(self, mock_json_dump, mock_open):
        """Test saving configuration to file"""
        result = self.controller.save_config("test_config.json")

        self.assertTrue(result)
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()

    @patch("app.controllers.motor_controller.open")
    def test_save_config_error(self, mock_open):
        """Test save configuration error handling"""
        mock_open.side_effect = Exception("File write error")

        result = self.controller.save_config("test_config.json")

        self.assertFalse(result)

    @patch("app.controllers.motor_controller.open")
    @patch("app.controllers.motor_controller.json.load")
    def test_load_config(self, mock_json_load, mock_open):
        """Test loading configuration from file"""
        mock_json_load.return_value = {
            "motor_config": {"motor_1": {"min_pos": 100, "max_pos": 4000}},
            "motor_mapping": {"joint_0": {"motor_id": 10}},
            "port": "COM5",
        }

        result = self.controller.load_config("test_config.json")

        self.assertTrue(result)
        self.assertEqual(self.controller.device, "COM5")
        self.assertIn("motor_1", self.controller.motor_config)

    @patch("app.controllers.motor_controller.open")
    def test_load_config_error(self, mock_open):
        """Test load configuration error handling"""
        mock_open.side_effect = Exception("File read error")

        result = self.controller.load_config("test_config.json")

        self.assertFalse(result)


class TestMotorMonitor(unittest.TestCase):
    """Tests for MotorMonitor class"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock dependencies
        self.controller_patcher = patch("app.controllers.motor_monitor.MotorController")
        self.mock_controller = self.controller_patcher.start()
        self.mock_controller_instance = MagicMock()
        self.mock_controller.return_value = self.mock_controller_instance

        from app.controllers.motor_monitor import MotorMonitor

        self.monitor = MotorMonitor(self.mock_controller_instance)

    def tearDown(self):
        """Clean up"""
        self.controller_patcher.stop()

    def test_init_default_values(self):
        """Test monitor initialization"""
        self.assertEqual(self.monitor.motor_controller, self.mock_controller_instance)
        self.assertFalse(self.monitor.running)
        self.assertIsNone(self.monitor.thread)
        self.assertEqual(self.monitor.motor_data, {})
        self.assertIsInstance(self.monitor.lock, type(threading.Lock()))

    def test_start(self):
        """Test starting the monitor"""
        motor_ids = [1, 2, 3]

        self.monitor.start(motor_ids)

        self.assertTrue(self.monitor.running)
        self.assertIsNotNone(self.monitor.thread)
        self.assertEqual(len(self.monitor.motor_data), 3)
        self.assertIn(1, self.monitor.motor_data)
        self.assertIn(2, self.monitor.motor_data)
        self.assertIn(3, self.monitor.motor_data)

    def test_start_already_running(self):
        """Test starting monitor when already running"""
        self.monitor.running = True

        self.monitor.start([1, 2, 3])

        # Thread should not be started again
        self.assertTrue(self.monitor.running)
        self.assertIsNone(self.monitor.thread)

    def test_stop(self):
        """Test stopping the monitor"""
        self.monitor.running = True
        self.monitor.thread = MagicMock()

        self.monitor.stop()

        self.assertFalse(self.monitor.running)
        self.monitor.thread.join.assert_called_once_with(timeout=2.0)

    def test_get_data(self):
        """Test getting data for specific motor"""
        from app.models.motor_data import MotorData

        test_data = MotorData(motor_id=1, position=2048, temperature=45.0)
        self.monitor.motor_data[1] = test_data

        result = self.monitor.get_data(1)

        self.assertEqual(result.motor_id, 1)
        self.assertEqual(result.position, 2048)
        self.assertEqual(result.temperature, 45.0)

    def test_get_data_not_found(self):
        """Test getting data for non-existent motor"""
        result = self.monitor.get_data(999)

        self.assertIsNone(result)

    def test_get_all_data(self):
        """Test getting all motor data"""
        from app.models.motor_data import MotorData

        self.monitor.motor_data[1] = MotorData(motor_id=1, position=100)
        self.monitor.motor_data[2] = MotorData(motor_id=2, position=200)

        result = self.monitor.get_all_data()

        self.assertEqual(len(result), 2)
        self.assertIsNot(result, self.monitor.motor_data)  # Returns copy

    @patch("app.controllers.motor_monitor.time.time")
    @patch("app.controllers.motor_monitor.time.sleep")
    def test_monitor_loop(self, mock_sleep, mock_time):
        """Test the monitoring loop"""
        mock_time.side_effect = [0.0, 0.1, 0.2, 1.0]  # Simulate time passing

        self.mock_controller_instance.connected = True
        self.mock_controller_instance.read_motor_data.return_value = {
            "position": 2048,
            "temperature": 45.0,
            "voltage": 12.0,
            "current": 0.5,
            "load": 30.0,
            "mode": 0,
            "moving": False,
        }

        self.monitor.start([1])
        self.monitor.running = False  # Stop after one iteration

        # Verify read_motor_data was called
        self.mock_controller_instance.read_motor_data.assert_called()

    def test_update_motor_data_not_connected(self):
        """Test updating motor data when not connected"""
        from app.models.motor_data import MotorData

        motor_data = MotorData(motor_id=1)

        self.mock_controller_instance.connected = False

        self.monitor._update_motor_data(1, motor_data)

        self.mock_controller_instance.read_motor_data.assert_not_called()

    def test_update_motor_data_success(self):
        """Test successful motor data update"""
        from app.models.motor_data import MotorData

        motor_data = MotorData(motor_id=1)

        self.mock_controller_instance.connected = True
        self.mock_controller_instance.read_motor_data.return_value = {
            "position": 2048,
            "temperature": 45.0,
            "voltage": 12.0,
            "current": 0.5,
            "load": 30.0,
            "mode": 0,
            "moving": False,
        }
        self.mock_controller_instance.get_torque_state.return_value = True

        self.monitor._update_motor_data(1, motor_data)

        self.assertEqual(motor_data.position, 2048)
        self.assertEqual(motor_data.temperature, 45.0)
        self.assertEqual(motor_data.voltage, 12.0)
        self.assertEqual(motor_data.current, 0.5)
        self.assertEqual(motor_data.load, 30.0)
        self.assertEqual(motor_data.mode, 0)
        self.assertFalse(motor_data.moving)
        self.assertTrue(motor_data.torque_enabled)
        self.assertEqual(motor_data.error_count, 0)

    def test_update_motor_data_with_errors(self):
        """Test motor data update with read errors"""
        from app.models.motor_data import MotorData

        motor_data = MotorData(motor_id=1, error_count=0)

        self.mock_controller_instance.connected = True
        self.mock_controller_instance.read_motor_data.return_value = {
            "position": None,  # Simulate read failure
            "temperature": None,
            "voltage": None,
            "current": None,
            "load": None,
            "mode": None,
            "moving": None,
        }

        self.monitor._update_motor_data(1, motor_data)

        self.assertEqual(motor_data.error_count, 1)

    def test_update_motor_data_exception(self):
        """Test motor data update exception handling"""
        from app.models.motor_data import MotorData

        motor_data = MotorData(motor_id=1, error_count=0)

        self.mock_controller_instance.connected = True
        self.mock_controller_instance.read_motor_data.side_effect = Exception("Read error")

        self.monitor._update_motor_data(1, motor_data)

        self.assertEqual(motor_data.error_count, 1)


class TestMotorDataModel(unittest.TestCase):
    """Tests for MotorData model"""

    def setUp(self):
        """Set up test fixtures"""
        from app.models.motor_data import MotorData

        self.MotorData = MotorData

    def test_motor_data_default_values(self):
        """Test MotorData default values"""
        data = self.MotorData(motor_id=1)

        self.assertEqual(data.motor_id, 1)
        self.assertIsNone(data.position)
        self.assertIsNone(data.temperature)
        self.assertIsNone(data.voltage)
        self.assertIsNone(data.current)
        self.assertIsNone(data.load)
        self.assertIsNone(data.mode)
        self.assertIsNone(data.moving)
        self.assertFalse(data.torque_enabled)
        self.assertEqual(data.error_count, 0)

    def test_motor_data_with_values(self):
        """Test MotorData with specific values"""
        data = self.MotorData(
            motor_id=1,
            position=2048,
            temperature=45.5,
            voltage=12.0,
            current=0.5,
            load=30.0,
            mode=0,
            moving=False,
            torque_enabled=True,
        )

        self.assertEqual(data.position, 2048)
        self.assertEqual(data.temperature, 45.5)
        self.assertEqual(data.voltage, 12.0)
        self.assertEqual(data.current, 0.5)
        self.assertEqual(data.load, 30.0)
        self.assertEqual(data.mode, 0)
        self.assertFalse(data.moving)
        self.assertTrue(data.torque_enabled)

    def test_is_overheating_false(self):
        """Test is_overheating when temperature is normal"""
        data = self.MotorData(motor_id=1, temperature=50.0)

        self.assertFalse(data.is_overheating())

    def test_is_overheating_warning(self):
        """Test is_overheating at warning threshold"""
        data = self.MotorData(motor_id=1, temperature=70.0)

        self.assertFalse(data.is_overheating())  # Warning, not critical

    def test_is_overheating_critical(self):
        """Test is_overheating at critical temperature"""
        data = self.MotorData(motor_id=1, temperature=80.0)

        self.assertTrue(data.is_overheating())

    def test_is_overheating_no_temperature(self):
        """Test is_overheating when temperature is None"""
        data = self.MotorData(motor_id=1, temperature=None)

        self.assertFalse(data.is_overheating())

    def test_to_dict(self):
        """Test converting MotorData to dict"""
        data = self.MotorData(motor_id=1, position=2048, temperature=45.0)

        result = data.to_dict()

        self.assertIsInstance(result, dict)
        self.assertEqual(result["motor_id"], 1)
        self.assertEqual(result["position"], 2048)
        self.assertEqual(result["temperature"], 45.0)


if __name__ == "__main__":
    unittest.main()
