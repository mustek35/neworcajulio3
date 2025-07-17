import unittest
from types import SimpleNamespace
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core.multi_object_ptz_system import (
    MultiObjectPTZTracker,
    MultiObjectConfig,
    create_multi_object_tracker,
)

class MockPTZService:
    def __init__(self, with_absolute=True):
        self.with_absolute = with_absolute
        self.last_move = None
    def create_type(self, name):
        return SimpleNamespace(ProfileToken=None, Position=None, Velocity=None)
    def AbsoluteMove(self, req):
        if self.with_absolute:
            self.last_move = ('Absolute', req)
        else:
            raise AttributeError('AbsoluteMove not supported')
    def ContinuousMove(self, req):
        self.last_move = ('Continuous', req)
    def GetStatus(self, req):
        return SimpleNamespace(Position=SimpleNamespace(PanTilt=SimpleNamespace(x=0.0, y=0.0), Zoom=SimpleNamespace(x=0.0)))

class MockPTZServiceNoAbs:
    def __init__(self):
        self.last_move = None
    def create_type(self, name):
        return SimpleNamespace(ProfileToken=None, Position=None, Velocity=None)
    def ContinuousMove(self, req):
        self.last_move = ('Continuous', req)
    def GetStatus(self, req):
        return SimpleNamespace(Position=SimpleNamespace(PanTilt=SimpleNamespace(x=0.0, y=0.0), Zoom=SimpleNamespace(x=0.0)))

class MockCamera:
    def __init__(self):
        self.calls = []
    def absolute_move(self, pan, tilt, zoom, speed=None):
        self.calls.append((pan, tilt, zoom))
    def continuous_move(self, pan, tilt, zoom_speed=0.0):
        self.calls.append(('cont', pan, tilt))

class AbsoluteMoveTests(unittest.TestCase):
    def test_service_absolute_move_used(self):
        cfg = MultiObjectConfig(use_absolute_move=True)
        tracker = MultiObjectPTZTracker('0.0.0.0', 80, 'u', 'p', multi_config=cfg)
        tracker.ptz_service = MockPTZService()
        tracker.profile_token = 't'
        tracker._send_ptz_command(0.5, -0.2)
        self.assertEqual(tracker.ptz_service.last_move[0], 'Absolute')

    def test_camera_absolute_move_fallback(self):
        cfg = MultiObjectConfig(use_absolute_move=True)
        tracker = MultiObjectPTZTracker('0.0.0.0', 80, 'u', 'p', multi_config=cfg)
        tracker.ptz_service = MockPTZServiceNoAbs()
        tracker.camera = MockCamera()
        tracker.profile_token = 't'
        tracker._send_ptz_command(0.3, 0.1)
        self.assertTrue(tracker.camera.calls)
        self.assertEqual(tracker.camera.calls[0][0], tracker.current_pan_position)


class PresetPropagationTests(unittest.TestCase):
    def test_preset_enables_absolute_move(self):
        tracker = create_multi_object_tracker(
            '0.0.0.0', 80, 'u', 'p', 'surveillance_precise'
        )
        self.assertTrue(tracker.multi_config.use_absolute_move)

    def test_preset_default_false(self):
        tracker = create_multi_object_tracker(
            '0.0.0.0', 80, 'u', 'p', 'maritime_standard'
        )
        self.assertFalse(tracker.multi_config.use_absolute_move)

if __name__ == '__main__':
    unittest.main()