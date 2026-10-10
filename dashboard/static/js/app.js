/**
 * SNTP Network Time Synchronization Simulator - Dashboard Controller
 * Handles live polling, Chart.js instances, canvas timeline animation,
 * packet inspector interaction, and presentation walkthrough.
 */

// Global State
let activeTab = "live-sim";
let activeClientId = "client_a";
let isRunning = false;
let pollingIntervalId = null;
let timelineAnimFrameId = null;
let animationState = {
  progress: 0,
  activeRecord: null,
  isAnimating: false,
};

// Chart.js instances
let offsetChart = null;
let delayChart = null;
let expChart = null;



// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initCharts();
  initSliders();
  initControls();
  initTimelineCanvas();
  loadPacketInspector();
  startStatusPolling();
});

// ==========================================
// Tab Switching
// ==========================================
function initTabs() {
  const tabBtns = document.querySelectorAll(".tab-btn");
  tabBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId);
    });
  });

  // Support URL query parameter ?tab=...
  const urlParams = new URLSearchParams(window.location.search);
  const tabParam = urlParams.get("tab");
  if (tabParam) {
    switchTab(tabParam);
  }

  const expParam = urlParams.get("exp");
  if (expParam) {
    switchTab("experiments");
    runExperimentScenario(expParam);
  }
}

