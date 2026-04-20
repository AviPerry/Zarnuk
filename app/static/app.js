const FIXED_COMMAND_TOPIC = "basa/command";
const FIXED_TELEMETRY_TOPIC = "basa/telemetry";

const state = { devices: [], selectedSn: null, watchedSn: null, ws: null, search: "" };

const appEl = document.getElementById("app");
const connectionStateEl = document.getElementById("connection-state");

function route() {
  const hash = window.location.hash.replace(/^#\/?/, "");
  const previousSelected = state.selectedSn;
  if (!hash.startsWith("device/")) {
    if (previousSelected) unwatchDevice(previousSelected);
    state.selectedSn = null;
    renderOverview();
    return;
  }
  const nextSelected = hash.split("/")[1]?.toUpperCase() || null;
  if (previousSelected && previousSelected !== nextSelected) {
    unwatchDevice(previousSelected);
  }
  state.selectedSn = nextSelected;
  renderDashboard();
}

function connectSocket() {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  state.ws = new WebSocket(`${protocol}://${window.location.host}/ws`);
  state.ws.addEventListener("open", () => {
    connectionStateEl.textContent = "מחובר";
    if (state.selectedSn) watchDevice(state.selectedSn);
  });
  state.ws.addEventListener("close", () => {
    connectionStateEl.textContent = "מנותק";
    setTimeout(connectSocket, 1200);
  });
  state.ws.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    if (message.type === "devices.snapshot") {
      state.devices = (message.payload.devices || []).map(normalizeDevice);
    }
    if (message.type === "device.updated") {
      upsertDevice(normalizeDevice(message.payload.device));
    }
    refresh();
  });
}

function normalizeDevice(device) {
  return {
    ...device,
    name: device.name || "",
    command_topic: FIXED_COMMAND_TOPIC,
    telemetry_topic: FIXED_TELEMETRY_TOPIC,
    telemetry: {
      vin: 0,
      v1: 0,
      ir: 0,
      frequency: 0,
      resistance: 0,
      power: 0,
      battery_voltage: 0,
      healthy: true,
      alerts: [],
      output_enabled: false,
      target_current: 0,
      target_frequency: 0,
      ...device.telemetry,
    },
  };
}

function upsertDevice(device) {
  const index = state.devices.findIndex((entry) => entry.sn === device.sn);
  if (index === -1) {
    state.devices.push(device);
    return;
  }

  const existing = state.devices[index];
  state.devices[index] = normalizeDevice({
    ...existing,
    ...device,
    telemetry: {
      ...existing.telemetry,
      ...device.telemetry,
    },
  });
}

function refresh() {
  if (state.selectedSn) {
    const device = state.devices.find((entry) => entry.sn === state.selectedSn);
    if (isDashboardMounted() && device) {
      updateDashboardView(device);
      return;
    }
    renderDashboard();
    return;
  }
  renderOverview();
}

function isDashboardMounted() {
  return Boolean(document.getElementById("device-title"));
}

function renderOverview() {
  const template = document.getElementById("overview-template");
  appEl.replaceChildren(template.content.cloneNode(true));
  const input = document.getElementById("device-search");
  const grid = document.getElementById("device-grid");
  const addForm = document.getElementById("add-device-form");
  const addInput = document.getElementById("add-device-input");
  const addNameInput = document.getElementById("add-device-name-input");
  input.value = state.search;

  const draw = () => {
    state.search = input.value.trim().toUpperCase();
    const filtered = state.devices.filter((device) => {
      const haystack = `${device.sn} ${device.name}`.toUpperCase();
      return haystack.includes(state.search);
    });
    grid.replaceChildren(...filtered.map(buildDeviceCard));
    if (!filtered.length) {
      grid.innerHTML = `<article class="panel"><h3>לא נמצאו התקנים</h3><p>נסה מספר סידורי אחר או שם שהוגדר לבקר.</p></article>`;
    }
  };

  input.addEventListener("input", draw);
  addForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await createDevice(addInput.value, addNameInput.value);
    addInput.value = "";
    addNameInput.value = "";
  });
  draw();
}

