const ANALYTICS_STORAGE_KEY = "phantomwallAnalytics";
const CONFIG_STORAGE_KEY = "phantomwallConfig";
const DEFAULT_BACKEND_ENDPOINT = "http://localhost:8000";
const BACKEND_FAILURE_BACKOFF_MS = 30000;
const MONITORED_RESOURCE_TYPES = new Set([
  "script",
  "xmlhttprequest",
  "image",
  "ping",
  "sub_frame",
]);

const defaultState = {
  blockedCount: 0,
  trackerHits: {},
  lastUpdated: null,
  protectionEnabled: true,
  rulesLoaded: false,
  backend: {
    endpoint: DEFAULT_BACKEND_ENDPOINT,
    healthy: false,
    lastSyncAt: null,
    lastError: null,
    registered: false,
    installId: null,
    installName: null,
  },
};

const defaultConfig = {
  backendEndpoint: DEFAULT_BACKEND_ENDPOINT,
  displayName: "",
  inviteCode: "",
  installId: null,
  installToken: null,
  registeredAt: null,
  browserName: "Chrome",
  extensionVersion: chrome.runtime.getManifest().version,
};

let analyticsState = structuredClone(defaultState);
let configState = structuredClone(defaultConfig);
let trackerMatchers = [];
let backendBackoffUntil = 0;
let startupReady = false;
let startupPromise = null;

chrome.runtime.onInstalled.addListener(async (details) => {
  await initializeState();
  await ensureRulesetEnabled();
  if (details.reason === "install") {
    await chrome.runtime.openOptionsPage();
  }
});

chrome.runtime.onStartup.addListener(async () => {
  await initializeState();
});

chrome.webRequest.onBeforeRequest.addListener(
  (details) => {
    void handleObservedRequest(details);
  },
  { urls: ["<all_urls>"] }
);

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "GET_STATS") {
    getPublicStats().then(sendResponse);
    return true;
  }

  if (message?.type === "GET_CONFIG") {
    getConfigSnapshot().then(sendResponse);
    return true;
  }

  if (message?.type === "SAVE_CONFIG") {
    saveConfig(message.payload || {}).then(sendResponse);
    return true;
  }

  if (message?.type === "REGISTER_INSTALL") {
    registerInstall(message.payload || {}).then(sendResponse);
    return true;
  }

  if (message?.type === "OPEN_OPTIONS") {
    chrome.runtime.openOptionsPage();
    sendResponse({ ok: true });
    return false;
  }

  return false;
});

void initializeState();

async function initializeState() {
  if (startupPromise) {
    return startupPromise;
  }

  if (startupReady) {
    return;
  }

  startupPromise = (async () => {
    const stored = await chrome.storage.local.get([
      ANALYTICS_STORAGE_KEY,
      CONFIG_STORAGE_KEY,
    ]);
    analyticsState = {
      ...structuredClone(defaultState),
      ...(stored[ANALYTICS_STORAGE_KEY] || {}),
      backend: {
        ...defaultState.backend,
        ...(stored[ANALYTICS_STORAGE_KEY]?.backend || {}),
      },
    };
    configState = {
      ...structuredClone(defaultConfig),
      ...(stored[CONFIG_STORAGE_KEY] || {}),
    };
    configState.extensionVersion = chrome.runtime.getManifest().version;
    syncBackendMetadata();

    trackerMatchers = await loadTrackerMatchers();
    analyticsState.rulesLoaded = trackerMatchers.length > 0;
    startupReady = true;

    await ensureRulesetEnabled();
    await updateBadge();
    await persistState();
  })();

  try {
    await startupPromise;
  } finally {
    startupPromise = null;
  }
}

async function ensureRulesetEnabled() {
  const enabledRulesets = await chrome.declarativeNetRequest.getEnabledRulesets();
  if (!enabledRulesets.includes("tracker-rules")) {
    await chrome.declarativeNetRequest.updateEnabledRulesets({
      enableRulesetIds: ["tracker-rules"],
    });
  }
  analyticsState.protectionEnabled = true;
}

function syncBackendMetadata() {
  analyticsState.backend.endpoint = configState.backendEndpoint;
  analyticsState.backend.registered = Boolean(
    configState.installId && configState.installToken
  );
  analyticsState.backend.installId = configState.installId;
  analyticsState.backend.installName = configState.displayName || null;
}

