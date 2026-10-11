"use strict";

const HOST_NAME = "com.omni_download_manager";
const MENU_ITEMS = [
  {
    id: "odm-download-link",
    title: "Download link with Omni Download Manager",
    contexts: ["link"]
  },
  {
    id: "odm-download-image",
    title: "Download image with Omni Download Manager",
    contexts: ["image"]
  },
  {
    id: "odm-download-video",
    title: "Download video with Omni Download Manager",
    contexts: ["video"]
  },
  {
    id: "odm-download-audio",
    title: "Download audio with Omni Download Manager",
    contexts: ["audio"]
  }
];

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    for (const item of MENU_ITEMS) {
      chrome.contextMenus.create({
        ...item,
        documentUrlPatterns: ["http://*/*", "https://*/*"]
      });
    }
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  const url = info.menuItemId === "odm-download-link"
    ? info.linkUrl
    : (info.srcUrl || info.linkUrl);
  if (!isWebUrl(url)) {
    notify("Unsupported link", "Only direct HTTP and HTTPS links can be sent to ODM.");
    return;
  }

  const request = { action: "download", url };
  const referer = originOf(tab && tab.url);
  if (referer) request.referer = referer;

  const filename = filenameFromUrl(url);
  if (filename) request.filename = filename;

  chrome.runtime.sendNativeMessage(HOST_NAME, request, (response) => {
    const lastError = chrome.runtime.lastError;
    if (lastError) {
      notify("ODM is not connected", "Install the desktop app and its browser integration, then try again.");
      return;
    }
    if (!response || response.ok !== true) {
      notify("Download was not added", (response && response.error) || "The desktop app did not accept the request.");
      return;
    }
    notify("Sent to ODM", response.message || "The download request was accepted.");
  });
});

function isWebUrl(value) {
  if (typeof value !== "string") return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

function originOf(value) {
  if (!isWebUrl(value)) return "";
  return new URL(value).origin + "/";
}

function filenameFromUrl(value) {
  try {
    const path = new URL(value).pathname;
    const last = path.substring(path.lastIndexOf("/") + 1);
    return last ? decodeURIComponent(last) : "";
  } catch {
    return "";
  }
}

function notify(title, message) {
  chrome.notifications.create(`odm-${Date.now()}`, {
    type: "basic",
    title,
    message,
    iconUrl: "icons/odm-128.png"
  });
}
