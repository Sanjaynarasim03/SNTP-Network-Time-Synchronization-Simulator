"""
Simulation Manager.

Coordinates the SNTP Server, simulated clients (Client A, B, C),
background polling loops, dynamic impairment updates, and pre-configured experiment scenarios.
"""

import threading
import time
import io
import csv
from dataclasses import asdict
from typing import Dict, List, Any, Optional

from server.sntp_server import SNTPServer
from client.sntp_client import SNTPClient, SyncRecord
from simulator.network_sim import NetworkConfig


class SimulationManager:
    """
    Orchestrator for the multi-client SNTP simulation testbed.
    """

    def __init__(self, server_port: int = 1123):
        self.server_port = server_port
        self.server = SNTPServer(port=server_port)
        
        # Simulated clients
        self.clients: Dict[str, SNTPClient] = {}
        self._init_default_clients()

        # Background polling control
        self.is_running = False
        self._poll_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Ensure server starts
        self.server.start(background=True)

    def _init_default_clients(self):
        """Initializes the three distinct default client nodes."""
        self.clients = {
            "client_a": SNTPClient(
                client_id="client_a",
                name="Client A (Campus LAN)",
                color="#38bdf8",  # Sky Blue
                server_port=self.server_port,
                initial_offset_sec=2.5,
                drift_ppm=15.0,
                network_config=NetworkConfig(
                    forward_delay_ms=10.0,
                    return_delay_ms=10.0,
                    jitter_ms=2.0,
                    packet_loss_rate=0.0,
                ),
                poll_interval_sec=3.0,
            ),
            "client_b": SNTPClient(
                client_id="client_b",
                name="Client B (WAN / 4G)",
                color="#a855f7",  # Purple
                server_port=self.server_port,
                initial_offset_sec=-3.5,
                drift_ppm=40.0,
                network_config=NetworkConfig(
                    forward_delay_ms=30.0,
                    return_delay_ms=30.0,
                    jitter_ms=12.0,
                    packet_loss_rate=0.05,
                ),
                poll_interval_sec=3.0,
            ),
            "client_c": SNTPClient(
                client_id="client_c",
                name="Client C (Satellite Link)",
                color="#f59e0b",  # Amber
                server_port=self.server_port,
                initial_offset_sec=5.0,
                drift_ppm=80.0,
                network_config=NetworkConfig(
                    forward_delay_ms=20.0,
                    return_delay_ms=90.0,  # Asymmetric!
                    jitter_ms=8.0,
                    packet_loss_rate=0.02,
                ),
                poll_interval_sec=3.0,
            ),
        }

    def start_simulation(self):
        """Starts background continuous periodic polling for all clients."""
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
            self._poll_thread = threading.Thread(target=self._run_poll_loop, daemon=True, name="Sim-Polling-Thread")
            self._poll_thread.start()

    def stop_simulation(self):
        """Stops background periodic polling."""
        with self._lock:
            self.is_running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=1.0)

    def _run_poll_loop(self):
        """Background loop executing syncs according to each client's poll interval."""
        last_polled: Dict[str, float] = {cid: 0.0 for cid in self.clients}
        while self.is_running:
            now = time.time()
            for cid, client in list(self.clients.items()):
                if not self.is_running:
                    break
                if now - last_polled.get(cid, 0.0) >= client.poll_interval:
                    last_polled[cid] = now
                    try:
                        client.sync_once()
                    except Exception as e:
                        pass
            time.sleep(0.2)

    def sync_client_once(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Manually triggers a single synchronization step for a given client."""
        client = self.clients.get(client_id)
        if not client:
            return None
        rec = client.sync_once()
        return client.get_summary()

    def sync_all_once(self) -> Dict[str, Any]:
        """Manually triggers a single synchronization step for all clients."""
        results = {}
        for cid, client in self.clients.items():
            client.sync_once()
            results[cid] = client.get_summary()
        return results

    def reset_all(self):
        """Resets all clients to baseline state."""
        self.stop_simulation()
        self._init_default_clients()

    def update_client_params(self, client_id: str, params: Dict[str, Any]):
        """Dynamically updates network or clock parameters for a client."""
        client = self.clients.get(client_id)
        if not client:
            return

        if "forward_delay_ms" in params:
            client.network.update_config(forward_delay_ms=float(params["forward_delay_ms"]))
        if "return_delay_ms" in params:
            client.network.update_config(return_delay_ms=float(params["return_delay_ms"]))
        if "jitter_ms" in params:
            client.network.update_config(jitter_ms=float(params["jitter_ms"]))
        if "packet_loss_rate" in params:
            client.network.update_config(packet_loss_rate=float(params["packet_loss_rate"]))
        if "poll_interval" in params:
            client.poll_interval = max(0.5, float(params["poll_interval"]))
        if "drift_ppm" in params:
            client.virtual_clock.drift_ppm = float(params["drift_ppm"])
        if "initial_offset_sec" in params:
            client.virtual_clock.initial_offset = float(params["initial_offset_sec"])

    def apply_experiment(self, experiment_id: str) -> Dict[str, Any]:
        """
        Configures an experiment preset, runs a test round, and produces an explanation.
        """
        self.stop_simulation()

        target_client = self.clients["client_a"]

        if experiment_id == "ideal":
            title = "Scenario 1: Ideal Symmetric Network"
            target_client.reset_state(initial_offset_sec=4.0, drift_ppm=0.0)
            target_client.network.update_config(
                forward_delay_ms=15.0,
                return_delay_ms=15.0,
                jitter_ms=0.0,
                packet_loss_rate=0.0,
            )
            # Run 3 sync cycles
            for _ in range(3):
                target_client.sync_once()
                time.sleep(0.05)
            
            explanation = (
                "In an ideal symmetrical channel (d_fwd = d_ret = 15.0 ms, 0 jitter, 0 loss), "
                "the SNTP assumption (T2 - T1 ≈ T4 - T3) holds with mathematical precision. "
                "The initial +4.000 s clock offset is corrected completely in the first round-trip, "
                "bringing the residual clock error down to < 0.5 ms."
            )

        elif experiment_id == "jitter":
            title = "Scenario 2: High Network Jitter"
            target_client.reset_state(initial_offset_sec=2.0, drift_ppm=10.0)
            target_client.network.update_config(
                forward_delay_ms=25.0,
                return_delay_ms=25.0,
                jitter_ms=25.0,  # Huge jitter: 0 ms to 50 ms delay variation
                packet_loss_rate=0.0,
            )
            for _ in range(5):
                target_client.sync_once()
                time.sleep(0.05)

            explanation = (
                "High network jitter causes random latency differences between the forward and return paths on every query. "
                "Even though average delay is symmetric, individual exchanges suffer from instantaneous asymmetry, "
                "causing the computed offset to fluctuate. Standard SNTP accepts this instantaneous value directly, "
                "which is why full NTP uses a Clock Filter Algorithm (retaining the minimum-delay sample) to reject jitter."
            )

        elif experiment_id == "asymmetry":
            title = "Scenario 3: Asymmetric Delay (The Fundamental SNTP Limitation)"
            target_client.reset_state(initial_offset_sec=0.0, drift_ppm=0.0)
            # Forward: 10 ms, Return: 90 ms -> Asymmetry = Return - Forward = 80 ms
            target_client.network.update_config(
                forward_delay_ms=10.0,
                return_delay_ms=90.0,
                jitter_ms=0.0,
                packet_loss_rate=0.0,
            )
            target_client.sync_once()

            rec = target_client.last_sync_record
            offset_err_ms = rec.offset_ms if rec else 0.0

            explanation = (
                f"Symmetric SNTP assumes Forward Delay = Return Delay = Total Delay / 2. "
                f"Here: Forward Delay = 10.0 ms, Return Delay = 90.0 ms (Asymmetry Δ = +80.0 ms). "
                f"Calculated offset error: {offset_err_ms:+.2f} ms! "
                f"Notice that offset error is EXACTLY -Δ/2 = -(90 - 10)/2 = -40.0 ms. "
                f"This proves the fundamental law of network timekeeping: "
                f"No two-way message protocol can distinguish between clock offset and path asymmetry without external reference."
            )

        elif experiment_id == "packet_loss":
            title = "Scenario 4: 30% Severe Packet Loss"
            target_client.reset_state(initial_offset_sec=3.0, drift_ppm=30.0)
            target_client.network.update_config(
                forward_delay_ms=20.0,
                return_delay_ms=20.0,
                jitter_ms=5.0,
                packet_loss_rate=0.30,
            )
            for _ in range(6):
                target_client.sync_once()
                time.sleep(0.05)

            loss_cnt = target_client.dropped_packets
            total_cnt = target_client.total_requests
            explanation = (
                f"With a 30% drop probability over UDP, {loss_cnt} out of {total_cnt} packets timed out or were lost in transit. "
                f"When a packet drops, the client's virtual clock cannot receive fresh timestamps and continues to drift. "
                f"The timeline and request table highlight dropped packets in red. SNTP clients must implement "
                f"retransmission timers and poll back-off when packet loss is detected."
            )

        elif experiment_id == "clock_drift":
            title = "Scenario 5: Large Clock Drift (High PPM)"
            target_client.reset_state(initial_offset_sec=0.0, drift_ppm=500.0)  # Huge 500 ppm drift
            target_client.network.update_config(
                forward_delay_ms=15.0,
                return_delay_ms=15.0,
                jitter_ms=1.0,
                packet_loss_rate=0.0,
            )
            # Advance time with drift, sync, and repeat
            time.sleep(0.5)
            target_client.sync_once()
            time.sleep(0.5)
            target_client.sync_once()

            explanation = (
                "A low-cost oscillator drifting at 500 ppm gains/loses 0.5 ms per second (1.8 seconds per hour!). "
                "Between sync intervals, the virtual clock wanders steadily away from true time. "
                "Periodic SNTP polling pulls it back, creating a saw-tooth error graph. "
                "Full NTP addresses this with a Phase-Locked Loop (PLL) clock discipline algorithm to tune the oscillator frequency directly."
            )
        else:
            return {"error": "Unknown experiment"}

        return {
            "experiment_id": experiment_id,
            "title": title,
            "explanation": explanation,
            "client_summary": target_client.get_summary(),
            "history": [asdict(r) for r in target_client.history],
        }

    def get_all_summaries(self) -> Dict[str, Any]:
        """Collects telemetry from all clients and server."""
        return {
            "is_running": self.is_running,
            "server": self.server.get_stats(),
            "clients": {cid: c.get_summary() for cid, c in self.clients.items()},
        }

    def get_client_history(self, client_id: str) -> List[Dict[str, Any]]:
        """Returns the full history of a client."""
        client = self.clients.get(client_id)
        if not client:
            return []
        return [asdict(rec) for rec in client.history]

    def export_csv(self) -> str:
        """Exports all client sync history records as CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Timestamp_Epoch",
            "Client_ID",
            "Seq",
            "Status",
            "T1_Originate",
            "T2_Receive",
            "T3_Transmit",
            "T4_Destination",
            "Offset_ms",
            "RoundTripDelay_ms",
            "ClockErrorBefore_ms",
            "ClockErrorAfter_ms",
            "ForwardDelay_ms",
            "ReturnDelay_ms",
        ])

        for cid, client in self.clients.items():
            for r in client.history:
                writer.writerow([
                    f"{r.timestamp:.3f}",
                    r.client_id,
                    r.seq,
                    r.status,
                    f"{r.t1:.6f}",
                    f"{r.t2:.6f}",
                    f"{r.t3:.6f}",
                    f"{r.t4:.6f}",
                    f"{r.offset_ms:.3f}",
                    f"{r.delay_ms:.3f}",
                    f"{r.error_before_ms:.3f}",
                    f"{r.error_after_ms:.3f}",
                    f"{r.forward_delay_ms:.2f}",
                    f"{r.return_delay_ms:.2f}",
                ])

        return output.getvalue()
