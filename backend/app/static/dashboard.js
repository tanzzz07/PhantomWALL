const state = {
  adminToken: localStorage.getItem("phantomwallAdminToken"),
  currentInstallId: "",
  socket: null,
  reconnectTimer: null,
  isRegisterMode: false,
  activeTab: "analytics",
};

const elements = {
  get authPanel() { return document.getElementById("auth-panel"); },
  get dashboardShell() { return document.getElementById("dashboard-shell"); },
  get loginForm() { return document.getElementById("login-form"); },
  get loginError() { return document.getElementById("login-error"); },
  get username() { return document.getElementById("username"); },
  get password() { return document.getElementById("password"); },
  get installFilter() { return document.getElementById("install-filter"); },
  get backendPill() { return document.getElementById("backend-pill"); },
  get socketPill() { return document.getElementById("socket-pill"); },
  get generatedAt() { return document.getElementById("generated-at"); },
  get blockedCount() { return document.getElementById("blocked-count"); },
  get totalEvents() { return document.getElementById("total-events"); },
  get uniqueTrackers() { return document.getElementById("unique-trackers"); },
  get blockRate() { return document.getElementById("block-rate"); },
  get topTrackers() { return document.getElementById("top-trackers"); },
  get classificationBreakdown() { return document.getElementById("classification-breakdown"); },
  get requestTypes() { return document.getElementById("request-types"); },
  get serviceStatus() { return document.getElementById("service-status"); },
  get thirdPartyCount() { return document.getElementById("third-party-count"); },
  get primaryRequestType() { return document.getElementById("primary-request-type"); },
  get latestTracker() { return document.getElementById("latest-tracker"); },
  get recentEvents() { return document.getElementById("recent-events"); },
  get installCards() { return document.getElementById("install-cards"); },
  get logoutBtn() { return document.getElementById("logout-btn"); },
  get tabAnalytics() { return document.getElementById("tab-analytics"); },
  get tabScriptHistory() { return document.getElementById("tab-script-history"); },
  get analyticsView() { return document.getElementById("analytics-view"); },
  get scriptHistoryView() { return document.getElementById("script-history-view"); },
  get scriptBlockageEvents() { return document.getElementById("script-blockage-events"); },
  get toggleAuthMode() { return document.getElementById("toggle-auth-mode"); },
  get authEyebrow() { return document.getElementById("auth-eyebrow"); },
  get authTitle() { return document.getElementById("auth-title"); },
  get authDesc() { return document.getElementById("auth-desc"); },
  get authSubmitBtn() { return document.getElementById("auth-submit-btn"); },
};


