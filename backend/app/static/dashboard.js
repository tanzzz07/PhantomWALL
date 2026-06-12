const state = {
  adminToken: localStorage.getItem("phantomwallAdminToken"),
  currentInstallId: "",
  socket: null,
  reconnectTimer: null,
};

const elements = {
  authPanel: document.getElementById("auth-panel"),
  dashboardShell: document.getElementById("dashboard-shell"),
  loginForm: document.getElementById("login-form"),
  loginError: document.getElementById("login-error"),
  username: document.getElementById("username"),
  password: document.getElementById("password"),
  installFilter: document.getElementById("install-filter"),
  backendPill: document.getElementById("backend-pill"),
  socketPill: document.getElementById("socket-pill"),
  generatedAt: document.getElementById("generated-at"),
  blockedCount: document.getElementById("blocked-count"),
  totalEvents: document.getElementById("total-events"),
  uniqueTrackers: document.getElementById("unique-trackers"),
  blockRate: document.getElementById("block-rate"),
  topTrackers: document.getElementById("top-trackers"),
  classificationBreakdown: document.getElementById("classification-breakdown"),
  requestTypes: document.getElementById("request-types"),
  serviceStatus: document.getElementById("service-status"),
  thirdPartyCount: document.getElementById("third-party-count"),
  primaryRequestType: document.getElementById("primary-request-type"),
  latestTracker: document.getElementById("latest-tracker"),
  recentEvents: document.getElementById("recent-events"),
  installCards: document.getElementById("install-cards"),
};

document.addEventListener("DOMContentLoaded", async () => {
  elements.loginForm.addEventListener("submit", handleLogin);
  elements.installFilter.addEventListener("change", async (event) => {
    state.currentInstallId = event.target.value;
    await fetchStats();
  });

  if (state.adminToken) {
    await bootstrapAuthenticatedView();
  } else {
    showLogin();
  }
});

async function handleLogin(event) {
  event.preventDefault();
  elements.loginError.textContent = "";

  try {
    const response = await fetch("/auth/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username: elements.username.value.trim(),
        password: elements.password.value,
      }),
    });

    if (!response.ok) {
      throw new Error("Login failed");
    }

    const payload = await response.json();
    state.adminToken = payload.access_token;
    localStorage.setItem("phantomwallAdminToken", state.adminToken);
    await bootstrapAuthenticatedView();
  } catch (error) {
    elements.loginError.textContent = "Incorrect admin username or password.";
  }
}

async function bootstrapAuthenticatedView() {
  try {
    await fetchAdminIdentity();
    showDashboard();
    await Promise.all([fetchInstalls(), fetchStats()]);
    connectLiveStream();
  } catch (error) {
    clearAdminSession();
    showLogin();
    elements.loginError.textContent = "Your session expired. Please sign in again.";
  }
}

async function fetchAdminIdentity() {
  const response = await authedFetch("/auth/me");
  if (!response.ok) {
    throw new Error("Admin session invalid");
  }
}

async function fetchInstalls() {
  const response = await authedFetch("/installs");
  if (!response.ok) {
    throw new Error("Install list request failed");
  }

  const payload = await response.json();
  renderInstallFilter(payload.installs || []);
  renderInstallCards(payload.installs || []);
}

async function fetchStats() {
  const query = new URLSearchParams({ recent_limit: "25" });
  if (state.currentInstallId) {
    query.set("install_id", state.currentInstallId);
  }

  const response = await authedFetch(`/stats?${query.toString()}`);
  if (!response.ok) {
    throw new Error("Stats request failed");
  }

  const stats = await response.json();
  renderDashboard(stats);
  setBackendStatus(true);
}

function renderDashboard(stats) {
  const recentEvents = Array.isArray(stats.recent_events) ? stats.recent_events : [];
  const topDomains = Array.isArray(stats.top_tracker_domains)
    ? stats.top_tracker_domains
    : [];
  const requestBreakdown = Array.isArray(stats.request_type_breakdown)
    ? stats.request_type_breakdown
    : [];
  const classificationBreakdown = Array.isArray(stats.classification_breakdown)
    ? stats.classification_breakdown
    : [];
  const blockedCount = Number(stats.blocked_tracker_count || 0);
  const totalEvents = Number(stats.total_events || 0);
  const blockRate = totalEvents > 0
    ? Math.round((blockedCount / totalEvents) * 100)
    : 0;

  elements.blockedCount.textContent = formatNumber(blockedCount);
  elements.totalEvents.textContent = formatNumber(totalEvents);
  elements.uniqueTrackers.textContent = formatNumber(stats.unique_tracker_count || 0);
  elements.blockRate.textContent = `${blockRate}%`;
  elements.serviceStatus.textContent = capitalize(stats.service_status || "unknown");
  elements.generatedAt.textContent = stats.generated_at
    ? `Last backend update ${formatTimestamp(stats.generated_at)}`
    : "Waiting for first snapshot";

  const thirdPartyCount = recentEvents.filter((event) => event.third_party).length;
  elements.thirdPartyCount.textContent = formatNumber(thirdPartyCount);
  elements.latestTracker.textContent = recentEvents[0]?.tracker_domain || "No data";
  elements.primaryRequestType.textContent = requestBreakdown[0]?.domain || "N/A";

  renderBars(
    elements.topTrackers,
    topDomains.map((entry) => ({
      label: entry.domain,
      value: entry.count,
    })),
    "No tracker activity yet"
  );

  renderBars(
    elements.classificationBreakdown,
    classificationBreakdown.map((entry) => ({
      label: entry.domain,
      value: entry.count,
    })),
    "Waiting for classification telemetry"
  );

  renderBars(
    elements.requestTypes,
    requestBreakdown.map((entry) => ({
      label: entry.domain,
      value: entry.count,
    })),
    "Waiting for request telemetry"
  );

  renderRecentEvents(recentEvents);
}

