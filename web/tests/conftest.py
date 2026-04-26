#!/usr/bin/env python3
"""
Pytest configuration and fixtures for web module tests.

Install dependencies:
    pip install pytest pytest-asyncio pytest-cov pytest-mock aiopika websockets

Run tests:
    pytest web/tests/ -v --cov=web
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

# Add parent directory to path
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)


@pytest.fixture(scope="session", autouse=True)
def _env_setup():
    """Setup environment variables for all tests."""
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-unit-tests-!@#%")
    os.environ.setdefault("JWT_ALGO", "HS256")
    os.environ.setdefault("TOKEN_EXP_H", "1")
    os.environ.setdefault("DEV_API_TOKEN", "test-dev-token-dev-only")


@pytest.fixture
def mocked_controller():
    """Mock MotorController for testing routes without hardware."""
    from unittest.mock import MagicMock
    
    mock = MagicMock()
    mock.is_connected = False
    mock.connect.return_value = True
    mock.disconnect.return_value = None
    mock.scan_servos.return_value = []
    mock.found_servos = []
    mock.read_motor_data.return_value = None
    
    return mock


@pytest.fixture
def connected_mock_controller():
    """Mock controller that is connected with dummy motor data."""
    from unittest.mock import MagicMock
    
    mock = MagicMock()
    mock.is_connected = True
    mock.connect.return_value = True
    mock.disconnect.return_value = None
    mock.scan_servos.return_value = [1, 2, 3, 4, 5, 6]
    mock.found_servos = [1, 2, 3, 4, 5, 6]
    
    # Mock motor data for each servo ID
    for i in range(1, 7):
        mock.read_motor_data.return_value = {
            "position": i * 100,
            "temperature": 45.0 + i,
            "voltage": 24.0,
            "current": 0.5 + i * 0.1,
            "load": 30 + i * 5,
            "moving": False,
            "mode": "position",
        }
    
    return mock


@pytest.fixture
def mock_ik():
    """Mock InverseKinematics for testing."""
    from unittest.mock import MagicMock
    
    mock = MagicMock()
    mock.solve.return_value = {
        "joint_0": 1500,
        "joint_1": 2000,
        "joint_2": 2500,
        "joint_3": 1000,
        "joint_4": 500,
        "joint_5": 150,
    }
    
    return mock


@pytest.fixture
def sample_jwt_token():
    """Generate a sample JWT token for testing auth."""
    try:
        import jwt as pyjwt
        return pyjwt.encode(
            {"username": "test_user", "sub": "test_id123"},
            os.environ["JWT_SECRET"],
            algorithm=os.environ["JWT_ALGO"]
        )
    except ImportError:
        return f"test-jwt-{os.environ.get('JWT_SECRET', 'secret')[:32]}".encode()


@pytest.fixture
def api_token():
    """Get the development API token."""
    return os.environ.get("DEV_API_TOKEN", "dev-token-change-in-production")


@pytest.fixture
def ml_service_mock():
    """Mock ML tracking service."""
    from unittest.mock import MagicMock
    
    mock = MagicMock()
    mock.get_state.return_value = MagicMock(
        is_running=False,
        model_name="",
        fps=0,
        frame_count=0,
        last_detection=None,
    )
    mock.start.return_value = None
    mock.stop.return_value = None
    
    return mock
