"""
Virtual Client Clock Simulator.

Simulates a client's local hardware oscillator with:
- Configurable initial clock error (e.g. +5.0 seconds fast or -3.0 seconds slow)
- Hardware oscillator frequency drift (measured in PPM: Parts Per Million)
- Discipline/Adjustment mechanism (step adjustment based on calculated SNTP offset)

Safely operates completely in software without modifying the host OS clock!
"""

import time
import threading
from typing import Dict, Any


class VirtualClock:
    """
    Virtual Clock simulating oscillator dynamics.
    
    Time Formula:
      Let real_now = time.time()
      elapsed_real = real_now - last_real_update
      virtual_elapsed = elapsed_real * (1.0 + (drift_ppm * 1e-6))
      current_virtual_time = last_virtual_time + virtual_elapsed
    """

    def __init__(self, initial_offset_sec: float = 5.0, drift_ppm: float = 50.0):
        """
        Args:
            initial_offset_sec: Initial difference from true time in seconds (e.g. +5.0s).
            drift_ppm: Frequency error in parts-per-million (e.g. +50 ppm = gains 50 us every second).
        """
        self.lock = threading.RLock()
        self.initial_offset = float(initial_offset_sec)
        self.drift_ppm = float(drift_ppm)

        # Baseline anchors
        self._last_real_time = time.time()
        self._accumulated_virtual_time = self._last_real_time + self.initial_offset
        self.total_adjustments_applied = 0.0
        self.adjustment_count = 0

    def get_time(self) -> float:
        """
        Returns the current virtual time timestamp (in seconds, Unix epoch equivalent).
        Advances with simulated drift relative to real elapsed wall time.
        """
        with self.lock:
            now_real = time.time()
            elapsed_real = now_real - self._last_real_time
            
            # Apply drift rate to elapsed real time
            drift_factor = 1.0 + (self.drift_ppm * 1e-6)
            elapsed_virtual = elapsed_real * drift_factor

            self._accumulated_virtual_time += elapsed_virtual
            self._last_real_time = now_real
            return self._accumulated_virtual_time

    def adjust(self, offset_correction_sec: float):
        """
        Applies a clock correction (in seconds) computed by the SNTP synchronization step.
        If offset_correction > 0, the clock was behind the server and is stepped forward.
        If offset_correction < 0, the clock was ahead of the server and is stepped backward.
        """
        with self.lock:
            # First advance to current instant
            _ = self.get_time()
            # Step the virtual clock by the computed offset
            self._accumulated_virtual_time += offset_correction_sec
            self.total_adjustments_applied += offset_correction_sec
            self.adjustment_count += 1

    def get_true_error(self) -> float:
        """
        Returns the true current error (virtual_time - true_system_time) in seconds.
        This provides ground-truth metric for evaluating synchronization accuracy.
        """
        current_vtime = self.get_time()
        current_true = time.time()
        return current_vtime - current_true

    def reset(self, initial_offset_sec: float = None, drift_ppm: float = None):
        """Resets the virtual clock to given parameters."""
        with self.lock:
            if initial_offset_sec is not None:
                self.initial_offset = float(initial_offset_sec)
            if drift_ppm is not None:
                self.drift_ppm = float(drift_ppm)

            self._last_real_time = time.time()
            self._accumulated_virtual_time = self._last_real_time + self.initial_offset
            self.total_adjustments_applied = 0.0
            self.adjustment_count = 0

    def get_state(self) -> Dict[str, Any]:
        """Returns clock diagnostic state for dashboard inspection."""
        v_now = self.get_time()
        t_now = time.time()
        true_err = v_now - t_now
        return {
            "virtual_time": v_now,
            "true_time": t_now,
            "true_error_sec": true_err,
            "true_error_ms": true_err * 1000.0,
            "drift_ppm": self.drift_ppm,
            "initial_offset": self.initial_offset,
            "adjustment_count": self.adjustment_count,
            "total_adjustments_applied": self.total_adjustments_applied,
        }