function buildDeviceCard(device) {
  const card = document.createElement("article");
  card.className = "device-card";
  card.innerHTML = `
    <header>
      <strong class="mono">${device.sn}</strong>
      <span class="status-badge ${device.online ? "status-online" : "status-offline"}">${device.online ? "online" : "offline"}</span>
    </header>
    <div class="meta-grid">
      <span>שם <strong>${escapeHtml(device.name || "ללא שם")}</strong></span>
      <span>תקינות <strong>${device.telemetry.healthy ? "תקין" : "דורש בדיקה"}</strong></span>
      <span>סוללה <strong>${Number(device.telemetry.battery_voltage || 0).toFixed(2)} V</strong></span>
      <span>Ir <strong>${Number(device.telemetry.ir || 0).toFixed(2)} A</strong></span>
      <span>V1 <strong>${Number(device.telemetry.v1 || 0).toFixed(1)} V</strong></span>
      <span>תדר <strong>${Number(device.telemetry.frequency || 0).toFixed(1)} kHz</strong></span>
      <span>פקודות <strong class="mono">${FIXED_COMMAND_TOPIC}</strong></span>
      <span>טלמטריה <strong class="mono">${FIXED_TELEMETRY_TOPIC}</strong></span>
    </div>
    <div class="device-card-actions">
      <button class="ghost-button" type="button" data-action="open">פתח</button>
      <button class="ghost-button danger-button inline-danger" type="button" data-action="delete">מחק</button>
    </div>
  `;
  card.querySelector('[data-action="open"]').addEventListener("click", () => {
    window.location.hash = `/device/${device.sn}`;
  });
  card.querySelector('[data-action="delete"]').addEventListener("click", async () => {
    await deleteDevice(device.sn);
  });
  return card;
}

function renderDashboard() {
  const template = document.getElementById("dashboard-template");
  appEl.replaceChildren(template.content.cloneNode(true));
  const device = state.devices.find((entry) => entry.sn === state.selectedSn);
  if (!device) {
    appEl.innerHTML = `<article class="panel"><h3>התקן לא נמצא</h3><p>המספר הסידורי ${escapeHtml(state.selectedSn || "")} לא קיים במערכת.</p></article>`;
    return;
  }

  document.getElementById("back-button").addEventListener("click", () => {
    unwatchDevice(device.sn);
    window.location.hash = "/";
  });
  document.getElementById("output-on").addEventListener("click", () => sendOutput(device.sn, "on"));
  document.getElementById("output-off").addEventListener("click", () => sendOutput(device.sn, "off"));
  document.getElementById("delete-device-button").addEventListener("click", () => deleteDevice(device.sn));
  document.getElementById("control-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitControls(device.sn);
  });
  document.getElementById("device-name-form").addEventListener("submit", (event) => {
    event.preventDefault();
    saveDeviceName(device.sn);
  });

  updateDashboardView(device);
  watchDevice(device.sn);
  fetchDevice(device.sn);
}

function updateDashboardView(device) {
  document.getElementById("device-title").textContent = `התקן ${device.sn}`;
  document.getElementById("device-sn-value").textContent = device.sn;
  document.getElementById("device-name-value").textContent = device.name || "ללא שם";
  const statusEl = document.getElementById("device-online-badge");
  statusEl.textContent = device.online ? "online" : "offline";
  statusEl.className = `status-badge ${device.online ? "status-online" : "status-offline"}`;
  document.getElementById("last-command").textContent = device.last_command_hex || "עדיין לא נשלחה פקודה";
  document.getElementById("ir-value").textContent = Number(device.telemetry.ir || 0).toFixed(2);
  document.getElementById("v1-value").textContent = Number(device.telemetry.v1 || 0).toFixed(1);
  document.getElementById("frequency-value").textContent = Number(device.telemetry.frequency || 0).toFixed(1);
  document.getElementById("resistance-value").textContent = Number(device.telemetry.resistance || 0).toFixed(2);
  document.getElementById("power-value").textContent = Number(device.telemetry.power || 0).toFixed(1);
  document.getElementById("battery-gauge-value").textContent = Number(device.telemetry.battery_voltage || 0).toFixed(2);

  const currentInput = document.getElementById("current-input");
  const frequencyInput = document.getElementById("frequency-input");
  const nameInput = document.getElementById("device-name-input");
  if (document.activeElement !== currentInput) {
    currentInput.value = Number(device.telemetry.target_current || 0).toFixed(2);
  }
  if (document.activeElement !== frequencyInput) {
    frequencyInput.value = Number(device.telemetry.target_frequency || 0).toFixed(2);
  }
  if (document.activeElement !== nameInput) {
    nameInput.value = device.name || "";
  }

  const lowBat = device.telemetry.alerts.includes("LOW-BAT");
  document.getElementById("low-battery-warning").classList.toggle("hidden", !lowBat);
  document.getElementById("output-on").disabled = lowBat;
  document.getElementById("output-on").classList.toggle("button-disabled", lowBat);

  const alertsEl = document.getElementById("alerts-list");
  const alerts = device.telemetry.alerts.length ? device.telemetry.alerts : ["תקין"];
  alertsEl.replaceChildren(...alerts.map((alert) => {
    const pill = document.createElement("div");
    pill.className = `alert-pill ${alert === "תקין" ? "status-online" : alert === "LOW-BAT" ? "status-warn" : "status-offline"}`;
    pill.textContent = alert;
    return pill;
  }));
}

