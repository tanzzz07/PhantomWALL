const blockedCountElement = document.getElementById("blocked-count");
const lastUpdatedElement = document.getElementById("last-updated");
const protectionPillElement = document.getElementById("protection-pill");
const backendStatusElement = document.getElementById("backend-status");
const streamStatusElement = document.getElementById("stream-status");
const topDomainsElement = document.getElementById("top-domains");
const rulesStatusElement = document.getElementById("rules-status");
const registrationStatusElement = document.getElementById("registration-status");
const installMetaElement = document.getElementById("install-meta");
const setupButtonElement = document.getElementById("setup-button");
const dashboardButtonElement = document.getElementById("dashboard-button");

let refreshTimer = null;

document.addEventListener("DOMContentLoaded", async () => {
  setupButtonElement.addEventListener("click", () => {
    void chrome.runtime.sendMessage({ type: "OPEN_OPTIONS" });
  });
  dashboardButtonElement.addEventListener("click", async () => {
    const stats = await chrome.runtime.sendMessage({ type: "GET_STATS" });
    const endpoint = stats.backend?.endpoint;
    if (endpoint) {
      window.open(`${endpoint}/dashboard`, "_blank");
    }
  });
  await refreshStats();
  refreshTimer = setInterval(refreshStats, 4000);
});

window.addEventListener("beforeunload", () => {
  if (refreshTimer) {
    clearInterval(refreshTimer);
  }
});

chrome.runtime.onMessage.addListener((message) => {
  if (message?.type === "STATS_UPDATED" && message.payload) {
    renderStats(message.payload);
  }
});

async function refreshStats() {
  const stats = await chrome.runtime.sendMessage({ type: "GET_STATS" });
  renderStats(stats);
}

function renderStats(stats) {
  blockedCountElement.textContent = String(stats.blockedCount ?? 0);
  lastUpdatedElement.textContent = stats.lastUpdated
    ? `Last event ${formatRelativeTime(stats.lastUpdated)}`
    : "Awaiting telemetry";

  const protectionActive = Boolean(stats.protectionEnabled);
  protectionPillElement.textContent = protectionActive
    ? "Shield active"
    : "Shield paused";
  protectionPillElement.className = `status-pill ${protectionActive ? "online" : "offline"}`;

  rulesStatusElement.textContent = stats.rulesLoaded
    ? "Ruleset armed"
    : "Ruleset unavailable";

  backendStatusElement.textContent = stats.backend?.healthy ? "Online" : "Offline";
  streamStatusElement.textContent = stats.backend?.lastSyncAt
    ? `Synced ${formatRelativeTime(stats.backend.lastSyncAt)}`
    : stats.backend?.lastError
      ? "Telemetry buffering locally"
      : "Live stream idle";
  registrationStatusElement.textContent = stats.backend?.registered
    ? "Install linked"
    : "Setup needed";
  installMetaElement.textContent = stats.backend?.registered
    ? `${stats.backend.installName || "Install"} is connected`
    : "Open setup and register this extension install.";

  renderTopDomains(stats.topDomains || []);
}

function renderTopDomains(domains) {
  topDomainsElement.innerHTML = "";

  if (!domains.length) {
    const emptyItem = document.createElement("li");
    emptyItem.className = "empty-state";
    emptyItem.textContent = "No blocked trackers yet";
    topDomainsElement.appendChild(emptyItem);
    return;
  }

  domains.forEach((entry, index) => {
    const item = document.createElement("li");
    item.className = "tracker-item";
    item.innerHTML = `
      <div>
        <span class="tracker-rank">0${index + 1}</span>
        <span class="tracker-domain">${entry.domain}</span>
      </div>
      <span class="tracker-count">${entry.count}</span>
    `;
    topDomainsElement.appendChild(item);
  });
}

function formatRelativeTime(timestamp) {
  const deltaMs = Date.now() - new Date(timestamp).getTime();
  const seconds = Math.max(1, Math.floor(deltaMs / 1000));

  if (seconds < 60) {
    return `${seconds}s ago`;
  }

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}
