"""
Network Condition Simulator.

Simulates physical network impairments on UDP packets:
- Symmetric and Asymmetric transmission delays (Client -> Server vs Server -> Client)
- Random network jitter
- Packet loss percentage (drops)
- Socket timeouts and retransmission handling
"""

import random
import time
from dataclasses import dataclass, asdict
from typing import Tuple, Dict, Any, Optional


@dataclass
class NetworkConfig:
    """Configuration for simulated network impairments."""
    forward_delay_ms: float = 20.0   # Latency from Client to Server (ms)
    return_delay_ms: float = 20.0    # Latency from Server to Client (ms)
    jitter_ms: float = 5.0           # Random deviation (+/- ms)
    packet_loss_rate: float = 0.0    # Packet loss probability [0.0 - 1.0] (e.g. 0.05 = 5%)
    timeout_sec: float = 1.0         # Socket wait timeout (seconds)
    max_retries: int = 1             # Number of retransmissions upon timeout


class NetworkSimulator:
    """
    Simulates transmission of packets across an impaired network channel.
    """

    def __init__(self, config: Optional[NetworkConfig] = None):
        self.config = config or NetworkConfig()

    def update_config(self, **kwargs):
        """Dynamically updates simulator parameters."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, float(value))

    def sample_forward_delay(self) -> float:
        """Computes simulated forward delay in seconds with random jitter."""
        jitter = random.uniform(-self.config.jitter_ms, self.config.jitter_ms) if self.config.jitter_ms > 0 else 0.0
        delay_ms = max(0.5, self.config.forward_delay_ms + jitter)
        return delay_ms / 1000.0

    def sample_return_delay(self) -> float:
        """Computes simulated return delay in seconds with random jitter."""
        jitter = random.uniform(-self.config.jitter_ms, self.config.jitter_ms) if self.config.jitter_ms > 0 else 0.0
        delay_ms = max(0.5, self.config.return_delay_ms + jitter)
        return delay_ms / 1000.0

    def check_packet_loss(self) -> Tuple[bool, str]:
        """
        Determines if a packet is lost.
        Returns: (is_lost: bool, drop_stage: 'none' | 'forward' | 'return')
        """
        if self.config.packet_loss_rate <= 0.0:
            return False, "none"

        roll = random.random()
        if roll < self.config.packet_loss_rate:
            # 50% chance forward drop, 50% chance return drop
            stage = "forward" if random.random() < 0.5 else "return"
            return True, stage
        return False, "none"

    def to_dict(self) -> Dict[str, Any]:
        """Serializes config for dashboard."""
        return asdict(self.config)
