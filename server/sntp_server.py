"""
SNTP Server (RFC 4330 / RFC 5905).

A standalone, non-blocking / multi-threaded UDP server listening on localhost
(default port 1123) that responds to standard 48-byte SNTP client requests.
"""

import socket
import threading
import time
import logging
from typing import Optional, Tuple
from server.packet import SNTPPacket, SNTP_PACKET_SIZE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [SNTP Server] %(message)s")
logger = logging.getLogger("SNTPServer")


class SNTPServer:
    """
    UDP SNTP Server listening on a configurable port (default 1123).
    
    Upon receiving an SNTP request (Mode 3):
    1. Records receive timestamp T2 (server's authoritative system time).
    2. Constructs reply with:
       - LI = 0 (No leap second warning)
       - VN = Version of client (or 4)
       - Mode = 4 (Server)
       - Stratum = 1 (Primary reference server)
       - Precision = -20 (~1 microsecond)
       - Reference ID = b'LOCL' (Local clock reference)
       - Originate Timestamp = Client's Transmit Timestamp (T1)
       - Receive Timestamp = T2
       - Transmit Timestamp = T3 (server's send time)
    3. Replies back to client socket via UDP.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 1123):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # Server statistics
        self.requests_handled = 0
        self.start_time: Optional[float] = None
        self.last_client_addr: Optional[Tuple[str, int]] = None

    def start(self, background: bool = True):
        """Starts the UDP server."""
        if self._running:
            logger.warning("Server is already running.")
            return

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow immediate reuse of the address
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.settimeout(0.5)  # Timeout for clean loop shutdown
        
        self._running = True
        self.start_time = time.time()
        logger.info(f"SNTP Server started on udp://{self.host}:{self.port} (Stratum 1 Localhost Reference)")

        if background:
            self._thread = threading.Thread(target=self._serve_loop, daemon=True, name="SNTP-Server-Thread")
            self._thread.start()
        else:
            self._serve_loop()

    def _serve_loop(self):
        """Internal UDP server listening loop."""
        while self._running:
            try:
                data, addr = self.sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                # Socket was closed
                break
            except Exception as e:
                logger.error(f"Socket error while receiving: {e}")
                continue

            # Record T2 (Server Receive Timestamp) immediately upon packet arrival
            t2 = time.time()

            if len(data) < SNTP_PACKET_SIZE:
                logger.warning(f"Ignored runt packet from {addr}: {len(data)} bytes")
                continue

            try:
                # Unpack the incoming client datagram
                req_packet = SNTPPacket.unpack(data)
                
                # Client's Transmit Timestamp becomes the Originate Timestamp in response (T1)
                t1 = req_packet.tx_timestamp

                # Prepare server response packet (RFC 4330 Mode 4)
                # T3 is stamped right before sending
                t3 = time.time()

                resp_packet = SNTPPacket(
                    li=0,                   # No leap warning
                    vn=req_packet.vn or 4,  # Mirror client's version or 4
                    mode=4,                 # Mode 4 = Server reply
                    stratum=1,              # Stratum 1 = Primary Reference Clock
                    poll=req_packet.poll,
                    precision=-20,          # ~1 µs resolution
                    root_delay=0,
                    root_dispersion=0,
                    ref_id=b"LOCL",         # Local reference clock identifier
                    ref_timestamp=self.start_time or t3,
                    orig_timestamp=t1,      # T1 (Originate) copied from client
                    recv_timestamp=t2,      # T2 (Receive)
                    tx_timestamp=t3,        # T3 (Transmit)
                )

                # Send serialized 48-byte packet back to client
                resp_bytes = resp_packet.pack()
                self.sock.sendto(resp_bytes, addr)
                
                self.requests_handled += 1
                self.last_client_addr = addr
                logger.debug(f"Replied to {addr} | T1={t1:.6f}, T2={t2:.6f}, T3={t3:.6f}")

            except Exception as e:
                logger.error(f"Error handling request from {addr}: {e}")

    def stop(self):
        """Stops the UDP server gracefully."""
        self._running = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
            self.sock = None
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        logger.info("SNTP Server stopped.")

    def get_stats(self) -> dict:
        """Returns runtime stats for the dashboard."""
        uptime = time.time() - self.start_time if (self._running and self.start_time) else 0.0
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "uptime_seconds": round(uptime, 1),
            "requests_handled": self.requests_handled,
            "last_client": f"{self.last_client_addr[0]}:{self.last_client_addr[1]}" if self.last_client_addr else None,
        }


if __name__ == "__main__":
    server = SNTPServer(port=1123)
    server.start(background=False)
