"""
SNTP Client Implementation.

Performs RFC 4330 4-timestamp time synchronization:
- Measures T1 (Transmit from Client)
- Receives T2 (Arrive at Server) & T3 (Transmit from Server)
- Measures T4 (Arrive at Client)
- Computes Clock Offset & Round-Trip Delay:
    offset = ((T2 - T1) + (T3 - T4)) / 2
    delay  = (T4 - T1) - (T3 - T2)
- Corrects local Virtual Clock
"""

import socket
import time
import logging
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List

from server.packet import SNTPPacket
from client.virtual_clock import VirtualClock
from simulator.network_sim import NetworkSimulator, NetworkConfig

logger = logging.getLogger("SNTPClient")


@dataclass
class SyncRecord:
    """Holds the result and telemetry of a single SNTP sync transaction."""
    client_id: str
    seq: int
    timestamp: float
    status: str              # "SUCCESS", "LOST_FORWARD", "LOST_RETURN", "TIMEOUT"
    t1: float = 0.0          # Client Originate Time
    t2: float = 0.0          # Server Receive Time
    t3: float = 0.0          # Server Transmit Time
    t4: float = 0.0          # Client Destination Time
    offset_sec: float = 0.0  # Computed clock offset in seconds
    offset_ms: float = 0.0   # Computed clock offset in milliseconds
    delay_sec: float = 0.0   # Computed round-trip delay in seconds
    delay_ms: float = 0.0    # Computed round-trip delay in milliseconds
    error_before_ms: float = 0.0 # Virtual clock error before sync
    error_after_ms: float = 0.0  # Virtual clock error after sync
    forward_delay_ms: float = 0.0
    return_delay_ms: float = 0.0
    raw_packet_hex: str = ""
    packet_inspect: Optional[Dict[str, Any]] = None
    retry_count: int = 0
    formula_explanation: str = ""


