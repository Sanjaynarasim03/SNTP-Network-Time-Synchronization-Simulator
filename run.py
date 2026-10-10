#!/usr/bin/env python3
"""
Single-command launcher for the SNTP Network Time Synchronization Simulator.

Usage:
    python3 run.py
"""

import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import flask
except ImportError:
    print("\n[ERROR] Flask is not installed.")
    print("Please install requirements using:")
    print("    pip install -r requirements.txt\n")
    sys.exit(1)

from dashboard.app import app

def main():
    print("=" * 70)
    print("  SNTP Network Time Synchronization Simulator (RFC 4330 / RFC 5905)")
    print("  Subject: Network Protocols and Analysis")
    print("=" * 70)
    print("  * SNTP UDP Server:     udp://127.0.0.1:1123 (Active)")
    print("  * Web Dashboard:       http://127.0.0.1:5000")
    print("  * Wireshark Filter:    udp.port == 1123")
    print("  * Mode:                100% Offline Localhost Simulation")
    print("=" * 70)
    print("  Opening dashboard... Press Ctrl+C to stop.\n")

    # Run the web server
    app.run(host="127.0.0.1", port=5000, debug=False)

if __name__ == "__main__":
    main()
