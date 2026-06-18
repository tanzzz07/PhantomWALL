const state = {
  adminToken: localStorage.getItem("phantomwallAdminToken"),
  currentInstallId: "",
  socket: null,
  reconnectTimer: null,
  isRegisterMode: false,
  activeTab: "analytics",
};

const historyState = {
  page: 1,
  limit: 15,
  classification: "",
  requestType: "",
  search: "",
  activeCharts: {}
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
  get observedCount() { return document.getElementById("observed-count"); },
  get blockRate() { return document.getElementById("block-rate"); },
  get avgRiskScore() { return document.getElementById("avg-risk-score"); },
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

  // History controls selectors
  get historySearch() { return document.getElementById("history-search"); },
  get historyFilterClass() { return document.getElementById("history-filter-class"); },
  get historyFilterType() { return document.getElementById("history-filter-type"); },
  get historyPrevBtn() { return document.getElementById("history-prev-btn"); },
  get historyNextBtn() { return document.getElementById("history-next-btn"); },
  get historyPageInfo() { return document.getElementById("history-page-info"); },
  get cleanupBtn() { return document.getElementById("cleanup-btn"); },
  get retentionPill() { return document.getElementById("retention-pill"); },

  // Detail Drawer selectors
  get threatIntelPanel() { return document.getElementById("threat-intel-panel"); },
  get closeIntelBtn() { return document.getElementById("close-intel-btn"); },
  get intelClassification() { return document.getElementById("intel-classification"); },
  get intelRiskScore() { return document.getElementById("intel-risk-score"); },
  get intelConfidence() { return document.getElementById("intel-confidence"); },
  get intelUrl() { return document.getElementById("intel-url"); },
  get intelDomain() { return document.getElementById("intel-domain"); },
  get intelRequestType() { return document.getElementById("intel-request-type"); },
  get intelThirdParty() { return document.getElementById("intel-third-party"); },
  get intelReferrer() { return document.getElementById("intel-referrer"); },
  get intelTimestamp() { return document.getElementById("intel-timestamp"); },
  get intelExplanation() { return document.getElementById("intel-explanation"); },
  get intelTopFeatures() { return document.getElementById("intel-top-features"); },

  // Reputation & alerts selectors
  get dangerousDomainsList() { return document.getElementById("dangerous-domains-list"); },
  get highestRiskCard() { return document.getElementById("highest-risk-card"); },
};

