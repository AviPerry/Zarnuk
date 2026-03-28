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
    if (message.type === "devices.snapshot") state.devices = message.payload.devices;
    if (message.type === "device.updated") upsertDevice(message.payload.device);
    refresh();
  });
}

function upsertDevice(device) {
  const index = state.devices.findIndex((entry) => entry.sn === device.sn);
  if (index === -1) state.devices.push(device);
  else state.devices[index] = device;
}

function refresh() {
  if (state.selectedSn) renderDashboard();
  else renderOverview();
}

function renderOverview() {
  const template = document.getElementById("overview-template");
  appEl.replaceChildren(template.content.cloneNode(true));
  const input = document.getElementById("device-search");
  const grid = document.getElementById("device-grid");
  const addForm = document.getElementById("add-device-form");
  const addInput = document.getElementById("add-device-input");
  const commandTopicInput = document.getElementById("add-command-topic-input");
  const telemetryTopicInput = document.getElementById("add-telemetry-topic-input");
  input.value = state.search;
  const draw = () => {
    state.search = input.value.trim().toUpperCase();
    const filtered = state.devices.filter((device) => device.sn.includes(state.search));
    grid.replaceChildren(...filtered.map(buildDeviceCard));
    if (!filtered.length) grid.innerHTML = `<article class="panel"><h3>לא נמצאו התקנים</h3><p>נסה מספר סידורי אחר.</p></article>`;
  };
  input.addEventListener("input", draw);
  addForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await createDevice(addInput.value, commandTopicInput.value, telemetryTopicInput.value);
    addInput.value = "";
    commandTopicInput.value = "";
    telemetryTopicInput.value = "";
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
      <span>סוללה <strong>${device.telemetry.battery_voltage.toFixed(2)} V</strong></span>
      <span>תקינות <strong>${device.telemetry.healthy ? "תקין" : "דורש בדיקה"}</strong></span>
      <span>Ir <strong>${device.telemetry.ir.toFixed(2)} A</strong></span>
      <span>V1 <strong>${device.telemetry.v1.toFixed(1)} V</strong></span>
      <span>פקודות <strong class="mono">${device.command_topic}</strong></span>
      <span>טלמטריה <strong class="mono">${device.telemetry_topic}</strong></span>
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
    appEl.innerHTML = `<article class="panel"><h3>התקן לא נמצא</h3><p>המספר הסידורי ${state.selectedSn || ""} לא קיים במערכת.</p></article>`;
    return;
  }

  document.getElementById("back-button").addEventListener("click", () => {
    unwatchDevice(device.sn);
    window.location.hash = "/";
  });
  document.getElementById("device-title").textContent = `התקן ${device.sn}`;
  const statusEl = document.getElementById("device-online-badge");
  statusEl.textContent = device.online ? "online" : "offline";
  statusEl.className = `status-badge ${device.online ? "status-online" : "status-offline"}`;
  document.getElementById("last-command").textContent = device.last_command_hex || "עדיין לא נשלחה פקודה";
  document.getElementById("ir-value").textContent = device.telemetry.ir.toFixed(2);
  document.getElementById("v1-value").textContent = device.telemetry.v1.toFixed(1);
  document.getElementById("vin-value").textContent = device.telemetry.vin.toFixed(2);
  document.getElementById("battery-value").textContent = device.telemetry.battery_voltage.toFixed(2);
  document.getElementById("telemetry-topic-value").textContent = device.telemetry_topic;
  document.getElementById("command-topic-value").textContent = device.command_topic;
  document.getElementById("current-input").value = device.telemetry.target_current.toFixed(2);
  document.getElementById("frequency-input").value = device.telemetry.target_frequency.toFixed(2);

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

  document.getElementById("output-on").addEventListener("click", () => sendOutput(device.sn, "on"));
  document.getElementById("output-off").addEventListener("click", () => sendOutput(device.sn, "off"));
  document.getElementById("delete-device-button").addEventListener("click", () => deleteDevice(device.sn));
  document.getElementById("control-form").addEventListener("submit", (event) => {
    event.preventDefault();
    submitControls(device.sn);
  });
  watchDevice(device.sn);
}

async function createDevice(sn, commandTopic, telemetryTopic) {
  const response = await fetch("/api/devices", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sn, command_topic: commandTopic, telemetry_topic: telemetryTopic }),
  });
  if (!response.ok) {
    const error = await response.json();
    showOverviewFeedback(error.detail || "הוספת ההתקן נכשלה", true);
    return;
  }
  showOverviewFeedback(`ההתקן ${sn.toUpperCase()} נוסף בהצלחה.`);
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
  showFeedback("פקודת זרם/תדר נשלחה לבקר.");
}

function watchDevice(sn) {
  if (state.watchedSn === sn) return;
  if (state.watchedSn && state.ws?.readyState === WebSocket.OPEN) {
    state.ws.send(JSON.stringify({ action: "unwatch", sn: state.watchedSn }));
  }
  state.watchedSn = sn;
  if (state.ws?.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ action: "watch", sn }));
}

function unwatchDevice(sn) {
  if (state.watchedSn !== sn) return;
  if (state.ws?.readyState === WebSocket.OPEN) state.ws.send(JSON.stringify({ action: "unwatch", sn }));
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

window.addEventListener("hashchange", route);
window.addEventListener("beforeunload", () => { if (state.selectedSn) unwatchDevice(state.selectedSn); });

connectSocket();
route();