function renderInstallFilter(installs) {
  const previous = state.currentInstallId;
  elements.installFilter.innerHTML = "";

  const allOption = document.createElement("option");
  allOption.value = "";
  allOption.textContent = "All installs";
  elements.installFilter.appendChild(allOption);

  installs.forEach((install) => {
    const option = document.createElement("option");
    option.value = install.install_id;
    option.textContent = install.display_name;
    elements.installFilter.appendChild(option);
  });

  elements.installFilter.value = previous;
}

function renderInstallCards(installs) {
  elements.installCards.innerHTML = "";

  if (!installs.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No installs have been registered yet.";
    elements.installCards.appendChild(empty);
    return;
  }

  installs.forEach((install) => {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "install-card";
    card.innerHTML = `
      <span class="install-name">${escapeHtml(install.display_name)}</span>
      <span class="install-metric">${formatNumber(install.blocked_count)} blocked</span>
      <span class="install-meta">${formatNumber(install.event_count)} events</span>
    `;
    card.addEventListener("click", async () => {
      state.currentInstallId = install.install_id;
      elements.installFilter.value = install.install_id;
      await fetchStats();
    });
    elements.installCards.appendChild(card);
  });
}

function renderBars(container, items, emptyMessage) {
  container.innerHTML = "";

  if (!items.length) {
    const emptyState = document.createElement("p");
    emptyState.className = "empty-state";
    emptyState.textContent = emptyMessage;
    container.appendChild(emptyState);
    return;
  }

  const maxValue = Math.max(...items.map((item) => item.value), 1);
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <div class="bar-meta">
        <span class="bar-label">${escapeHtml(item.label)}</span>
        <span class="bar-value">${item.value}</span>
      </div>
      <div class="bar-track">
        <div class="bar-fill" style="width: ${(item.value / maxValue) * 100}%"></div>
      </div>
    `;
    container.appendChild(row);
  });
}

function renderRecentEvents(events) {
  elements.recentEvents.innerHTML = "";

  if (!events.length) {
    elements.recentEvents.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell">No events received yet</td>
      </tr>
    `;
    return;
  }

  events.forEach((event) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatTimestamp(event.occurred_at)}</td>
      <td>${escapeHtml(event.install_name || "Unknown")}</td>
      <td class="tracker-cell">${escapeHtml(event.tracker_domain)}</td>
      <td>${escapeHtml(event.request_type || "unknown")}</td>
      <td>${escapeHtml(formatOrigin(event.page_origin))}</td>
      <td>
        <span class="category-pill ${(event.classification || "Safe").toLowerCase()}">
          ${escapeHtml(event.classification || "Safe")}
        </span>
      </td>
      <td>
        <span class="decision-pill ${event.blocked ? "blocked" : "observed"}">
          ${event.blocked ? "Blocked" : "Observed"}
        </span>
      </td>
    `;
    elements.recentEvents.appendChild(row);
  });
}

function connectLiveStream() {
  if (!state.adminToken) {
    return;
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socketUrl = `${protocol}//${window.location.host}/ws/live?token=${encodeURIComponent(state.adminToken)}`;

  if (state.socket) {
    state.socket.close();
  }

  state.socket = new WebSocket(socketUrl);
  setSocketStatus("connecting", "Connecting live stream");

  state.socket.onopen = () => {
    setSocketStatus("online", "Live stream active");
  };

  state.socket.onmessage = async (event) => {
    const payload = JSON.parse(event.data);
    if (payload?.type === "stats.snapshot") {
      renderDashboard(payload.data);
      setBackendStatus(true);
      return;
    }

    if (payload?.type === "telemetry.received") {
      await fetchInstalls();
      await fetchStats();
      setSocketStatus("online", "Live stream active");
    }
  };

  state.socket.onerror = () => {
    setSocketStatus("idle", "Live stream error");
  };

  state.socket.onclose = () => {
    setSocketStatus("idle", "Retrying live stream");
    clearTimeout(state.reconnectTimer);
    state.reconnectTimer = setTimeout(connectLiveStream, 3000);
  };
}

function setBackendStatus(isOnline) {
  elements.backendPill.textContent = isOnline ? "Backend online" : "Backend offline";
  elements.backendPill.className = `status-pill ${isOnline ? "online" : "offline"}`;
}

function setSocketStatus(mode, label) {
  elements.socketPill.textContent = label;
  elements.socketPill.className = `status-pill ${mode}`;
}

function showLogin() {
  elements.authPanel.hidden = false;
  elements.dashboardShell.hidden = true;
}

function showDashboard() {
  elements.authPanel.hidden = false;
  elements.dashboardShell.hidden = false;
  elements.authPanel.classList.add("authenticated");
}

function clearAdminSession() {
  state.adminToken = null;
  localStorage.removeItem("phantomwallAdminToken");
}

async function authedFetch(url, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${state.adminToken}`);
  return fetch(url, { ...options, headers });
}

function formatNumber(value) {
  return new Intl.NumberFormat().format(value);
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatOrigin(origin) {
  if (!origin) {
    return "Unknown";
  }

  try {
    return new URL(origin).hostname;
  } catch (error) {
    return origin;
  }
}

function capitalize(value) {
  if (!value) {
    return value;
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