document.addEventListener("DOMContentLoaded", async () => {
  elements.loginForm.addEventListener("submit", handleLogin);

  // Clear stale error messages when user starts interacting with the form
  elements.username.addEventListener("input", () => { elements.loginError.textContent = ""; });
  elements.password.addEventListener("input", () => { elements.loginError.textContent = ""; });

  elements.installFilter.addEventListener("change", async (event) => {
    state.currentInstallId = event.target.value;
    if (state.activeTab === "analytics") {
      await fetchStats();
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
    void fetchHistory();
    void fetchWidgets();
    void fetchHistoryStatsAndDrawCharts();
  });

  // History controls bindings
  elements.historySearch.addEventListener("input", debounce(async (e) => {
    historyState.search = e.target.value.trim();
    historyState.page = 1;
    await fetchHistory();
  }, 300));

  elements.historyFilterClass.addEventListener("change", async (e) => {
    historyState.classification = e.target.value;
    historyState.page = 1;
    await fetchHistory();
  });

  elements.historyFilterType.addEventListener("change", async (e) => {
    historyState.requestType = e.target.value;
    historyState.page = 1;
    await fetchHistory();
  });

  elements.historyPrevBtn.addEventListener("click", async () => {
    if (historyState.page > 1) {
      historyState.page--;
      await fetchHistory();
    }
  });

  elements.historyNextBtn.addEventListener("click", async () => {
    historyState.page++;
    await fetchHistory();
  });

  elements.closeIntelBtn.addEventListener("click", () => {
    elements.threatIntelPanel.setAttribute("hidden", "");
  });

  elements.cleanupBtn.addEventListener("click", async () => {
    if (confirm("Run the database retention cleanup? This will permanently delete raw telemetry logs older than 30 days while keeping Domain Reputation aggregated statistics intact.")) {
      try {
        const res = await authedFetch("/admin/cleanup", { method: "POST" });
        if (res.ok) {
          const result = await res.json();
          alert(`Database cleanup complete. Deleted ${result.deleted_count} events.`);
          await fetchHistory();
          await fetchWidgets();
          await fetchHistoryStatsAndDrawCharts();
        } else {
          const err = await res.json();
          alert(`Cleanup failed: ${err.detail || res.statusText}`);
        }
      } catch (e) {
        alert(`Cleanup failed: ${e}`);
      }
    }
  });

  if (state.adminToken) {
    await bootstrapAuthenticatedView(true);
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
      const regResponse = await fetch("/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!regResponse.ok) {
        const payload = await regResponse.json();
        throw new Error(payload?.detail || "Registration failed");
      }

      // Auto-login after successful registration
      const loginResponse = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });

      if (!loginResponse.ok) {
        // Registration succeeded but auto-login failed; fall back to manual login
        elements.loginError.textContent = "Registration successful! You can now log in.";
        elements.loginError.style.color = "var(--accent-2)";
        state.isRegisterMode = false;
        elements.authEyebrow.textContent = "Admin access";
        elements.authTitle.textContent = "PhantomWall Command";
        elements.authDesc.textContent = "Sign in to review all registered installs, live blocked tracker events, and shared telemetry across your deployed extension fleet.";
        elements.authSubmitBtn.textContent = "Enter dashboard";
        document.getElementById("toggle-text-prefix").textContent = "Don't have an account?";
        elements.toggleAuthMode.textContent = "Register";
        elements.username.value = username;
        elements.password.value = "";
        return;
      }

      const loginPayload = await loginResponse.json();
      state.adminToken = loginPayload.access_token;
      localStorage.setItem("phantomwallAdminToken", state.adminToken);
      await bootstrapAuthenticatedView();
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
        const errPayload = await response.json().catch(() => null);
        throw new Error(errPayload?.detail || "Invalid username or password");
      }

      const payload = await response.json();
      state.adminToken = payload.access_token;
      localStorage.setItem("phantomwallAdminToken", state.adminToken);
      await bootstrapAuthenticatedView();
    } catch (error) {
      elements.loginError.textContent = error.message || "Incorrect username or password.";
    }
  }
}