function switchTab(tabId) {
  activeTab = tabId;
  document.querySelectorAll(".tab-btn").forEach((b) => {
    b.classList.toggle("active", b.getAttribute("data-tab") === tabId);
  });
  document.querySelectorAll(".tab-panel").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${tabId}`);
  });

  if (tabId === "packet-inspector") {
    loadPacketInspector();
  }
}

// ==========================================
// Client Switching & Parameter Sliders
// ==========================================
function initSliders() {
  const clientPills = document.querySelectorAll(".client-pill-btn");
  clientPills.forEach((pill) => {
    pill.addEventListener("click", () => {
      clientPills.forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      activeClientId = pill.getAttribute("data-client");
      fetchStatus();
    });
  });

  const sliders = [
    { id: "sliderFwdDelay", key: "forward_delay_ms", valId: "valFwdDelay", unit: "ms" },
    { id: "sliderRetDelay", key: "return_delay_ms", valId: "valRetDelay", unit: "ms" },
    { id: "sliderJitter", key: "jitter_ms", valId: "valJitter", unit: "ms" },
    { id: "sliderLoss", key: "packet_loss_rate", valId: "valLoss", unit: "%", scale: 0.01 },
    { id: "sliderDrift", key: "drift_ppm", valId: "valDrift", unit: "ppm" },
    { id: "sliderPoll", key: "poll_interval", valId: "valPoll", unit: "s" },
  ];

  sliders.forEach((s) => {
    const el = document.getElementById(s.id);
    const valEl = document.getElementById(s.valId);
    if (!el || !valEl) return;

    el.addEventListener("input", () => {
      valEl.textContent = `${el.value} ${s.unit}`;
    });

    el.addEventListener("change", () => {
      const payload = {};
      payload[s.key] = s.scale ? parseFloat(el.value) * s.scale : parseFloat(el.value);
      updateClientParams(activeClientId, payload);
    });
  });

  const btnAsym = document.getElementById("btnMakeAsymmetric");
  if (btnAsym) {
    btnAsym.addEventListener("click", () => {
      document.getElementById("sliderFwdDelay").value = 10;
      document.getElementById("valFwdDelay").textContent = "10 ms";
      document.getElementById("sliderRetDelay").value = 90;
      document.getElementById("valRetDelay").textContent = "90 ms";
      updateClientParams(activeClientId, { forward_delay_ms: 10, return_delay_ms: 90 });
    });
  }
}

async function updateClientParams(clientId, params) {
  try {
    await fetch(`/api/client/${clientId}/update`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(params),
    });
  } catch (err) {
    console.error("Failed to update parameters:", err);
  }
}

// ==========================================
// Simulation Controls (Start, Stop, Reset, Sync)
// ==========================================
function initControls() {
  const btnStart = document.getElementById("btnStart");
  const btnStop = document.getElementById("btnStop");
  const btnSync = document.getElementById("btnSync");
  const btnReset = document.getElementById("btnReset");

  btnStart?.addEventListener("click", async () => {
    await fetch("/api/start", { method: "POST" });
    fetchStatus();
  });

  btnStop?.addEventListener("click", async () => {
    await fetch("/api/stop", { method: "POST" });
    fetchStatus();
  });

  btnSync?.addEventListener("click", () => {
    triggerSync(activeClientId);
  });

  btnReset?.addEventListener("click", async () => {
    await fetch("/api/reset", { method: "POST" });
    clearCharts();
    fetchStatus();
  });

  // Export buttons
  document.getElementById("btnExportCSV")?.addEventListener("click", () => {
    window.location.href = "/api/export-csv";
  });
  document.getElementById("btnExportPNG")?.addEventListener("click", exportChartsAsPNG);
}

async function triggerSync(clientId) {
  try {
    const res = await fetch("/api/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId }),
    });
    const data = await res.json();
    fetchStatus();
    if (data.client && data.client.last_record) {
      triggerTimelineAnimation(data.client.last_record);
    }
  } catch (err) {
    console.error("Sync error:", err);
  }
}

// ==========================================
// Status Polling & UI Updates
// ==========================================
function startStatusPolling() {
  fetchStatus();
  pollingIntervalId = setInterval(fetchStatus, 1500);
}

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    updateUI(data);
  } catch (err) {
    console.warn("Status fetch failed:", err);
  }
}

function updateUI(data) {
  isRunning = data.is_running;

  // Toggle Start / Stop button active styles
  const btnStart = document.getElementById("btnStart");
  const btnStop = document.getElementById("btnStop");
  if (btnStart && btnStop) {
    if (isRunning) {
      btnStart.classList.remove("btn-primary");
      btnStart.classList.add("btn-success");
      btnStart.innerHTML = `<span class="pulse-dot"></span> Running...`;
    } else {
      btnStart.classList.add("btn-primary");
      btnStart.classList.remove("btn-success");
      btnStart.innerHTML = `▶ Start Sync`;
    }
  }

  // Update server status pill
  const serverTimeEl = document.getElementById("serverClock");
  if (serverTimeEl) {
    const now = new Date();
    serverTimeEl.textContent = now.toTimeString().split(" ")[0];
  }

  // Active client details
  const client = data.clients[activeClientId];
  if (!client) return;

  // Update KPI Cards
  const kpiOffset = document.getElementById("kpiOffset");
  const kpiDelay = document.getElementById("kpiDelay");
  const kpiLoss = document.getElementById("kpiLoss");
  const kpiStatus = document.getElementById("kpiStatus");
  const kpiTrueErr = document.getElementById("kpiTrueError");

  if (kpiOffset) {
    kpiOffset.textContent = client.last_offset_ms !== null ? `${client.last_offset_ms > 0 ? "+" : ""}${client.last_offset_ms} ms` : "--";
  }
  if (kpiDelay) {
    kpiDelay.textContent = client.last_delay_ms !== null ? `${client.last_delay_ms} ms` : "--";
  }
  if (kpiLoss) {
    kpiLoss.textContent = `${client.packet_loss_pct}% (${client.dropped_packets}/${client.total_requests})`;
  }
  if (kpiStatus) {
    kpiStatus.textContent = client.status;
    kpiStatus.style.color =
      client.status === "Synchronized" ? "var(--status-synced)" :
      client.status === "Packet Lost" ? "var(--status-lost)" : "var(--status-drifting)";
  }
  if (kpiTrueErr) {
    kpiTrueErr.textContent = `${client.true_error_ms > 0 ? "+" : ""}${client.true_error_ms} ms`;
  }

  // Update slider inputs to match server if not focused
  updateSliderDisplay(client);

  // Update History Table & Charts
  fetchClientHistory(activeClientId);
}

function updateSliderDisplay(client) {
  const net = client.network_config;
  const isSliderActive = (id) => document.activeElement === document.getElementById(id);

  if (!isSliderActive("sliderFwdDelay")) {
    document.getElementById("sliderFwdDelay").value = net.forward_delay_ms;
    document.getElementById("valFwdDelay").textContent = `${net.forward_delay_ms} ms`;
  }
  if (!isSliderActive("sliderRetDelay")) {
    document.getElementById("sliderRetDelay").value = net.return_delay_ms;
    document.getElementById("valRetDelay").textContent = `${net.return_delay_ms} ms`;
  }
  if (!isSliderActive("sliderJitter")) {
    document.getElementById("sliderJitter").value = net.jitter_ms;
    document.getElementById("valJitter").textContent = `${net.jitter_ms} ms`;
  }
  if (!isSliderActive("sliderLoss")) {
    const pct = Math.round(net.packet_loss_rate * 100);
    document.getElementById("sliderLoss").value = pct;
    document.getElementById("valLoss").textContent = `${pct} %`;
  }
  if (!isSliderActive("sliderDrift")) {
    document.getElementById("sliderDrift").value = client.clock_state.drift_ppm;
    document.getElementById("valDrift").textContent = `${client.clock_state.drift_ppm} ppm`;
  }
  if (!isSliderActive("sliderPoll")) {
    document.getElementById("sliderPoll").value = client.poll_interval;
    document.getElementById("valPoll").textContent = `${client.poll_interval} s`;
  }
}

async function fetchClientHistory(clientId) {
  try {
    const res = await fetch(`/api/client/${clientId}/history`);
    const data = await res.json();
    renderHistoryTable(data.history);
    updateChartsData(data.history);
  } catch (err) {
    console.error("Error fetching history:", err);
  }
}

function renderHistoryTable(history) {
  const tbody = document.getElementById("syncTableBody");
  if (!tbody) return;

  if (!history || history.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 24px;">No synchronization packets recorded yet. Click "Sync Once" or "Start Continuous Sync".</td></tr>`;
    return;
  }

  // Show newest on top
  const rows = [...history].reverse().slice(0, 15).map((r) => {
    const isSuccess = r.status === "SUCCESS";
    const badgeClass = isSuccess ? "badge-success" : "badge-danger";
    const statusText = isSuccess ? "OK" : r.status;
    const timeStr = new Date(r.timestamp * 1000).toTimeString().split(" ")[0];

    return `
      <tr>
        <td>#${r.seq}</td>
        <td>${timeStr}</td>
        <td><span class="badge ${badgeClass}">${statusText}</span></td>
        <td>${r.t1 > 0 ? r.t1.toFixed(4) : "--"}</td>
        <td>${r.t2 > 0 ? r.t2.toFixed(4) : "--"}</td>
        <td>${r.t3 > 0 ? r.t3.toFixed(4) : "--"}</td>
        <td>${r.t4 > 0 ? r.t4.toFixed(4) : "--"}</td>
        <td style="color: ${isSuccess ? '#38bdf8' : '#ef4444'}; font-weight: 700;">
          ${isSuccess ? `${r.offset_ms > 0 ? '+' : ''}${r.offset_ms.toFixed(2)} ms` : '--'}
        </td>
        <td style="color: #34d399; font-weight: 700;">
          ${isSuccess ? `${r.delay_ms.toFixed(2)} ms` : '--'}
        </td>
      </tr>
    `;
  });

  tbody.innerHTML = rows.join("");
}

