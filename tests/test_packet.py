"""
Unit Tests for SNTP Packet Serialization and Timestamp Conversion.
"""

import unittest
import time
from server.packet import (
    SNTPPacket,
    SNTP_PACKET_SIZE,
    NTP_EPOCH_DELTA,
    system_to_ntp_timestamp,
    ntp_to_system_timestamp,
)


class TestSNTPPacket(unittest.TestCase):
    def test_packet_size_is_48_bytes(self):
        """RFC 4330 / RFC 5905 strictly specifies a 48-byte header."""
        self.assertEqual(SNTP_PACKET_SIZE, 48)
        pkt = SNTPPacket()
        packed_bytes = pkt.pack()
        self.assertEqual(len(packed_bytes), 48)

    def test_ntp_epoch_constant(self):
        """Verify NTP 1900 vs Unix 1970 epoch delta is exactly 2,208,988,800 seconds."""
        # 17 leap years (1904 to 1968) * 366 + 53 regular years * 365 = 25,567 days * 86,400 = 2,208,988,800
        self.assertEqual(NTP_EPOCH_DELTA, 2208988800)

    def test_timestamp_conversion_roundtrip(self):
        """Converting Unix float -> NTP (sec, frac) -> Unix float must preserve accuracy."""
        test_times = [
            0.0,                    # Unix epoch start (1970-01-01)
            1710000000.123456,      # Arbitrary modern timestamp with microseconds
            time.time(),            # Current wall time
        ]
        for t in test_times:
            ntp_sec, ntp_frac = system_to_ntp_timestamp(t)
            reconstructed = ntp_to_system_timestamp(ntp_sec, ntp_frac)
            self.assertAlmostEqual(t, reconstructed, places=5)

    def test_packet_pack_and_unpack(self):
        """Pack an SNTP packet and unpack it; verify all fields match."""
        now = time.time()
        pkt = SNTPPacket(
            li=1,                   # Leap indicator
            vn=4,                   # Version 4
            mode=4,                 # Server
            stratum=1,              # Stratum 1
            poll=6,
            precision=-20,
            root_delay=65536,
            root_dispersion=32768,
            ref_id=b"GPS\x00",
            ref_timestamp=now - 100,
            orig_timestamp=now - 50,
            recv_timestamp=now - 10,
            tx_timestamp=now,
        )

        data = pkt.pack()
        self.assertEqual(len(data), 48)

        unpacked = SNTPPacket.unpack(data)
        self.assertEqual(unpacked.li, 1)
        self.assertEqual(unpacked.vn, 4)
        self.assertEqual(unpacked.mode, 4)
        self.assertEqual(unpacked.stratum, 1)
        self.assertEqual(unpacked.poll, 6)
        self.assertEqual(unpacked.precision, -20)
        self.assertEqual(unpacked.root_delay, 65536)
        self.assertEqual(unpacked.root_dispersion, 32768)
        self.assertEqual(unpacked.ref_id, b"GPS\x00")
        
        self.assertAlmostEqual(unpacked.ref_timestamp, pkt.ref_timestamp, places=4)
        self.assertAlmostEqual(unpacked.orig_timestamp, pkt.orig_timestamp, places=4)
        self.assertAlmostEqual(unpacked.recv_timestamp, pkt.recv_timestamp, places=4)
        self.assertAlmostEqual(unpacked.tx_timestamp, pkt.tx_timestamp, places=4)

    def test_unpack_short_data_raises_error(self):
        """Attempting to unpack fewer than 48 bytes should raise a ValueError."""
        with self.assertRaises(ValueError):
            SNTPPacket.unpack(b"too_short_packet")

    def test_inspect_dict_generation(self):
        """Verify inspector dictionary contains all required diagnostic fields."""
        pkt = SNTPPacket(li=0, vn=4, mode=3, stratum=0, tx_timestamp=time.time())
        info = pkt.to_inspect_dict()
        self.assertIn("hex_dump", info)
        self.assertIn("li", info)
        self.assertIn("vn", info)
        self.assertIn("mode", info)
        self.assertIn("stratum", info)
        self.assertIn("tx_timestamp", info)


if __name__ == "__main__":
    unittest.main()