async function loadTrackerMatchers() {
  try {
    const response = await fetch(chrome.runtime.getURL("rules.json"));
    const rules = await response.json();
    return rules
      .map((rule) => buildTrackerMatcher(rule?.condition?.urlFilter))
      .filter(Boolean);
  } catch (error) {
    console.warn("PhantomWall failed to load tracker rules", error);
    return [];
  }
}

async function handleObservedRequest(details) {
  if (!startupReady) {
    await initializeState();
  }

  if (details.tabId < 0) {
    return;
  }

  if (!MONITORED_RESOURCE_TYPES.has(details.type)) {
    return;
  }

  const trackerDomain = matchTrackerDomain(details.url);
  if (!trackerDomain) {
    return;
  }

  const pageOrigin = details.initiator || details.documentUrl || "";
  if (!isThirdPartyRequest(pageOrigin, details.url)) {
    return;
  }

  const event = {
    tracker_domain: trackerDomain,
    url: details.url,
    page_origin: pageOrigin || null,
    request_type: details.type,
    source: "extension",
    blocked: true,
    third_party: true,
    occurred_at: new Date().toISOString(),
  };

  analyticsState.blockedCount += 1;
  analyticsState.trackerHits[trackerDomain] =
    (analyticsState.trackerHits[trackerDomain] || 0) + 1;
  analyticsState.lastUpdated = event.occurred_at;

  await updateBadge();
  await persistState();
  await pushStatsUpdate();
  void sendEventToBackend(event);
}

async function persistState() {
  await chrome.storage.local.set({
    [ANALYTICS_STORAGE_KEY]: analyticsState,
    [CONFIG_STORAGE_KEY]: configState,
  });
}

async function updateBadge() {
  const badgeText = analyticsState.blockedCount > 0
    ? String(Math.min(analyticsState.blockedCount, 999))
    : "";

  await chrome.action.setBadgeBackgroundColor({ color: "#00d1ff" });
  await chrome.action.setBadgeText({ text: badgeText });
}

async function getPublicStats() {
  const topDomains = Object.entries(analyticsState.trackerHits)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([domain, count]) => ({ domain, count }));

  return {
    blockedCount: analyticsState.blockedCount,
    topDomains,
    protectionEnabled: analyticsState.protectionEnabled,
    rulesLoaded: analyticsState.rulesLoaded,
    lastUpdated: analyticsState.lastUpdated,
    backend: analyticsState.backend,
  };
}

async function getConfigSnapshot() {
  if (!startupReady) {
    await initializeState();
  }

  return {
    backendEndpoint: configState.backendEndpoint,
    displayName: configState.displayName,
    inviteCode: configState.inviteCode,
    installId: configState.installId,
    registeredAt: configState.registeredAt,
    isRegistered: Boolean(configState.installId && configState.installToken),
    extensionVersion: configState.extensionVersion,
    browserName: configState.browserName,
    backendHealthy: analyticsState.backend.healthy,
    lastError: analyticsState.backend.lastError,
  };
}

async function saveConfig(payload) {
  if (!startupReady) {
    await initializeState();
  }

  configState = {
    ...configState,
    backendEndpoint: normalizeBackendEndpoint(
      payload.backendEndpoint ?? configState.backendEndpoint
    ),
    displayName: (payload.displayName ?? configState.displayName).trim(),
    inviteCode: (payload.inviteCode ?? configState.inviteCode).trim(),
    browserName: payload.browserName ?? configState.browserName,
    extensionVersion: chrome.runtime.getManifest().version,
  };

  if (payload.clearRegistration) {
    configState.installId = null;
    configState.installToken = null;
    configState.registeredAt = null;
  }

  syncBackendMetadata();
  await persistState();
  await pushStatsUpdate();
  return { ok: true, config: await getConfigSnapshot() };
}