async function bootstrapAuthenticatedView(isPageLoad = false) {
  try {
    await fetchAdminIdentity();
    showDashboard();
    await fetchInstalls();
    if (state.activeTab === "analytics") {
      await fetchStats();
    } else {
      await fetchHistory();
      await fetchWidgets();
      await fetchHistoryStatsAndDrawCharts();
    }
    connectLiveStream();
  } catch (error) {
    clearAdminSession();
    showLogin();
    // Only show "session expired" if this was an automatic page-load check
    // with a stale token. Don't show it after a fresh login attempt fails
    // (that case is handled by handleLogin's own catch block).
    if (isPageLoad) {
      // Silently clear the stale token — don't confuse the user
      // They just need to log in normally.
    } else {
      elements.loginError.textContent = "Session could not be established. Please sign in again.";
    }
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

  // Render observed stats from overall DB if available, fallback to difference
  const observedCount = Math.max(totalEvents - blockedCount, 0);

  elements.blockedCount.textContent = formatNumber(blockedCount);
  if (elements.observedCount) elements.observedCount.textContent = formatNumber(observedCount);
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

// --- NEW TELEMETRY & INTEL SCRIPTS ---

async function fetchHistory() {
  const query = new URLSearchParams({
    page: historyState.page,
    limit: historyState.limit
  });
  if (historyState.classification) {
    query.set("classification", historyState.classification);
  }
  if (historyState.requestType) {
    query.set("request_type", historyState.requestType);
  }
  if (historyState.search) {
    query.set("search", historyState.search);
  }

  const response = await authedFetch(`/history?${query.toString()}`);
  if (!response.ok) {
    console.error("Failed to fetch script history logs");
    return;
  }

  const data = await response.json();
  renderHistoryTable(data.items || []);
  
  elements.historyPageInfo.textContent = `Page ${data.page} of ${Math.max(data.pages, 1)}`;
  elements.historyPrevBtn.disabled = data.page <= 1;
  elements.historyNextBtn.disabled = data.page >= data.pages;
}

function renderHistoryTable(items) {
  const container = elements.scriptBlockageEvents;
  container.innerHTML = "";

  if (!items.length) {
    container.innerHTML = `
      <tr>
        <td colspan="7" class="empty-cell">No matching telemetry logs found</td>
      </tr>
    `;
    return;
  }

  items.forEach((item) => {
    const row = document.createElement("tr");
    row.className = "clickable-row";
    row.innerHTML = `
      <td>${formatTimestamp(item.timestamp)}</td>
      <td class="tracker-cell" style="color: var(--accent);">${escapeHtml(item.domain)}</td>
      <td>${escapeHtml(item.request_type)}</td>
      <td>
        <span class="category-pill ${item.classification.toLowerCase()}">
          ${escapeHtml(item.classification)}
        </span>
      </td>
      <td style="font-family: monospace;">${(item.confidence * 100).toFixed(0)}%</td>
      <td style="font-weight: bold; font-family: monospace; color: ${getRiskColor(item.risk_score)};">${item.risk_score}</td>
      <td>
        <span class="decision-pill ${item.blocked ? "blocked" : "observed"}">
          ${item.blocked ? "Blocked" : "Observed"}
        </span>
      </td>
    `;
    
    row.addEventListener("click", () => {
      openIntelDrawer(item);
    });
    
    container.appendChild(row);
  });
}

function getRiskColor(score) {
  if (score >= 80) return "var(--danger)";
  if (score >= 50) return "var(--warning)";
  return "var(--accent-2)";
}

function openIntelDrawer(item) {
  elements.intelClassification.textContent = item.classification;
  elements.intelClassification.className = `category-pill ${item.classification.toLowerCase()}`;
  elements.intelRiskScore.textContent = item.risk_score;
  elements.intelRiskScore.style.color = getRiskColor(item.risk_score);
  elements.intelConfidence.textContent = `${(item.confidence * 100).toFixed(0)}%`;
  elements.intelUrl.textContent = item.full_url;
  elements.intelDomain.textContent = item.domain;
  elements.intelRequestType.textContent = item.request_type;
  elements.intelThirdParty.textContent = item.third_party ? "Yes (Cross-Origin)" : "No (Same-Origin)";
  elements.intelThirdParty.style.color = item.third_party ? "var(--warning)" : "var(--accent-2)";
  elements.intelReferrer.textContent = item.referrer || "Direct (None)";
  elements.intelTimestamp.textContent = formatTimestamp(item.timestamp);
  elements.intelExplanation.textContent = item.explanation || "No explanation summary available.";
  
  elements.intelTopFeatures.innerHTML = "";
  if (Array.isArray(item.top_features) && item.top_features.length) {
    item.top_features.forEach((feat) => {
      const chip = document.createElement("span");
      chip.className = "status-pill online";
      chip.style.fontSize = "10px";
      chip.style.padding = "4px 8px";
      chip.style.background = "rgba(0, 211, 255, 0.08)";
      chip.style.borderColor = "rgba(0, 211, 255, 0.2)";
      chip.style.color = "var(--accent)";
      chip.textContent = feat.replace(/_score|_flag/g, "").replace(/_/g, " ");
      elements.intelTopFeatures.appendChild(chip);
    });
  } else {
    elements.intelTopFeatures.innerHTML = `<span style="font-size: 12px; color: var(--muted);">None</span>`;
  }
  
  elements.threatIntelPanel.removeAttribute("hidden");
}

async function fetchWidgets() {
  const repResponse = await authedFetch("/reputation/top-risk?limit=5");
  if (repResponse.ok) {
    const domains = await repResponse.json();
    renderDangerousDomains(domains);
  }

  const historyResponse = await authedFetch("/history?limit=50");
  if (historyResponse.ok) {
    const data = await historyResponse.json();
    const items = data.items || [];
    if (items.length) {
      const highestRiskItem = items.reduce((prev, current) => (prev.risk_score > current.risk_score) ? prev : current);
      renderHighestRiskEvent(highestRiskItem);
    } else {
      renderHighestRiskEvent(null);
    }
  }
}

function renderDangerousDomains(domains) {
  const container = elements.dangerousDomainsList;
  container.innerHTML = "";

  if (!domains.length) {
    container.innerHTML = `
      <tr>
        <td colspan="6" class="empty-cell">No dangerous domains detected yet</td>
      </tr>
    `;
    return;
  }

  domains.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td style="font-family: monospace; font-weight: bold; color: var(--accent);">${escapeHtml(item.domain)}</td>
      <td>
        <span class="category-pill ${item.classification.toLowerCase()}">
          ${escapeHtml(item.classification)}
        </span>
      </td>
      <td>${item.times_seen}</td>
      <td>${item.times_blocked}</td>
      <td style="font-weight: bold; font-family: monospace; color: ${getRiskColor(item.average_risk_score)};">${item.average_risk_score.toFixed(0)}</td>
      <td>${formatTimestamp(item.last_seen)}</td>
    `;
    container.appendChild(row);
  });
}

function renderHighestRiskEvent(event) {
  const container = elements.highestRiskCard;
  if (!event || event.risk_score < 40) {
    container.innerHTML = `<p class="empty-state">No critical telemetry event detected</p>`;
    return;
  }

  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center;">
      <span style="font-size: 11px; color: var(--danger); font-weight: bold; letter-spacing: 0.1em; text-transform: uppercase;">Highest Risk Alert</span>
      <span class="category-pill ${event.classification.toLowerCase()}">${escapeHtml(event.classification)}</span>
    </div>
    <div style="font-size: 28px; font-weight: bold; color: var(--danger); margin: 6px 0;">
      Risk Score: ${event.risk_score}
    </div>
    <div style="font-family: monospace; font-size: 13px; word-break: break-all; color: var(--text);">
      ${escapeHtml(event.domain)}
    </div>
    <div style="font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.4;">
      URL: ${escapeHtml(event.full_url.substring(0, 80))}${event.full_url.length > 80 ? "..." : ""}
    </div>
    <div style="font-size: 11px; color: var(--muted); margin-top: 4px;">
      Logged: ${formatTimestamp(event.timestamp)}
    </div>
  `;
}

async function fetchHistoryStatsAndDrawCharts() {
  const response = await authedFetch("/history/stats");
  if (!response.ok) {
    console.error("Failed to fetch history stats");
    return;
  }
  const hStats = await response.json();
  
  const topDomResponse = await authedFetch("/history/top-domains?limit=5");
  let topDomains = [];
  if (topDomResponse.ok) {
    topDomains = await topDomResponse.json();
  }

  updateCharts(hStats, topDomains);
  updateHistoryStatsCards(hStats);
}

function updateHistoryStatsCards(hStats) {
  const blockedCount = Number(hStats.blocked_count || 0);
  const observedCount = Number(hStats.observed_count || 0);
  const total = blockedCount + observedCount;
  const blockRate = total > 0 ? Math.round((blockedCount / total) * 100) : 0;
  const avgRisk = Number(hStats.average_risk_score || 0).toFixed(1);

  if (elements.blockedCount) elements.blockedCount.textContent = formatNumber(blockedCount);
  if (elements.observedCount) elements.observedCount.textContent = formatNumber(observedCount);
  if (elements.blockRate) elements.blockRate.textContent = `${blockRate}%`;
  if (elements.avgRiskScore) elements.avgRiskScore.textContent = avgRisk;
}

function updateCharts(stats, topDomains) {
  // 1. Threat Distribution Chart (Doughnut)
  renderDoughnutChart(
    "chart-threat-dist",
    ["Analytics", "Advertising", "Fingerprinting", "Suspicious"],
    [stats.analytics, stats.advertising, stats.fingerprinting, stats.suspicious],
    ["#00d3ff", "#ff9f43", "#a55eea", "#ff637e"]
  );

  // 2. Top Blocked Domains Chart (Horizontal Bar)
  const topDomLabels = topDomains.map(d => d.domain);
  const topDomCounts = topDomains.map(d => d.count);
  renderHorizontalBarChart("chart-top-domains", topDomLabels, topDomCounts, "#00d3ff");

  // 3. Blocked Requests Over Time Chart (Line)
  const timeLabels = stats.over_time.map(d => d.date);
  const timeCounts = stats.over_time.map(d => d.count);
  renderLineChart("chart-over-time", timeLabels, timeCounts, "#2affb4");

  // 4. Top Request Types Chart (Bar)
  const typeLabels = stats.request_types.map(t => t.type);
  const typeCounts = stats.request_types.map(t => t.count);
  renderBarChart("chart-request-types", typeLabels, typeCounts, "#00d3ff");

  // 5. Risk Score Distribution Chart (Bar)
  const riskLabels = stats.risk_distribution.map(r => `Risk ${r.risk_score}`);
  const riskCounts = stats.risk_distribution.map(r => r.count);
  renderBarChart("chart-risk-dist", riskLabels, riskCounts, "#ff637e");
}

function destroyChart(id) {
  if (historyState.activeCharts[id]) {
    historyState.activeCharts[id].destroy();
    delete historyState.activeCharts[id];
  }
}

function renderDoughnutChart(id, labels, data, colors) {
  destroyChart(id);
  const ctx = document.getElementById(id).getContext("2d");
  historyState.activeCharts[id] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          position: "bottom",
          labels: { color: "#8ca8c7", boxWidth: 10, font: { size: 9 } }
        }
      }
    }
  });
}

