"""
SNTP Packet Definition and Serialization (RFC 4330 / RFC 5905).

This module defines the 48-byte packet structure used by SNTP/NTP,
along with utilities to convert between Unix epoch (1970) and NTP epoch (1900).
"""

import struct
import time
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, Any

# Difference in seconds between NTP epoch (1900-01-01) and Unix epoch (1970-01-01)
# 70 years = 17 leap years + 53 normal years = 25,567 days * 86,400 s/day = 2,208,988,800 s
NTP_EPOCH_DELTA: int = 2208988800

# 48-byte SNTP packet struct format:
# ! = Network byte order (big-endian)
# B = uint8  (LI, VN, Mode packed into 1 byte)
# B = uint8  (Stratum)
# b = int8   (Poll interval)
# b = int8   (Precision)
# I = uint32 (Root Delay - fixed point)
# I = uint32 (Root Dispersion - fixed point)
# 4s= 4-byte ASCII/binary (Reference ID)
# Followed by 4 pairs of uint32 (sec, frac) for 64-bit NTP timestamps:
# Reference Timestamp (I, I), Originate Timestamp (I, I),
# Receive Timestamp (I, I), Transmit Timestamp (I, I)
SNTP_PACKET_FORMAT: str = "!BBbbII4sIIIIIIII"
SNTP_PACKET_SIZE: int = struct.calcsize(SNTP_PACKET_FORMAT)  # Exactly 48 bytes


def system_to_ntp_timestamp(unix_time: float) -> Tuple[int, int]:
    """
    Converts a Unix floating-point timestamp (seconds since 1970)
    into an NTP 64-bit timestamp represented as (seconds_since_1900, fraction_of_second).
    
    Fraction is scaled to a 32-bit integer (multiplied by 2^32).
    """
    ntp_total = unix_time + NTP_EPOCH_DELTA
    ntp_seconds = int(ntp_total)
    ntp_fraction = int((ntp_total - ntp_seconds) * (2 ** 32))
    return ntp_seconds, ntp_fraction


def ntp_to_system_timestamp(ntp_seconds: int, ntp_fraction: int) -> float:
    """
    Converts an NTP 64-bit timestamp (ntp_seconds, ntp_fraction)
    into a Unix floating-point timestamp (seconds since 1970).
    """
    if ntp_seconds == 0 and ntp_fraction == 0:
        return 0.0
    unix_time = (ntp_seconds + (ntp_fraction / (2 ** 32))) - NTP_EPOCH_DELTA
    return unix_time