// ==========================================
// Chart.js Live Graphs
// ==========================================
function initCharts() {
  const ctxOffset = document.getElementById("offsetChart")?.getContext("2d");
  const ctxDelay = document.getElementById("delayChart")?.getContext("2d");

  if (ctxOffset) {
    offsetChart = new Chart(ctxOffset, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Calculated Offset (ms)",
            data: [],
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.15)",
            borderWidth: 2,
            tension: 0.2,
            fill: true,
            pointRadius: 4,
          },
          {
            label: "Zero Offset Target",
            data: [],
            borderColor: "rgba(255, 255, 255, 0.2)",
            borderDash: [5, 5],
            borderWidth: 1,
            pointRadius: 0,
            fill: false,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: "#1f2937" }, ticks: { color: "#9ca3af" } },
          y: {
            title: { display: true, text: "Offset (ms)", color: "#9ca3af" },
            grid: { color: "#1f2937" },
            ticks: { color: "#9ca3af" },
          },
        },
        plugins: {
          legend: { labels: { color: "#e5e7eb" } },
        },
      },
    });
  }

  if (ctxDelay) {
    delayChart = new Chart(ctxDelay, {
      type: "line",
      data: {
        labels: [],
        datasets: [
          {
            label: "Round-Trip Delay (ms)",
            data: [],
            borderColor: "#a855f7",
            backgroundColor: "rgba(168, 85, 247, 0.15)",
            borderWidth: 2,
            tension: 0.2,
            fill: true,
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { color: "#1f2937" }, ticks: { color: "#9ca3af" } },
          y: {
            title: { display: true, text: "Delay (ms)", color: "#9ca3af" },
            grid: { color: "#1f2937" },
            ticks: { color: "#9ca3af" },
          },
        },
        plugins: {
          legend: { labels: { color: "#e5e7eb" } },
        },
      },
    });
  }
}

