# SNTP Simulator: Protocol Explainer & Viva Guide

This document explains the **Simple Network Time Protocol (SNTP)**, the architecture of this simulator, and provides answers to **10 likely viva examination questions** in clear, beginner-friendly language.

---

## 1. What is SNTP?

Every computer has a hardware clock (quartz crystal oscillator), but no two quartz crystals vibrate at the exact same frequency. Temperature, aging, and voltage cause clocks to **drift** by seconds or minutes every day.

To keep financial transactions, security certificates, authentication tokens, and logging in sync across the Internet, computers synchronize their clocks using **NTP (Network Time Protocol)** or **SNTP (Simple Network Time Protocol)**.

- **NTP (RFC 5905):** A comprehensive, complex protocol that polls multiple time servers, filters out network jitter, and continuously disciplines the local oscillator using a phase-locked loop (PLL).
- **SNTP (RFC 4330):** A lightweight, simplified version of NTP designed for client devices. It sends a single UDP request and steps the clock based on the calculated offset.

---

## 2. The 48-Byte SNTP Packet Structure

Every SNTP packet sent over UDP is exactly **48 bytes** long. Here is the structure:

| Byte Offset | Field Name | Size | Purpose |
| :--- | :--- | :--- | :--- |
| `0 [Bits 7-6]` | **LI (Leap Indicator)** | 2 bits | Warns of an upcoming leap second (00 = no warning, 11 = alarm/unsynced). |
| `0 [Bits 5-3]` | **VN (Version Number)** | 3 bits | Protocol version (4 for SNTPv4 / NTPv4). |
| `0 [Bits 2-0]` | **Mode** | 3 bits | 3 = Client Request, 4 = Server Response. |
| `1` | **Stratum** | 1 byte | Distance from reference clock (1 = Primary/Atomic, 2 = Secondary, etc.). |
| `2` | **Poll** | 1 byte | Maximum poll interval between messages as $2^{\text{poll}}$ seconds. |
| `3` | **Precision** | 1 byte | Clock precision as $2^{\text{precision}}$ seconds (e.g. -20 $\approx 1\,\mu\text{s}$). |
| `4 - 7` | **Root Delay** | 4 bytes | Total round-trip delay to the primary reference clock. |
| `8 - 11` | **Root Dispersion** | 4 bytes | Maximum clock error relative to primary reference. |
| `12 - 15` | **Reference ID** | 4 bytes | 4-character ASCII code (e.g., `'LOCL'`, `'GPS '`) or IPv4 address. |
| `16 - 23` | **Reference Timestamp** | 8 bytes | Time when the local clock was last set or synchronized. |
| `24 - 31` | **Originate Timestamp ($T_1$)** | 8 bytes | Time when request packet departed the client. |
| `32 - 39` | **Receive Timestamp ($T_2$)** | 8 bytes | Time when request packet arrived at the server. |
| `40 - 47` | **Transmit Timestamp ($T_3$)** | 8 bytes | Time when response packet departed the server. |

### The NTP Epoch vs. Unix Epoch
- **Unix Epoch:** Seconds since January 1, 1970, 00:00:00 UTC.
- **NTP Epoch:** Seconds since January 1, 1900, 00:00:00 UTC.
- **Delta:** 70 years = 17 leap years + 53 regular years = 25,567 days = **2,208,988,800 seconds**.
- Each 8-byte NTP timestamp consists of:
  - 32-bit unsigned integer: Seconds since 1900.
  - 32-bit unsigned integer: Fractional seconds scaled to $2^{32}$.

---

## 3. The Four-Timestamp ($T_1, T_2, T_3, T_4$) Exchange

When a client synchronizes with a server, four timestamps are recorded:

1. **$T_1$ (Client Transmit):** Client reads its virtual clock and puts $T_1$ into the *Transmit Timestamp* field of the request.
2. **$T_2$ (Server Receive):** Server receives the UDP packet and records $T_2$ from its system clock.
3. **$T_3$ (Server Transmit):** Server prepares reply, copies $T_1$ to the *Originate Timestamp* field, sets $T_2$ in the *Receive Timestamp* field, and records $T_3$ as the packet leaves.
4. **$T_4$ (Client Receive):** Client receives the UDP reply and records $T_4$ from its virtual clock.

```
       Client Clock                                Server Clock
            |                                           |
    T1 ---- o (Request departed client)                 |
            \                                           |
             \  Forward Transit Delay (d_fwd)           |
              \                                         |
               +--------------------------------------> o ---- T2 (Request arrived at server)
                                                        |
                                                        | Server processing time
                                                        |
               +<-------------------------------------- o ---- T3 (Response departed server)
              /
             /  Return Transit Delay (d_ret)
            /
    T4 ---- o (Response arrived at client)
            |
```

---

## 4. Mathematical Formulas & Derivations

Let $\theta$ be the clock offset (difference between server clock and client clock: $\text{Server} - \text{Client}$).  
Let $d_{\text{fwd}}$ be the forward transit delay (Client $\to$ Server).  
Let $d_{\text{ret}}$ be the return transit delay (Server $\to$ Client).

From the timeline:
$$T_2 = T_1 + d_{\text{fwd}} + \theta$$
$$T_4 = T_3 + d_{\text{ret}} - \theta$$

Rearranging the two equations:
$$T_2 - T_1 = d_{\text{fwd}} + \theta \quad \text{--- (Equation 1)}$$
$$T_3 - T_4 = -d_{\text{ret}} + \theta \quad \text{--- (Equation 2)}$$

### Clock Offset Formula:
Summing Equation 1 and Equation 2:
$$(T_2 - T_1) + (T_3 - T_4) = (d_{\text{fwd}} - d_{\text{ret}}) + 2\theta$$

Under the assumption of a **symmetric network** ($d_{\text{fwd}} = d_{\text{ret}}$):
$$(T_2 - T_1) + (T_3 - T_4) = 2\theta$$
$$\mathbf{\theta = \frac{(T_2 - T_1) + (T_3 - T_4)}{2}}$$

### Round-Trip Delay Formula:
Subtracting Equation 2 from Equation 1:
$$(T_4 - T_1) - (T_3 - T_2) = d_{\text{fwd}} + d_{\text{ret}}$$
$$\mathbf{\delta = (T_4 - T_1) - (T_3 - T_2)}$$

### Asymmetric Delay Theorem:
If the return path has extra delay $\Delta$ compared to forward path ($d_{\text{ret}} = d_{\text{fwd}} + \Delta$):
$$(T_2 - T_1) + (T_3 - T_4) = -\Delta + 2\theta$$
$$\theta_{\text{calculated}} = \theta_{\text{true}} - \frac{\Delta}{2}$$

**Conclusion:** SNTP offset error is **exactly half of the path asymmetry**!

---

## 5. Architecture & File Overview

| File | Role / Responsibility |
| :--- | :--- |
| `server/packet.py` | Defines the 48-byte packet structure using `struct.pack/unpack`, and handles 1900/1970 epoch conversion. |
| `server/sntp_server.py` | Standalone UDP server listening on `127.0.0.1:1123`. Handles incoming requests and replies with $T_2$ and $T_3$. |
| `client/virtual_clock.py` | Simulates an independent client clock with configurable initial offset and oscillator drift (ppm) without touching OS clock. |
| `client/sntp_client.py` | SNTP client that executes the 4-timestamp exchange, computes offset and delay, and corrects the virtual clock. |
| `simulator/network_sim.py` | Simulates asymmetric delays, jitter, packet loss drops, and socket timeouts. |
| `simulator/simulation_manager.py` | Manages 3 simultaneous clients (LAN, WAN, Satellite) and executes experiment presets. |
| `dashboard/app.py` | Flask REST API backend serving simulation telemetry, live updates, and CSV export. |
| `dashboard/static/js/app.js` | UI logic: Chart.js graphs, animated canvas timeline, and presentation mode walkthrough. |
| `tests/` | Unit tests for packet serialization, struct sizing, and mathematical formulas. |
| `run.py` | Single-command launcher for the server and web dashboard. |