async function createDevice(sn, name) {
  const response = await fetch("/api/devices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sn, name }),
  });
  if (!response.ok) {
    const error = await response.json();
    showOverviewFeedback(error.detail || "הוספת ההתקן נכשלה", true);
    return;
  }
  showOverviewFeedback(`ההתקן ${sn.trim().toUpperCase()} נוסף בהצלחה.`);
}

async function saveDeviceName(sn) {
  const name = document.getElementById("device-name-input").value;
  const response = await fetch(`/api/devices/${sn}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) {
    const error = await response.json();
    showFeedback(error.detail || "שמירת השם נכשלה", true);
    return;
  }
  showFeedback("השם נשמר בהצלחה.");
}

async function fetchDevices() {
  try {
    const response = await fetch("/api/devices");
    if (!response.ok) return;
    const data = await response.json();
    state.devices = (data.devices || []).map(normalizeDevice);
    refresh();
  } catch (_) {
    // WebSocket remains the primary live channel.
  }
}

async function fetchDevice(sn) {
  try {
    const response = await fetch(`/api/devices/${sn}`);
    if (!response.ok) return;
    const device = await response.json();
    upsertDevice(normalizeDevice(device));
    refresh();
  } catch (_) {
    // Live updates still arrive through WebSocket.
  }
}

async function deleteDevice(sn) {
  const confirmed = window.confirm(`למחוק את ההתקן ${sn}?`);
  if (!confirmed) return;
  const response = await fetch(`/api/devices/${sn}`, { method: "DELETE" });
  if (!response.ok) {
    const error = await response.json();
    showFeedback(error.detail || "מחיקת ההתקן נכשלה", true);
    return;
  }
  showOverviewFeedback(`ההתקן ${sn} נמחק.`);
  unwatchDevice(sn);
  window.location.hash = "/";
}

async function sendOutput(sn, command) {
  const response = await fetch(`/api/devices/${sn}/output`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ command }),
  });
  if (!response.ok) {
    const error = await response.json();
    showFeedback(error.detail || "שליחת הפקודה נכשלה", true);
    return;
  }
  showFeedback(`פקודת ${command === "on" ? "הפעלה" : "כיבוי"} נשלחה.`);
}

async function submitControls(sn) {
  const current = Number(document.getElementById("current-input").value);
  const frequency = Number(document.getElementById("frequency-input").value);
  const response = await fetch(`/api/devices/${sn}/controls`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ current, frequency }),
  });
  if (!response.ok) {
    const error = await response.json();
    showFeedback(error.detail || "עדכון ההגדרות נכשל", true);
    return;
  }
  showFeedback("פקודת זרם ותדר נשלחה לבקר.");
}

function watchDevice(sn) {
  if (state.watchedSn === sn) return;
  if (state.watchedSn && state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ action: "unwatch", sn: state.watchedSn }));
  }
  state.watchedSn = sn;
  if (state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ action: "watch", sn }));
  }
}

function unwatchDevice(sn) {
  if (state.watchedSn !== sn) return;
  if (state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ action: "unwatch", sn }));
  }
  state.watchedSn = null;
}

function showFeedback(message, isError = false) {
  const feedback = document.getElementById("command-feedback");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.className = `command-feedback ${isError ? "status-offline" : "status-online"}`;
}

function showOverviewFeedback(message, isError = false) {
  const feedback = document.getElementById("overview-feedback");
  if (!feedback) return;
  feedback.textContent = message;
  feedback.className = `command-feedback ${isError ? "status-offline" : "status-online"}`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", () => {
  if (state.selectedSn) unwatchDevice(state.selectedSn);
});

connectSocket();
fetchDevices();
route();