document.addEventListener("DOMContentLoaded", async () => {
  elements.loginForm.addEventListener("submit", handleLogin);
  elements.installFilter.addEventListener("change", async (event) => {
    state.currentInstallId = event.target.value;
    if (state.activeTab === "analytics") {
      await fetchStats();
    } else {
      await fetchBlockedScripts();
    }
  });

  elements.toggleAuthMode.addEventListener("click", (event) => {
    event.preventDefault();
    state.isRegisterMode = !state.isRegisterMode;
    elements.loginError.textContent = "";
    elements.loginError.style.color = "var(--danger)";

    if (state.isRegisterMode) {
      elements.authEyebrow.textContent = "New account registration";
      elements.authTitle.textContent = "Create Dashboard Account";
      elements.authDesc.textContent = "Register a personal account to track and view your specific extension installs and telemetry.";
      elements.authSubmitBtn.textContent = "Register account";
      document.getElementById("toggle-text-prefix").textContent = "Already have an account?";
      elements.toggleAuthMode.textContent = "Log in";
    } else {
      elements.authEyebrow.textContent = "Admin access";
      elements.authTitle.textContent = "PhantomWall Command";
      elements.authDesc.textContent = "Sign in to review all registered installs, live blocked tracker events, and shared telemetry across your deployed extension fleet.";
      elements.authSubmitBtn.textContent = "Enter dashboard";
      document.getElementById("toggle-text-prefix").textContent = "Don't have an account?";
      elements.toggleAuthMode.textContent = "Register";
    }
  });

  elements.logoutBtn.addEventListener("click", () => {
    clearAdminSession();
    if (state.socket) {
      state.socket.close();
      state.socket = null;
    }
    showLogin();
  });

  elements.tabAnalytics.addEventListener("click", () => {
    state.activeTab = "analytics";
    elements.tabAnalytics.classList.add("active");
    elements.tabScriptHistory.classList.remove("active");
    elements.analyticsView.hidden = false;
    elements.scriptHistoryView.hidden = true;
    void fetchStats();
  });

  elements.tabScriptHistory.addEventListener("click", () => {
    state.activeTab = "script-history";
    elements.tabAnalytics.classList.remove("active");
    elements.tabScriptHistory.classList.add("active");
    elements.analyticsView.hidden = true;
    elements.scriptHistoryView.hidden = false;
    void fetchBlockedScripts();
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
  elements.loginError.style.color = "var(--danger)";

  const username = elements.username.value.trim();
  const password = elements.password.value;

  if (state.isRegisterMode) {
    try {
      const response = await fetch("/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const payload = await response.json();
        throw new Error(payload?.detail || "Registration failed");
      }

      elements.loginError.textContent = "Registration successful! You can now log in.";
      elements.loginError.style.color = "var(--accent-2)";
      elements.toggleAuthMode.click();
      elements.username.value = username;
      elements.password.value = "";
    } catch (error) {
      elements.loginError.textContent = error.message;
    }
  } else {
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        throw new Error("Invalid username or password");
      }

      const payload = await response.json();
      state.adminToken = payload.access_token;
      localStorage.setItem("phantomwallAdminToken", state.adminToken);
      await bootstrapAuthenticatedView();
    } catch (error) {
      elements.loginError.textContent = "Incorrect username or password.";
    }
  }
}

async function bootstrapAuthenticatedView() {
  try {
    await fetchAdminIdentity();
    showDashboard();
    await fetchInstalls();
    if (state.activeTab === "analytics") {
      await fetchStats();
    } else {
      await fetchBlockedScripts();
    }
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

async function fetchBlockedScripts() {
  const query = new URLSearchParams({ limit: "50" });
  if (state.currentInstallId) {
    query.set("install_id", state.currentInstallId);
  }

  const response = await authedFetch(`/blocked-scripts?${query.toString()}`);
  if (!response.ok) {
    throw new Error("Blocked scripts request failed");
  }

  const scripts = await response.json();
  renderBlockedScripts(scripts);
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
      if (state.activeTab === "analytics") {
        await fetchStats();
      } else {
        await fetchBlockedScripts();
      }
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

function renderBlockedScripts(scripts) {
  elements.scriptBlockageEvents.innerHTML = "";

  if (!scripts.length) {
    elements.scriptBlockageEvents.innerHTML = `
      <tr>
        <td colspan="5" class="empty-cell">No blocked scripts found</td>
      </tr>
    `;
    return;
  }

  scripts.forEach((script) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${formatTimestamp(script.occurred_at)}</td>
      <td>${escapeHtml(script.install_name || "Unknown")}</td>
      <td>${escapeHtml(formatOrigin(script.page_origin))}</td>
      <td class="tracker-cell" style="word-break: break-all; max-width: 400px;">${escapeHtml(script.url)}</td>
      <td>
        <span class="category-pill ${(script.classification || "Safe").toLowerCase()}">
          ${escapeHtml(script.classification || "Safe")}
        </span>
      </td>
    `;
    elements.scriptBlockageEvents.appendChild(row);
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
      if (state.activeTab === "analytics") {
        renderDashboard(payload.data);
      }
      setBackendStatus(true);
      return;
    }

    if (payload?.type === "telemetry.received") {
      await fetchInstalls();
      if (state.activeTab === "analytics") {
        await fetchStats();
      } else {
        await fetchBlockedScripts();
      }
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
  elements.authPanel.classList.remove("authenticated");
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