function updateChartsData(history) {
  if (!offsetChart || !delayChart || !history) return;

  const validRecords = history.slice(-20);
  const labels = validRecords.map((r) => `#${r.seq}`);
  const offsets = validRecords.map((r) => (r.status === "SUCCESS" ? r.offset_ms : null));
  const delays = validRecords.map((r) => (r.status === "SUCCESS" ? r.delay_ms : null));
  const zeros = validRecords.map(() => 0);

  offsetChart.data.labels = labels;
  offsetChart.data.datasets[0].data = offsets;
  offsetChart.data.datasets[1].data = zeros;
  offsetChart.update("none");

  delayChart.data.labels = labels;
  delayChart.data.datasets[0].data = delays;
  delayChart.update("none");
}

function clearCharts() {
  if (offsetChart) {
    offsetChart.data.labels = [];
    offsetChart.data.datasets[0].data = [];
    offsetChart.update();
  }
  if (delayChart) {
    delayChart.data.labels = [];
    delayChart.data.datasets[0].data = [];
    delayChart.update();
  }
}

// ==========================================
// Animated Timeline Canvas & Live Formula
// ==========================================
function initTimelineCanvas() {
  const canvas = document.getElementById("timelineCanvas");
  if (!canvas) return;

  // Handle high-DPI scaling
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);

  drawTimeline(ctx, rect.width, rect.height, null, 0);
}

function triggerTimelineAnimation(record) {
  animationState.activeRecord = record;
  animationState.progress = 0;
  animationState.isAnimating = true;

  updateFormulaDisplay(record);

  if (timelineAnimFrameId) {
    cancelAnimationFrame(timelineAnimFrameId);
  }

  const startTime = performance.now();
  const animDuration = 1800; // ms

  function animate(now) {
    const elapsed = now - startTime;
    animationState.progress = Math.min(1.0, elapsed / animDuration);

    const canvas = document.getElementById("timelineCanvas");
    if (canvas) {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      const ctx = canvas.getContext("2d");
      ctx.save();
      ctx.scale(dpr, dpr);
      drawTimeline(ctx, rect.width, rect.height, animationState.activeRecord, animationState.progress);
      ctx.restore();
    }

    if (animationState.progress < 1.0) {
      timelineAnimFrameId = requestAnimationFrame(animate);
    } else {
      animationState.isAnimating = false;
    }
  }

  timelineAnimFrameId = requestAnimationFrame(animate);
}