class SNTPClient:
    """
    SNTP Client with Virtual Clock and Network Simulator integration.
    """

    def __init__(
        self,
        client_id: str,
        name: str = "Client",
        color: str = "#3b82f6",
        server_host: str = "127.0.0.1",
        server_port: int = 1123,
        initial_offset_sec: float = 3.0,
        drift_ppm: float = 20.0,
        network_config: Optional[NetworkConfig] = None,
        poll_interval_sec: float = 3.0,
    ):
        self.client_id = client_id
        self.name = name
        self.color = color
        self.server_host = server_host
        self.server_port = server_port
        
        # Virtual Clock for this client
        self.virtual_clock = VirtualClock(initial_offset_sec=initial_offset_sec, drift_ppm=drift_ppm)
        
        # Network conditions channel for this client
        self.network = NetworkSimulator(network_config or NetworkConfig())
        
        self.poll_interval = poll_interval_sec
        self.sequence_number = 0
        self.history: List[SyncRecord] = []
        self.max_history_len = 100

        # Statistics
        self.total_requests = 0
        self.successful_syncs = 0
        self.dropped_packets = 0
        self.last_sync_record: Optional[SyncRecord] = None

    def sync_once(self) -> SyncRecord:
        """
        Executes one full SNTP request-response round-trip exchange.
        Measures T1, T2, T3, T4 and applies virtual clock correction.
        """
        self.sequence_number += 1
        self.total_requests += 1
        seq = self.sequence_number
        now_epoch = time.time()

        err_before = self.virtual_clock.get_true_error() * 1000.0

        # Sample simulated channel conditions for this packet
        is_lost, drop_stage = self.network.check_packet_loss()
        fwd_delay = self.network.sample_forward_delay()
        ret_delay = self.network.sample_return_delay()

        # Check if dropped on forward path
        if is_lost and drop_stage == "forward":
            self.dropped_packets += 1
            record = SyncRecord(
                client_id=self.client_id,
                seq=seq,
                timestamp=now_epoch,
                status="LOST_FORWARD",
                error_before_ms=err_before,
                error_after_ms=self.virtual_clock.get_true_error() * 1000.0,
                forward_delay_ms=fwd_delay * 1000.0,
                return_delay_ms=ret_delay * 1000.0,
                formula_explanation="Packet dropped in flight on forward path (Client -> Server).",
            )
            self._save_record(record)
            return record

        # Measure T1 (Client Originate Timestamp from Virtual Clock)
        t1 = self.virtual_clock.get_time()

        # Construct SNTP Client Request (Mode 3, VN 4)
        req = SNTPPacket(
            li=0,
            vn=4,
            mode=3,            # Mode 3 = Client Request
            stratum=0,
            poll=4,
            precision=-20,
            ref_id=b"\x00\x00\x00\x00",
            tx_timestamp=t1,   # T1 placed in Transmit Timestamp field
        )
        req_bytes = req.pack()

        # Simulate forward path transit delay
        time.sleep(fwd_delay)

        # Send over real UDP socket to server
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.network.config.timeout_sec)

        try:
            sock.sendto(req_bytes, (self.server_host, self.server_port))
            
            # Receive server reply over UDP
            resp_bytes, _ = sock.recvfrom(1024)
            
        except socket.timeout:
            self.dropped_packets += 1
            sock.close()
            record = SyncRecord(
                client_id=self.client_id,
                seq=seq,
                timestamp=now_epoch,
                status="TIMEOUT",
                t1=t1,
                error_before_ms=err_before,
                error_after_ms=self.virtual_clock.get_true_error() * 1000.0,
                forward_delay_ms=fwd_delay * 1000.0,
                return_delay_ms=ret_delay * 1000.0,
                formula_explanation="Socket timed out waiting for server response.",
            )
            self._save_record(record)
            return record
        except Exception as e:
            self.dropped_packets += 1
            sock.close()
            record = SyncRecord(
                client_id=self.client_id,
                seq=seq,
                timestamp=now_epoch,
                status="ERROR",
                t1=t1,
                error_before_ms=err_before,
                error_after_ms=self.virtual_clock.get_true_error() * 1000.0,
                formula_explanation=f"Network error: {str(e)}",
            )
            self._save_record(record)
            return record
        finally:
            sock.close()

        # Check if dropped on return path
        if is_lost and drop_stage == "return":
            self.dropped_packets += 1
            record = SyncRecord(
                client_id=self.client_id,
                seq=seq,
                timestamp=now_epoch,
                status="LOST_RETURN",
                t1=t1,
                error_before_ms=err_before,
                error_after_ms=self.virtual_clock.get_true_error() * 1000.0,
                forward_delay_ms=fwd_delay * 1000.0,
                return_delay_ms=ret_delay * 1000.0,
                formula_explanation="Server replied, but response packet was dropped on return path (Server -> Client).",
            )
            self._save_record(record)
            return record

        # Simulate return path transit delay
        time.sleep(ret_delay)

        # Measure T4 (Client Destination Timestamp from Virtual Clock upon receipt)
        t4 = self.virtual_clock.get_time()

        # Unpack server response
        resp_packet = SNTPPacket.unpack(resp_bytes)
        t2 = resp_packet.recv_timestamp  # Server Receive Timestamp
        t3 = resp_packet.tx_timestamp    # Server Transmit Timestamp

        # Standard SNTP / RFC 4330 Formulas:
        # Offset: theta = ((T2 - T1) + (T3 - T4)) / 2
        # Delay:  delta = (T4 - T1) - (T3 - T2)
        offset_sec = ((t2 - t1) + (t3 - t4)) / 2.0
        delay_sec = (t4 - t1) - (t3 - t2)

        # Apply correction to virtual clock
        self.virtual_clock.adjust(offset_sec)
        err_after = self.virtual_clock.get_true_error() * 1000.0

        self.successful_syncs += 1

        # Build formula explanation string with live values substituted
        formula_exp = (
            f"Offset = [({t2:.4f} - {t1:.4f}) + ({t3:.4f} - {t4:.4f})] / 2 = {offset_sec*1000.0:+.2f} ms | "
            f"Delay = ({t4:.4f} - {t1:.4f}) - ({t3:.4f} - {t2:.4f}) = {delay_sec*1000.0:.2f} ms"
        )

        record = SyncRecord(
            client_id=self.client_id,
            seq=seq,
            timestamp=now_epoch,
            status="SUCCESS",
            t1=t1,
            t2=t2,
            t3=t3,
            t4=t4,
            offset_sec=offset_sec,
            offset_ms=offset_sec * 1000.0,
            delay_sec=delay_sec,
            delay_ms=delay_sec * 1000.0,
            error_before_ms=err_before,
            error_after_ms=err_after,
            forward_delay_ms=fwd_delay * 1000.0,
            return_delay_ms=ret_delay * 1000.0,
            raw_packet_hex=resp_bytes.hex().upper(),
            packet_inspect=resp_packet.to_inspect_dict(resp_bytes),
            formula_explanation=formula_exp,
        )

        self._save_record(record)
        return record

    def _save_record(self, record: SyncRecord):
        """Maintains ring buffer of sync records."""
        self.last_sync_record = record
        self.history.append(record)
        if len(self.history) > self.max_history_len:
            self.history.pop(0)

    def reset_state(self, initial_offset_sec: float = None, drift_ppm: float = None):
        """Resets the client virtual clock and telemetry logs."""
        self.virtual_clock.reset(initial_offset_sec, drift_ppm)
        self.history.clear()
        self.total_requests = 0
        self.successful_syncs = 0
        self.dropped_packets = 0
        self.sequence_number = 0
        self.last_sync_record = None

    def get_summary(self) -> Dict[str, Any]:
        """Provides real-time telemetry summary for the dashboard."""
        v_state = self.virtual_clock.get_state()
        last = self.last_sync_record

        # Determine sync status
        true_err_abs_ms = abs(v_state["true_error_ms"])
        if last is None:
            sync_status = "Initialized"
        elif last.status in ("TIMEOUT", "LOST_FORWARD", "LOST_RETURN"):
            sync_status = "Packet Lost"
        elif true_err_abs_ms < 5.0:
            sync_status = "Synchronized"
        elif true_err_abs_ms < 50.0:
            sync_status = "Coarse Sync"
        else:
            sync_status = "Drifting"

        loss_pct = (self.dropped_packets / self.total_requests * 100.0) if self.total_requests > 0 else 0.0

        return {
            "client_id": self.client_id,
            "name": self.name,
            "color": self.color,
            "poll_interval": self.poll_interval,
            "status": sync_status,
            "virtual_time_str": time.strftime("%H:%M:%S", time.localtime(v_state["virtual_time"])),
            "true_error_ms": round(v_state["true_error_ms"], 2),
            "last_offset_ms": round(last.offset_ms, 2) if last and last.status == "SUCCESS" else None,
            "last_delay_ms": round(last.delay_ms, 2) if last and last.status == "SUCCESS" else None,
            "total_requests": self.total_requests,
            "successful_syncs": self.successful_syncs,
            "dropped_packets": self.dropped_packets,
            "packet_loss_pct": round(loss_pct, 1),
            "clock_state": v_state,
            "network_config": self.network.to_dict(),
            "last_record": asdict(last) if last else None,
        }