@dataclass
class SNTPPacket:
    """
    Represents an RFC 4330 48-byte SNTP Datagram.
    """
    li: int = 0             # Leap Indicator (2 bits): 0 = no warning, 3 = alarm (clock not synced)
    vn: int = 4             # Version Number (3 bits): 4 for SNTPv4
    mode: int = 3           # Mode (3 bits): 3 = client request, 4 = server reply
    stratum: int = 0        # Stratum (1 byte): 0 = unspecified/kiss-o'-death, 1 = primary, 2 = secondary
    poll: int = 4           # Maximum interval between successive messages (log2 seconds)
    precision: int = -20    # Precision of the local clock (log2 seconds, ~1 microsecond)
    root_delay: int = 0     # Total round-trip delay to reference clock
    root_dispersion: int = 0# Maximum error with respect to reference clock
    ref_id: bytes = b"LOCL" # 4-character ID (e.g. b'LOCL', b'SIMU', b'GPS\0')
    
    # 64-bit timestamps stored as float seconds in Unix epoch (1970) for easy manipulation:
    ref_timestamp: float = 0.0   # Reference timestamp: time when local clock was last set
    orig_timestamp: float = 0.0  # T1: Originate timestamp (time request departed client)
    recv_timestamp: float = 0.0  # T2: Receive timestamp (time request arrived at server)
    tx_timestamp: float = 0.0    # T3: Transmit timestamp (time response departed server)

    def pack(self) -> bytes:
        """
        Serializes the SNTPPacket into standard 48-byte network wire format.
        """
        # Pack LI (2 bits), VN (3 bits), and Mode (3 bits) into single first byte
        first_byte = ((self.li & 0x03) << 6) | ((self.vn & 0x07) << 3) | (self.mode & 0x07)
        
        # Ensure ref_id is 4 bytes
        ref_id_bytes = self.ref_id[:4].ljust(4, b"\x00")
        
        # Convert timestamps from Unix float to NTP (sec, frac) pairs
        ref_sec, ref_frac = system_to_ntp_timestamp(self.ref_timestamp)
        orig_sec, orig_frac = system_to_ntp_timestamp(self.orig_timestamp)
        recv_sec, recv_frac = system_to_ntp_timestamp(self.recv_timestamp)
        tx_sec, tx_frac = system_to_ntp_timestamp(self.tx_timestamp)

        return struct.pack(
            SNTP_PACKET_FORMAT,
            first_byte,
            self.stratum,
            self.poll,
            self.precision,
            self.root_delay,
            self.root_dispersion,
            ref_id_bytes,
            ref_sec, ref_frac,
            orig_sec, orig_frac,
            recv_sec, recv_frac,
            tx_sec, tx_frac,
        )

    @classmethod
    def unpack(cls, data: bytes) -> "SNTPPacket":
        """
        Deserializes a 48-byte buffer into an SNTPPacket instance.
        """
        if len(data) < SNTP_PACKET_SIZE:
            raise ValueError(f"Packet too short: got {len(data)} bytes, expected {SNTP_PACKET_SIZE}")

        fields = struct.unpack(SNTP_PACKET_FORMAT, data[:SNTP_PACKET_SIZE])
        
        first_byte = fields[0]
        li = (first_byte >> 6) & 0x03
        vn = (first_byte >> 3) & 0x07
        mode = first_byte & 0x07
        
        stratum = fields[1]
        poll = fields[2]
        precision = fields[3]
        root_delay = fields[4]
        root_dispersion = fields[5]
        ref_id = fields[6]

        ref_ts = ntp_to_system_timestamp(fields[7], fields[8])
        orig_ts = ntp_to_system_timestamp(fields[9], fields[10])
        recv_ts = ntp_to_system_timestamp(fields[11], fields[12])
        tx_ts = ntp_to_system_timestamp(fields[13], fields[14])

        return cls(
            li=li,
            vn=vn,
            mode=mode,
            stratum=stratum,
            poll=poll,
            precision=precision,
            root_delay=root_delay,
            root_dispersion=root_dispersion,
            ref_id=ref_id,
            ref_timestamp=ref_ts,
            orig_timestamp=orig_ts,
            recv_timestamp=recv_ts,
            tx_timestamp=tx_ts,
        )

    def to_inspect_dict(self, raw_bytes: bytes = None) -> Dict[str, Any]:
        """
        Returns a detailed structured representation of packet fields
        for the dashboard Packet Inspector.
        """
        if raw_bytes is None:
            raw_bytes = self.pack()

        hex_dump = raw_bytes.hex().upper()
        # Format hex into space-separated byte pairs
        formatted_hex = " ".join(hex_dump[i:i+2] for i in range(0, len(hex_dump), 2))

        mode_names = {
            1: "Symmetric Active",
            2: "Symmetric Passive",
            3: "Client Request",
            4: "Server Response",
            5: "Broadcast",
        }

        li_names = {
            0: "No warning",
            1: "Last minute of day has 61 seconds (Leap second added)",
            2: "Last minute of day has 59 seconds (Leap second deleted)",
            3: "Alarm condition (Clock not synchronized)",
        }

        stratum_desc = "Primary reference (e.g. GPS, atomic clock)" if self.stratum == 1 else \
                       f"Secondary reference (Stratum {self.stratum})" if 1 < self.stratum < 16 else \
                       "Unsynchronized / Kiss-of-Death"

        try:
            ref_id_str = self.ref_id.decode("ascii", errors="replace").strip("\x00")
        except Exception:
            ref_id_str = str(self.ref_id)

        return {
            "hex_dump": formatted_hex,
            "raw_length": len(raw_bytes),
            "li": {
                "val": self.li,
                "desc": li_names.get(self.li, "Unknown"),
                "bits": f"{self.li:02b}",
                "offset": "Byte 0 [Bits 7-6]",
            },
            "vn": {
                "val": self.vn,
                "desc": f"NTP Version {self.vn}",
                "bits": f"{self.vn:03b}",
                "offset": "Byte 0 [Bits 5-3]",
            },
            "mode": {
                "val": self.mode,
                "desc": mode_names.get(self.mode, f"Mode {self.mode}"),
                "bits": f"{self.mode:03b}",
                "offset": "Byte 0 [Bits 2-0]",
            },
            "stratum": {
                "val": self.stratum,
                "desc": stratum_desc,
                "offset": "Byte 1",
            },
            "poll": {
                "val": self.poll,
                "desc": f"2^{self.poll} = {2**self.poll} seconds",
                "offset": "Byte 2",
            },
            "precision": {
                "val": self.precision,
                "desc": f"2^{self.precision} ≈ {2**self.precision * 1e6:.2f} µs",
                "offset": "Byte 3",
            },
            "root_delay": {
                "val": self.root_delay,
                "desc": f"{self.root_delay / 65536.0:.4f} s",
                "offset": "Bytes 4-7",
            },
            "root_dispersion": {
                "val": self.root_dispersion,
                "desc": f"{self.root_dispersion / 65536.0:.4f} s",
                "offset": "Bytes 8-11",
            },
            "ref_id": {
                "val": ref_id_str,
                "desc": f"Reference Clock Identifier ('{ref_id_str}')",
                "offset": "Bytes 12-15",
            },
            "ref_timestamp": {
                "unix": self.ref_timestamp,
                "iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.ref_timestamp)) if self.ref_timestamp else "Not set (0)",
                "offset": "Bytes 16-23",
            },
            "orig_timestamp": {
                "name": "T1 (Originate Timestamp)",
                "unix": self.orig_timestamp,
                "iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.orig_timestamp)) if self.orig_timestamp else "Not set (0)",
                "offset": "Bytes 24-31",
            },
            "recv_timestamp": {
                "name": "T2 (Receive Timestamp)",
                "unix": self.recv_timestamp,
                "iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.recv_timestamp)) if self.recv_timestamp else "Not set (0)",
                "offset": "Bytes 32-39",
            },
            "tx_timestamp": {
                "name": "T3 / T1 (Transmit Timestamp)",
                "unix": self.tx_timestamp,
                "iso": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(self.tx_timestamp)) if self.tx_timestamp else "Not set (0)",
                "offset": "Bytes 40-47",
            },
        }
