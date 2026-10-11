"use strict";

const checkButton = document.getElementById("check-button");
checkButton.addEventListener("click", checkConnection);
checkConnection();

function checkConnection() {
  const title = document.getElementById("status-title");
  const message = document.getElementById("status-message");
  const dot = document.getElementById("status-dot");
  checkButton.disabled = true;
  title.textContent = "Checking connection…";
  message.textContent = "Contacting the desktop integration.";
  dot.className = "status-dot";

  chrome.runtime.sendNativeMessage(
    "com.omni_download_manager",
    { action: "status" },
    (response) => {
      checkButton.disabled = false;
      const lastError = chrome.runtime.lastError;
      if (lastError || !response || response.ok !== true) {
        title.textContent = "Native host unavailable";
        message.textContent = "Install or repair the desktop app integration, then restart your browser.";
        dot.className = "status-dot offline";
        return;
      }
      if (response.application_running) {
        title.textContent = "Connected";
        message.textContent = "Omni Download Manager is running and ready.";
        dot.className = "status-dot ready";
      } else {
        title.textContent = "Ready when needed";
        message.textContent = "The browser host is installed. The desktop app will start when you send a download.";
        dot.className = "status-dot";
      }
    }
  );
}
