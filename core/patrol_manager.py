import threading
import time
from typing import List, Callable, Optional


class PatrolManager:
    """Gestor simple para patrullaje de presets"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._presets: List[str] = []
        self._interval: int = 10
        self._ptz_camera = None
        self._index: int = 0
        self._log_callback: Optional[Callable[[str], None]] = None

    def start(self, ptz_camera, presets: List[str], interval: int = 10,
              log_callback: Optional[Callable[[str], None]] = None) -> None:
        """Iniciar patrullaje en un hilo de fondo."""
        self.stop()
        self._ptz_camera = ptz_camera
        self._presets = presets
        self._interval = interval
        self._index = 0
        self._log_callback = log_callback
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while self._running and self._ptz_camera and self._presets:
            preset = self._presets[self._index % len(self._presets)]
            try:
                self._ptz_camera.goto_preset(str(preset))
                if self._log_callback:
                    self._log_callback(f"📍 Patrulla: preset {preset}")
            except Exception as e:
                if self._log_callback:
                    self._log_callback(f"❌ Error yendo a preset {preset}: {e}")
            self._index += 1
            for _ in range(int(self._interval * 10)):
                if not self._running:
                    break
                time.sleep(0.1)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        self._thread = None

    def is_running(self) -> bool:
        return self._running

    @property
    def interval(self) -> int:
        return self._interval

    @interval.setter
    def interval(self, value: int) -> None:
        self._interval = int(value)


global_patrol_manager = PatrolManager()