function renderHorizontalBarChart(id, labels, data, color) {
  destroyChart(id);
  const ctx = document.getElementById(id).getContext("2d");
  historyState.activeCharts[id] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: color,
        borderRadius: 4
      }]
    },
    options: {
      indexAxis: "y",
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#8ca8c7", font: { size: 9 } } },
        y: { grid: { display: false }, ticks: { color: "#8ca8c7", font: { size: 9 } } }
      }
    }
  });
}

function renderBarChart(id, labels, data, color) {
  destroyChart(id);
  const ctx = document.getElementById(id).getContext("2d");
  historyState.activeCharts[id] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: color,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: "#8ca8c7", font: { size: 9 } } },
        y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#8ca8c7", font: { size: 9 } } }
      }
    }
  });
}

function renderLineChart(id, labels, data, color) {
  destroyChart(id);
  const ctx = document.getElementById(id).getContext("2d");
  historyState.activeCharts[id] = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [{
        data: data,
        borderColor: color,
        backgroundColor: "rgba(42, 255, 180, 0.05)",
        fill: true,
        tension: 0.3,
        borderWidth: 2,
        pointRadius: 2
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#8ca8c7", font: { size: 9 } } },
        y: { grid: { color: "rgba(255,255,255,0.03)" }, ticks: { color: "#8ca8c7", font: { size: 9 } } }
      }
    }
  });
}

// --- UTILS ---

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
      }
      setSocketStatus("online", "Live stream active");
    }

    if (payload?.type === "history.new") {
      await fetchInstalls();
      if (state.activeTab === "script-history") {
        await fetchHistory();
        await fetchWidgets();
        await fetchHistoryStatsAndDrawCharts();
      } else {
        await fetchStats();
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

function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