function drawTimeline(ctx, width, height, record, progress) {
  ctx.clearRect(0, 0, width, height);

  const clientX = 100;
  const serverX = width - 100;
  const topY = 35;
  const bottomY = height - 35;

  // Draw Vertical Lanes
  ctx.strokeStyle = "#374151";
  ctx.lineWidth = 2;
  ctx.setLineDash([]);

  // Client Lane
  ctx.beginPath();
  ctx.moveTo(clientX, topY);
  ctx.lineTo(clientX, bottomY);
  ctx.stroke();

  // Server Lane
  ctx.beginPath();
  ctx.moveTo(serverX, topY);
  ctx.lineTo(serverX, bottomY);
  ctx.stroke();

  // Lane Headers
  ctx.font = "bold 13px -apple-system, sans-serif";
  ctx.fillStyle = "#38bdf8";
  ctx.textAlign = "center";
  ctx.fillText("CLIENT VIRTUAL CLOCK", clientX, topY - 12);

  ctx.fillStyle = "#10b981";
  ctx.fillText("SNTP UDP SERVER (Port 1123)", serverX, topY - 12);

  const yT1 = topY + 25;
  const yT2 = topY + 75;
  const yT3 = topY + 115;
  const yT4 = bottomY - 15;

  // Draw Timestamp Nodes on Lanes
  drawNode(ctx, clientX, yT1, "T1", record?.t1 ? record.t1.toFixed(4) : "T1: Client Tx", "#38bdf8", "right");
  drawNode(ctx, serverX, yT2, "T2", record?.t2 ? record.t2.toFixed(4) : "T2: Server Rx", "#10b981", "left");
  drawNode(ctx, serverX, yT3, "T3", record?.t3 ? record.t3.toFixed(4) : "T3: Server Tx", "#10b981", "left");
  drawNode(ctx, clientX, yT4, "T4", record?.t4 ? record.t4.toFixed(4) : "T4: Client Rx", "#38bdf8", "right");

  // Draw Static Path Arrows
  ctx.setLineDash([4, 4]);
  ctx.lineWidth = 1.5;

  // Forward Path (T1 -> T2)
  ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
  ctx.beginPath();
  ctx.moveTo(clientX, yT1);
  ctx.lineTo(serverX, yT2);
  ctx.stroke();

  // Server Processing (T2 -> T3)
  ctx.strokeStyle = "rgba(16, 185, 129, 0.6)";
  ctx.beginPath();
  ctx.moveTo(serverX, yT2);
  ctx.lineTo(serverX, yT3);
  ctx.stroke();

  // Return Path (T3 -> T4)
  ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
  ctx.beginPath();
  ctx.moveTo(serverX, yT3);
  ctx.lineTo(clientX, yT4);
  ctx.stroke();

  // Animated Packet Ball
  if (record && progress > 0) {
    ctx.setLineDash([]);
    let ballX = clientX;
    let ballY = yT1;
    let label = "Request Packet (Mode 3)";
    let ballColor = "#38bdf8";

    if (progress <= 0.45) {
      // Forward path stage (0.0 to 0.45)
      const p = progress / 0.45;
      ballX = clientX + (serverX - clientX) * p;
      ballY = yT1 + (yT2 - yT1) * p;
      if (record.status === "LOST_FORWARD" && p > 0.6) {
        ballColor = "#ef4444";
        label = "DROPPED IN FLIGHT!";
      }
    } else if (progress <= 0.55) {
      // Server processing stage (0.45 to 0.55)
      const p = (progress - 0.45) / 0.1;
      ballX = serverX;
      ballY = yT2 + (yT3 - yT2) * p;
      ballColor = "#10b981";
      label = "Server Processing (T2->T3)";
    } else {
      // Return path stage (0.55 to 1.0)
      const p = (progress - 0.55) / 0.45;
      ballX = serverX + (clientX - serverX) * p;
      ballY = yT3 + (yT4 - yT3) * p;
      ballColor = "#a855f7";
      label = "Response Packet (Mode 4)";
      if (record.status === "LOST_RETURN" && p > 0.6) {
        ballColor = "#ef4444";
        label = "DROPPED ON RETURN!";
      }
    }

    // Draw glowing packet ball
    ctx.beginPath();
    ctx.arc(ballX, ballY, 8, 0, Math.PI * 2);
    ctx.fillStyle = ballColor;
    ctx.shadowColor = ballColor;
    ctx.shadowBlur = 12;
    ctx.fill();
    ctx.shadowBlur = 0; // reset

    // Draw label beside packet
    ctx.font = "bold 11px ui-monospace, monospace";
    ctx.fillStyle = ballColor;
    ctx.fillText(label, ballX, ballY - 12);
  }
}

