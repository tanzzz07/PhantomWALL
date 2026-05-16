const formElement = document.getElementById("setup-form");
const backendEndpointElement = document.getElementById("backend-endpoint");
const displayNameElement = document.getElementById("display-name");
const inviteCodeElement = document.getElementById("invite-code");
const registerButtonElement = document.getElementById("register-button");
const feedbackElement = document.getElementById("form-feedback");
const healthPillElement = document.getElementById("health-pill");
const statusCopyElement = document.getElementById("status-copy");
const installIdElement = document.getElementById("install-id");
const registeredAtElement = document.getElementById("registered-at");
const extensionVersionElement = document.getElementById("extension-version");

document.addEventListener("DOMContentLoaded", async () => {
  formElement.addEventListener("submit", handleSave);
  registerButtonElement.addEventListener("click", handleRegister);
  await loadConfig();
});

async function loadConfig() {
  const config = await chrome.runtime.sendMessage({ type: "GET_CONFIG" });
  renderConfig(config);
}

async function handleSave(event) {
  event.preventDefault();
  feedbackElement.textContent = "";

  const response = await chrome.runtime.sendMessage({
    type: "SAVE_CONFIG",
    payload: getPayload(),
  });

  if (response?.ok) {
    feedbackElement.textContent = "Settings saved locally.";
    renderConfig(response.config);
  }
}

async function handleRegister() {
  feedbackElement.textContent = "Registering install...";
  const response = await chrome.runtime.sendMessage({
    type: "REGISTER_INSTALL",
    payload: getPayload(),
  });

  if (response?.ok) {
    feedbackElement.textContent = "Install registered successfully.";
    renderConfig(response.config);
  } else {
    feedbackElement.textContent = response?.error || "Registration failed.";
    if (response?.config) {
      renderConfig(response.config);
    }
  }
}

function getPayload() {
  return {
    backendEndpoint: backendEndpointElement.value.trim(),
    displayName: displayNameElement.value.trim(),
    inviteCode: inviteCodeElement.value.trim(),
  };
}

function renderConfig(config) {
  backendEndpointElement.value = config.backendEndpoint || "";
  displayNameElement.value = config.displayName || "";
  inviteCodeElement.value = config.inviteCode || "";
  extensionVersionElement.textContent = config.extensionVersion || "Unknown";
  installIdElement.textContent = config.installId || "Not registered";
  registeredAtElement.textContent = config.registeredAt
    ? formatTimestamp(config.registeredAt)
    : "Pending";

  const isRegistered = Boolean(config.isRegistered);
  healthPillElement.textContent = isRegistered ? "Connected" : "Not connected";
  healthPillElement.className = `status-pill ${isRegistered ? "online" : "offline"}`;
  statusCopyElement.textContent = isRegistered
    ? config.backendHealthy
      ? "Telemetry can reach the shared backend."
      : "Registered, but backend sync is currently offline."
    : config.lastError || "Complete setup and register this install.";
}

function formatTimestamp(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }

  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

