# Project Report: SNTP Network Time Synchronization Simulator

**Course:** Network Protocols and Analysis (NPA)  
**Project Title:** Simple Network Time Protocol (SNTP) Network Time Synchronization Simulator  
**Deliverable:** Mini-Project Report Skeleton  

---

## Abstract
Accurate clock synchronization across distributed nodes is a vital prerequisite for modern networking applications, including consensus algorithms, transaction ordering, and logging. The Simple Network Time Protocol (SNTP, RFC 4330) provides a lightweight mechanism for clock synchronization over the User Datagram Protocol (UDP). This project designs, implements, and evaluates an end-to-end SNTP Network Time Synchronization Simulator built entirely using the Python standard library networking primitives and a modern Flask web dashboard. The simulator implements the full 48-byte RFC 4330 datagram, converts between Unix and NTP epochs, executes the four-timestamp ($T_1, T_2, T_3, T_4$) exchange, and manages a software-based Virtual Clock model. Network impairments—including transmission latency, jitter, path asymmetry, and packet loss—are simulated to empirically evaluate SNTP clock offset convergence. We formally demonstrate that path asymmetry $\Delta$ induces an offset calculation error of exactly $-\Delta / 2$.

---

## 1. Introduction
Modern network infrastructures rely heavily on consistent timestamping. In physical systems, hardware oscillators suffer from frequency drift influenced by temperature fluctuations and hardware aging. Protocols such as the Network Time Protocol (NTP, RFC 5905) and Simple Network Time Protocol (SNTP, RFC 4330) bridge this divide. While full NTP provides sophisticated multi-peer filtering and continuous phase-locked loop (PLL) disciplines, SNTP is tailored for client endpoints requiring minimal computational overhead.

---

## 2. Objectives
1. Implement an RFC 4330 compliant SNTP server listening on an unprivileged UDP port (`1123`) using standard binary packing (`struct`).
2. Implement a client that records timestamps $T_1$ and $T_4$, extracts $T_2$ and $T_3$, and computes clock offset ($\theta$) and round-trip delay ($\delta$).
3. Develop an isolated Virtual Clock module that simulates frequency drift (in PPM) and step corrections without modifying the operating system's system clock.
4. Construct a network channel simulator introducing forward/return latency, random jitter, path asymmetry, and packet loss.
5. Provide a real-time web dashboard featuring an animated $T_1 - T_4$ message exchange timeline, live Chart.js graphs, an interactive 48-byte packet inspector, and pre-configured experiment scenarios.

---

## 3. Protocol Overview (RFC 4330 / RFC 5905)
SNTP datagrams are strictly formatted 48-byte UDP payloads:
- **Leap Indicator (LI, 2 bits):** Leap second warning.
- **Version Number (VN, 3 bits):** Version 4.
- **Mode (3 bits):** Mode 3 (Client) / Mode 4 (Server).
- **Stratum (8 bits):** Stratum 1 (Primary reference clock).
- **Poll & Precision (8 bits each):** Polling interval and clock precision exponents.
- **Root Delay & Dispersion (32 bits each):** Fixed-point error metrics.
- **Reference Identifier (32 bits):** Reference clock identifier (e.g. `'LOCL'`).
- **Timestamps (64 bits each):** Reference, Originate ($T_1$), Receive ($T_2$), Transmit ($T_3$).

---

## 4. System Design & Architecture
The system consists of five distinct layers:
1. **Packet Serialization Layer (`server/packet.py`):** Uses Python `struct.pack('!BBbbII4sIIIIIIII')` to format binary datagrams in network byte order. Converts between the 1900 NTP epoch and 1970 Unix epoch ($2,208,988,800$ s delta).
2. **Authoritative UDP Server (`server/sntp_server.py`):** Operates on `127.0.0.1:1123`. Unpacks requests, timestamps arrival ($T_2$), generates departure timestamp ($T_3$), and replies.
3. **Virtual Client Clock (`client/virtual_clock.py`):** Tracks virtual elapsed time according to:
   $$V(t) = V_{\text{prev}} + \Delta t_{\text{real}} \times (1 + \text{drift}_{\text{ppm}} \times 10^{-6}) + \text{adjustments}$$
4. **Network Impairment Pipeline (`simulator/network_sim.py`):** Injects asymmetric transit delays ($d_{\text{fwd}}, d_{\text{ret}}$), uniform random jitter, and probabilistic drop rates.
5. **Interactive Presentation Dashboard (`dashboard/`):** Flask backend with Vanilla CSS and Chart.js frontend.

---

## 5. Mathematical Formulations
### Clock Offset:
$$\theta = \frac{(T_2 - T_1) + (T_3 - T_4)}{2}$$

### Round-Trip Delay:
$$\delta = (T_4 - T_1) - (T_3 - T_2)$$

### Proof of Asymmetric Delay Error:
Let forward transit delay be $d_{\text{fwd}}$ and return transit delay be $d_{\text{ret}} = d_{\text{fwd}} + \Delta$.
$$T_2 = T_1 + d_{\text{fwd}} + \theta_{\text{true}}$$
$$T_4 = T_3 + (d_{\text{fwd}} + \Delta) - \theta_{\text{true}}$$
Subtracting and substituting into the offset formula:
$$\theta_{\text{calc}} = \frac{(d_{\text{fwd}} + \theta_{\text{true}}) + (-d_{\text{fwd}} - \Delta + \theta_{\text{true}})}{2} = \theta_{\text{true}} - \frac{\Delta}{2}$$
Thus, any path asymmetry directly skews the calculated offset by half the asymmetry value.

---

## 6. Experimental Results & Analysis

### Scenario 1: Ideal Symmetric Network
- **Configuration:** $d_{\text{fwd}} = 15\text{ ms}, d_{\text{ret}} = 15\text{ ms}$, Jitter = $0$, Loss = $0$, Drift = $0$.
- **Result:** Initial clock skew (+4.000 s) converges to $< 0.5\text{ ms}$ on the first synchronization exchange.

### Scenario 2: High Network Jitter
- **Configuration:** Delay = $25\text{ ms} \pm 25\text{ ms}$ random jitter.
- **Result:** Offset calculations fluctuate across successive cycles due to instantaneous path variance. Highlights the necessity of NTP's minimum-delay Clock Filter Algorithm.

### Scenario 3: Asymmetric Delay
- **Configuration:** $d_{\text{fwd}} = 10\text{ ms}, d_{\text{ret}} = 90\text{ ms}$ ($\Delta = +80\text{ ms}$).
- **Result:** Calculated clock offset equals $-40.0\text{ ms}$, exactly validating $-\Delta / 2$.

### Scenario 4: 30% UDP Packet Loss
- **Configuration:** $P_{\text{loss}} = 0.30$.
- **Result:** Demonstrates socket timeouts and skipped synchronization cycles, highlighting UDP's best-effort transport characteristics.

---

## 7. Conclusion
The SNTP Network Time Synchronization Simulator successfully models RFC 4330 datagram exchanges and provides an empirical testbed for studying the behavior of clock offset estimation under diverse network impairments. The implementation confirms both the efficiency of SNTP in symmetric environments and its fundamental vulnerability to path asymmetry and jitter.

---

## References
1. Mills, D., "Simple Network Time Protocol (SNTP) Version 4 for IPv4, IPv6 and OSI", RFC 4330, January 2006.
2. Mills, D., et al., "Network Time Protocol Version 4: Protocol and Algorithms Specification", RFC 5905, June 2010.
3. Kurose, J. F., & Ross, K. W., "Computer Networking: A Top-Down Approach", 8th Edition, Pearson.