---

## 6. Top 10 Viva Examination Questions and Answers

### Q1: Why does SNTP use UDP instead of TCP?
**Answer:** Time synchronization requires minimal latency and minimal protocol overhead. TCP requires a 3-way handshake (`SYN`, `SYN-ACK`, `ACK`), connection state, retransmissions, and flow control—all of which introduce unpredictable transmission delays and jitter. UDP is connectionless and incurs near-zero transport overhead, allowing precise departure and arrival timestamping.

### Q2: What is the fundamental difference between NTP and SNTP?
**Answer:** SNTP is a lightweight client subset of NTP. SNTP queries a single time server and immediately applies a step correction to its clock. Full NTP (RFC 5905) queries multiple servers (peers), uses Marzullo's intersection algorithm to reject "falsetickers", applies a Clock Filter Algorithm to reject jitter, and continuously slews the local oscillator using a Phase-Locked Loop (PLL).

### Q3: Why is port 1123 used in this project instead of the standard NTP port 123?
**Answer:** Ports below 1024 are "privileged ports" on Unix/macOS/Linux and require root/administrator privileges (`sudo`) to bind. Port 1123 is an unprivileged port that allows the simulator to run completely in user space on localhost without administrative rights.

### Q4: Why does NTP epoch start in 1900 while Unix epoch starts in 1970?
**Answer:** NTP was designed in the late 1970s and chose January 1, 1900 as its epoch to encompass the entire 20th century. The Unix epoch begins on January 1, 1970. The constant difference between them is exactly 70 years ($2,208,988,800$ seconds).

### Q5: What is clock drift and what does PPM mean?
**Answer:** Quartz crystal oscillators vibrate at slightly imperfect frequencies due to manufacturing tolerances and temperature. **PPM stands for Parts Per Million**. A clock with $+50\text{ PPM}$ drift gains 50 microseconds every second, which accumulates to $4.32$ seconds of error every day without synchronization.

### Q6: How does network asymmetry affect SNTP offset calculations?
**Answer:** SNTP mathematically assumes that forward delay equals return delay. If the return path is slower than the forward path by $\Delta$, the calculated clock offset will have an error of exactly $-\Delta / 2$. No two-way protocol can distinguish path asymmetry from clock offset without an external reference (such as GPS).

### Q7: What are $T_1, T_2, T_3, T_4$?
**Answer:**
- $T_1$: Originate timestamp (time client sent request, measured by client clock).
- $T_2$: Receive timestamp (time server received request, measured by server clock).
- $T_3$: Transmit timestamp (time server sent response, measured by server clock).
- $T_4$: Destination timestamp (time client received response, measured by client clock).

### Q8: What does the Stratum number signify in NTP?
**Answer:** Stratum indicates the distance from the primary reference clock:
- **Stratum 0:** High-precision atomic clocks or GPS satellites (not directly reachable over network).
- **Stratum 1:** Primary time servers connected directly to Stratum 0 devices.
- **Stratum 2:** Secondary servers synchronized to Stratum 1 servers over network.
- **Stratum 16:** Unsynchronized / invalid clock.

### Q9: Why is a "Virtual Clock" used in this project?
**Answer:** In operating systems, modifying the real hardware clock requires root permissions and can disrupt system logs, SSL certificates, and scheduled tasks. Our Virtual Clock simulates oscillator dynamics, initial errors, frequency drift, and SNTP discipline in software safely.

### Q10: How does full NTP handle high network jitter that SNTP struggles with?
**Answer:** Full NTP maintains a sliding window of the last 8 round-trip measurements and executes the **Clock Filter Algorithm**. It selects the sample with the lowest round-trip delay, because packets experiencing the lowest delay encounter the least queueing latency and thus have the lowest jitter and asymmetry.