async function registerInstall(payload) {
  if (!startupReady) {
    await initializeState();
  }

  await saveConfig(payload);

  if (!configState.backendEndpoint || !configState.displayName || !configState.inviteCode) {
    return {
      ok: false,
      error: "Backend URL, display name, and invite code are required.",
    };
  }

  try {
    const response = await fetch(`${configState.backendEndpoint}/installs/register`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        display_name: configState.displayName,
        invite_code: configState.inviteCode,
        extension_version: chrome.runtime.getManifest().version,
        browser_name: configState.browserName,
      }),
    });

    if (!response.ok) {
      const errorPayload = await safeJson(response);
      throw new Error(errorPayload?.detail || `Backend responded with ${response.status}`);
    }

    const registration = await response.json();
    configState.installId = registration.install_id;
    configState.installToken = registration.api_token;
    configState.registeredAt = registration.created_at;
    configState.backendEndpoint = normalizeBackendEndpoint(
      registration.endpoint || configState.backendEndpoint
    );
    analyticsState.backend.healthy = true;
    analyticsState.backend.lastError = null;
    analyticsState.backend.lastSyncAt = new Date().toISOString();
    syncBackendMetadata();
    await persistState();
    await pushStatsUpdate();
    return { ok: true, config: await getConfigSnapshot() };
  } catch (error) {
    analyticsState.backend.healthy = false;
    analyticsState.backend.lastError = String(error);
    await persistState();
    await pushStatsUpdate();
    return { ok: false, error: String(error), config: await getConfigSnapshot() };
  }
}

async function pushStatsUpdate() {
  try {
    const payload = await getPublicStats();
    await chrome.runtime.sendMessage({
      type: "STATS_UPDATED",
      payload,
    });
  } catch (error) {
    // The popup is often closed, so there may be no active listener.
  }
}

async function sendEventToBackend(event) {
  const now = Date.now();
  if (now < backendBackoffUntil) {
    return;
  }

  if (!configState.installToken || !configState.installId) {
    analyticsState.backend.registered = false;
    analyticsState.backend.lastError = "Install not registered. Open setup to connect.";
    await persistState();
    return;
  }

  const endpoint = configState.backendEndpoint;

  try {
    const response = await fetch(`${endpoint}/track-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-PhantomWall-Install-Token": configState.installToken,
      },
      body: JSON.stringify(event),
    });

    if (!response.ok) {
      throw new Error(`Backend responded with ${response.status}`);
    }

    analyticsState.backend.healthy = true;
    analyticsState.backend.lastSyncAt = new Date().toISOString();
    analyticsState.backend.lastError = null;
    analyticsState.backend.registered = true;
    await persistState();
    await pushStatsUpdate();
  } catch (error) {
    analyticsState.backend.healthy = false;
    analyticsState.backend.lastError = String(error);
    backendBackoffUntil = now + BACKEND_FAILURE_BACKOFF_MS;
    await persistState();
    await pushStatsUpdate();
  }
}

function normalizeBackendEndpoint(endpoint) {
  const candidate = String(endpoint || DEFAULT_BACKEND_ENDPOINT).trim();
  return candidate.replace(/\/+$/, "");
}

async function safeJson(response) {
  try {
    return await response.json();
  } catch (error) {
    return null;
  }
}

function matchTrackerDomain(url) {
  try {
    const requestUrl = new URL(url);
    const requestHost = requestUrl.hostname.toLowerCase();
    const requestPath = requestUrl.pathname.toLowerCase();

    for (const tracker of trackerMatchers) {
      if (
        requestHost === tracker.domain ||
        requestHost.endsWith(`.${tracker.domain}`)
      ) {
        if (!tracker.pathPrefix || requestPath.startsWith(tracker.pathPrefix)) {
          return tracker.domain;
        }
      }
    }
    return null;
  } catch (error) {
    return null;
  }
}

function isThirdPartyRequest(pageUrl, requestUrl) {
  try {
    const pageHost = new URL(pageUrl).hostname;
    const requestHost = new URL(requestUrl).hostname;
    return getBaseDomain(pageHost) !== getBaseDomain(requestHost);
  } catch (error) {
    return false;
  }
}

function getBaseDomain(hostname) {
  if (!hostname || hostname === "localhost" || /^\d+\.\d+\.\d+\.\d+$/.test(hostname)) {
    return hostname;
  }

  const segments = hostname.split(".");
  if (segments.length <= 2) {
    return hostname;
  }

  const last = segments.at(-1);
  const secondLast = segments.at(-2);
  const thirdLast = segments.at(-3);

  if (last.length === 2 && secondLast.length <= 3 && thirdLast) {
    return `${thirdLast}.${secondLast}.${last}`;
  }

  return `${secondLast}.${last}`;
}

function buildTrackerMatcher(urlFilter) {
  if (typeof urlFilter !== "string") {
    return null;
  }

  const match = urlFilter.match(/^\|\|([^/^]+)(\/[^^]*)?/);
  if (!match) {
    return null;
  }

  return {
    domain: match[1].toLowerCase(),
    pathPrefix: match[2] ? match[2].toLowerCase() : null,
  };
}
