"""
Unit Tests for SNTP Mathematical Formulas (Offset, Round-Trip Delay, and Asymmetry).
"""

import unittest
from client.virtual_clock import VirtualClock


def calculate_sntp_offset_and_delay(t1: float, t2: float, t3: float, t4: float):
    """
    Standard RFC 4330 SNTP formulas:
      offset = ((T2 - T1) + (T3 - T4)) / 2
      delay  = (T4 - T1) - (T3 - T2)
    """
    offset = ((t2 - t1) + (t3 - t4)) / 2.0
    delay = (t4 - t1) - (t3 - t2)
    return offset, delay


class TestSNTPFormulas(unittest.TestCase):
    def test_ideal_symmetric_sync(self):
        """
        Suppose:
          True server time is T.
          Client clock is fast by +2.0 seconds (Client Time = True Time + 2.0).
          Forward delay = 0.020 s (20 ms).
          Server processing time = 0.002 s (2 ms).
          Return delay = 0.020 s (20 ms).
        """
        t_base = 1000.000
        client_error = 2.000  # Client is ahead by 2.0s
        d_fwd = 0.020
        d_srv = 0.002
        d_ret = 0.020

        # T1 stamped by client
        t1 = (t_base) + client_error                  # 1002.000

        # Packet arrives at server
        t2 = t_base + d_fwd                           # 1000.020

        # Server sends response
        t3 = t2 + d_srv                               # 1000.022

        # Packet arrives back at client
        t4 = (t_base + d_fwd + d_srv + d_ret) + client_error # 1002.042

        offset, delay = calculate_sntp_offset_and_delay(t1, t2, t3, t4)

        # Expected offset = -2.000 s (client must adjust backward by 2 seconds)
        self.assertAlmostEqual(offset, -2.000, places=6)
        
        # Expected round-trip delay = d_fwd + d_ret = 0.040 s (40 ms)
        self.assertAlmostEqual(delay, 0.040, places=6)

    def test_asymmetric_delay_error_theorem(self):
        """
        Theoretical Theorem:
        If the return path has an asymmetric delay increase of Delta over forward path:
          d_ret = d_fwd + Delta
        Then the computed offset will have an error equal to exactly -Delta / 2.
        """
        t_base = 1000.000
        client_error = 0.000  # Perfect client clock initially
        d_fwd = 0.010         # 10 ms forward
        d_srv = 0.001
        d_ret = 0.090         # 90 ms return (Delta = 80 ms)
        delta_asymmetry = d_ret - d_fwd  # +0.080 s

        t1 = t_base + client_error
        t2 = t_base + d_fwd
        t3 = t2 + d_srv
        t4 = (t_base + d_fwd + d_srv + d_ret) + client_error

        offset, delay = calculate_sntp_offset_and_delay(t1, t2, t3, t4)

        # SNTP miscalculates offset error by exactly -Delta / 2 = -0.040 s (-40 ms)
        expected_error = -delta_asymmetry / 2.0
        self.assertAlmostEqual(offset, expected_error, places=6)
        
        # Total network delay = 10 + 90 = 100 ms
        self.assertAlmostEqual(delay, 0.100, places=6)

    def test_virtual_clock_drift_and_adjustment(self):
        """Test virtual clock stepping and frequency drift calculation."""
        vclock = VirtualClock(initial_offset_sec=5.0, drift_ppm=0.0)
        
        # Initial error should be approximately 5.0 seconds
        self.assertAlmostEqual(vclock.get_true_error(), 5.0, places=2)

        # Apply correction of -5.0 seconds
        vclock.adjust(-5.0)
        
        # After correction, error should be approximately 0.0 seconds
        self.assertAlmostEqual(vclock.get_true_error(), 0.0, places=2)


if __name__ == "__main__":
    unittest.main()