function drawNode(ctx, x, y, label, text, color, align) {
  ctx.beginPath();
  ctx.arc(x, y, 5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();

  ctx.font = "bold 11px ui-monospace, monospace";
  ctx.fillStyle = color;
  ctx.textAlign = align === "left" ? "left" : "right";
  const offset = align === "left" ? 12 : -12;
  ctx.fillText(text, x + offset, y + 4);
}

function updateFormulaDisplay(record) {
  const fBox = document.getElementById("liveFormulaBox");
  if (!fBox) return;

  if (record.status !== "SUCCESS") {
    fBox.innerHTML = `
      <div style="color: #ef4444; font-weight: 700;">
        ⚠️ Packet failed during exchange: <strong>${record.status}</strong>. Synchronization skipped.
      </div>
    `;
    return;
  }

  const t1 = record.t1;
  const t2 = record.t2;
  const t3 = record.t3;
  const t4 = record.t4;
  const offMs = record.offset_ms.toFixed(2);
  const dlyMs = record.delay_ms.toFixed(2);

  fBox.innerHTML = `
    <div class="formula-row">
      <span class="formula-label">Clock Offset (θ):</span>
      <span>[ (T2 - T1) + (T3 - T4) ] / 2</span>
      <span>= [ (${t2.toFixed(4)} - ${t1.toFixed(4)}) + (${t3.toFixed(4)} - ${t4.toFixed(4)}) ] / 2</span>
      <span class="formula-result">= ${offMs > 0 ? "+" : ""}${offMs} ms</span>
    </div>
    <div class="formula-row">
      <span class="formula-label">Round-Trip Delay (δ):</span>
      <span>(T4 - T1) - (T3 - T2)</span>
      <span>= (${t4.toFixed(4)} - ${t1.toFixed(4)}) - (${t3.toFixed(4)} - ${t2.toFixed(4)})</span>
      <span class="formula-result">= ${dlyMs} ms</span>
    </div>
  `;
}

// ==========================================
// Packet Inspector
// ==========================================
async function loadPacketInspector() {
  try {
    const res = await fetch(`/api/packet-inspect?client_id=${activeClientId}`);
    const data = await res.json();
    renderPacketInspector(data.record, data.raw_hex);
  } catch (err) {
    console.error("Inspector error:", err);
  }
}

function renderPacketInspector(rec, hexDump) {
  const hexEl = document.getElementById("inspectorHexDump");
  if (hexEl && hexDump) {
    // Format nicely into 16-byte rows
    const chunks = hexDump.match(/.{1,32}/g) || [hexDump];
    const formatted = chunks
      .map((c, i) => {
        const offset = (i * 16).toString(16).padStart(4, "0").toUpperCase();
        const spaced = c.match(/.{1,2}/g).join(" ");
        return `${offset}  ${spaced}`;
      })
      .join("\n");
    hexEl.textContent = formatted;
  }

  // Bind click details to fields
  const fields = [
    { id: "fLI", key: "li", title: "Leap Indicator (LI)", bits: "2 bits" },
    { id: "fVN", key: "vn", title: "Version Number (VN)", bits: "3 bits" },
    { id: "fMode", key: "mode", title: "Mode", bits: "3 bits" },
    { id: "fStratum", key: "stratum", title: "Stratum", bits: "8 bits (1 byte)" },
    { id: "fPoll", key: "poll", title: "Poll Interval", bits: "8 bits (1 byte)" },
    { id: "fPrecision", key: "precision", title: "Precision", bits: "8 bits (1 byte)" },
    { id: "fRootDelay", key: "root_delay", title: "Root Delay", bits: "32 bits (4 bytes)" },
    { id: "fRootDisp", key: "root_dispersion", title: "Root Dispersion", bits: "32 bits (4 bytes)" },
    { id: "fRefID", key: "ref_id", title: "Reference Identifier", bits: "32 bits (4 bytes)" },
    { id: "fRefTS", key: "ref_timestamp", title: "Reference Timestamp", bits: "64 bits (8 bytes)" },
    { id: "fOrigTS", key: "orig_timestamp", title: "Originate Timestamp (T1)", bits: "64 bits (8 bytes)" },
    { id: "fRecvTS", key: "recv_timestamp", title: "Receive Timestamp (T2)", bits: "64 bits (8 bytes)" },
    { id: "fTxTS", key: "tx_timestamp", title: "Transmit Timestamp (T3)", bits: "64 bits (8 bytes)" },
  ];

  fields.forEach((f) => {
    const el = document.getElementById(f.id);
    if (!el) return;
    const item = rec[f.key];
    if (item) {
      const valStr = typeof item.val !== "undefined" ? item.val : item.iso || item.unix;
      const valSpan = el.querySelector(".field-value");
      if (valSpan) valSpan.textContent = valStr;

      el.onclick = () => showFieldDetails(f.title, f.bits, item);
    }
  });
}

function showFieldDetails(title, bitWidth, item) {
  const panel = document.getElementById("fieldDetailCard");
  if (!panel) return;

  panel.innerHTML = `
    <h3 style="color: #38bdf8; font-size: 1.1rem; margin-bottom: 8px;">${title}</h3>
    <div style="font-size: 0.85rem; color: #9ca3af; margin-bottom: 12px;">Offset: ${item.offset || "--"} | Size: ${bitWidth}</div>
    <div style="background: #111827; padding: 12px; border-radius: 6px; border: 1px solid #374151; font-family: ui-monospace, monospace; font-size: 0.9rem;">
      <div><strong>Value:</strong> <span style="color: #34d399;">${typeof item.val !== 'undefined' ? item.val : item.unix}</span></div>
      ${item.bits ? `<div><strong>Binary:</strong> <code>0b${item.bits}</code></div>` : ""}
      ${item.iso ? `<div><strong>Human Time:</strong> ${item.iso}</div>` : ""}
      <div style="margin-top: 8px; color: #e2e8f0; font-family: -apple-system, sans-serif;">
        <strong>Meaning:</strong> ${item.desc || "Standard RFC 4330 header field"}
      </div>
    </div>
  `;
}

// ==========================================
// Experiments Mode
// ==========================================
async function runExperimentScenario(expId) {
  const resPanel = document.getElementById("expResultPanel");
  const loading = document.getElementById("expLoadingIndicator");
  const content = document.getElementById("expResultContent");
  const title = document.getElementById("expResultTitle");

  if (resPanel) resPanel.style.display = "block";
  if (loading) loading.style.display = "block";
  if (content) content.style.display = "none";
  if (title) title.textContent = "Simulating Scenario & Calculating Telemetry...";

  try {
    const res = await fetch(`/api/experiment/${expId}`, { method: "POST" });
    const data = await res.json();
    if (loading) loading.style.display = "none";
    if (content) content.style.display = "block";
    renderExperimentResult(data);
  } catch (err) {
    if (loading) loading.style.display = "none";
    console.error("Experiment failed:", err);
  }
}

function renderExperimentResult(data) {
  document.getElementById("expResultTitle").textContent = data.title;
  document.getElementById("expExplanationText").textContent = data.explanation;

  const ctxExp = document.getElementById("expChart")?.getContext("2d");
  if (!ctxExp) return;

  if (expChart) expChart.destroy();

  const labels = data.history.map((r) => `#${r.seq}`);
  const offsets = data.history.map((r) => (r.status === "SUCCESS" ? r.offset_ms : null));
  const errors = data.history.map((r) => r.error_after_ms);

  expChart = new Chart(ctxExp, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Computed Offset (ms)",
          data: offsets,
          borderColor: "#38bdf8",
          backgroundColor: "rgba(56, 189, 248, 0.2)",
          borderWidth: 2,
          tension: 0.2,
          pointRadius: 5,
        },
        {
          label: "Residual Clock Error (ms)",
          data: errors,
          borderColor: "#f59e0b",
          borderWidth: 2,
          borderDash: [4, 4],
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { grid: { color: "#1f2937" }, ticks: { color: "#9ca3af" } },
        y: {
          title: { display: true, text: "Milliseconds", color: "#9ca3af" },
          grid: { color: "#1f2937" },
          ticks: { color: "#9ca3af" },
        },
      },
      plugins: {
        legend: { labels: { color: "#e5e7eb" } },
      },
    },
  });
}



// ==========================================
// Chart Export PNG
// ==========================================
function exportChartsAsPNG() {
  if (!offsetChart) return;
  const imageURI = offsetChart.toBase64Image();
  const link = document.createElement("a");
  link.download = "sntp_offset_chart.png";
  link.href = imageURI;
  link.click();
}
