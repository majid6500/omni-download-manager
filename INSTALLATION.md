# Browser Integration: Installation and Setup Guide

**Application:** Omni Download Manager  
**Version:** 0.3.0  
**Supported browsers:** Google Chrome and Microsoft Edge (Chromium-based)

## Overview

Browser Integration allows you to send download links directly from your browser to Omni Download Manager. Once configured, you can send links through the browser's right-click context menu or the extension's interface.

This guide explains how to install the browser extension, configure communication with the desktop application, and verify that the integration works correctly.

## 1. Prerequisites

Before you begin, make sure you have:

- Omni Download Manager version 0.3.0
- Google Chrome or Microsoft Edge
- The browser extension ZIP archive included with this release

> **Important:** Installing the extension alone is not sufficient. The Native Messaging Host must also be installed and registered correctly for the extension to communicate with the desktop application.

## 2. Installing the Browser Extension

For this release, the extension can be installed manually using the browser's Developer Mode. This method does not require the extension to be published in a browser extension store.

### Google Chrome

1. Open Google Chrome.
2. Navigate to `chrome://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the `browser_extension` directory.

### Microsoft Edge

1. Open Microsoft Edge.
2. Navigate to `edge://extensions`.
3. Enable **Developer mode**.
4. Click **Load unpacked**.
5. Select the `browser_extension` directory.

After installation, the extension should appear in the browser's extension list.

**Note:** If you only have the extension ZIP archive, extract it first. Then select the directory containing `manifest.json` using **Load unpacked**.

## 3. Configuring Desktop Application Communication

The extension uses **Native Messaging** to communicate with Omni Download Manager.

When running the desktop application's installer, you may be asked to provide the extension's ID for each browser you want to register.

### Finding the Extension ID

1. Open the browser's extensions page.
2. Locate the Omni Download Manager extension.
3. Copy its extension ID.
4. Enter the ID in the appropriate field in the application installer.

Chrome and Edge may use different extension IDs. If you use both browsers, provide the correct ID for each browser separately.

If you do not want to configure browser integration during installation, you may leave the relevant field empty. However, browser integration may remain unavailable until the Native Messaging Host is registered correctly.

The installer should register the Native Messaging Host configuration in the appropriate Windows location according to the application's implementation.

## 4. Verifying the Connection

After installing the extension and the desktop application:

1. Launch Omni Download Manager.
2. Open **Settings → Browser Integration**.
3. Check the registration status for the selected browser.
4. Click the extension's icon in the browser.
5. If the extension provides a **Check Host** option, use it to test communication with the native host.

A **Registered** status indicates that the browser registration has been configured. However, you should also perform a test transfer to confirm that the integration works end to end.

## 5. Testing a Download

1. Open a webpage containing a direct download link.
2. Right-click the link.
3. Select **Send to Omni Download Manager**.
4. Return to the desktop application.
5. Verify that the link has been received and added to the download queue.

If the extension supports sending links through its popup interface, you can test that method as well.

## 6. Updating the Extension

To install an updated extension version:

1. Remove the previous extension from the browser's extensions page, or follow the extension's supported update procedure.
2. Extract the new ZIP archive.
3. Load the extension using **Load unpacked**.
4. Verify the connection to the desktop application again.

If the extension ID changes, the Native Messaging Host may need to be registered again with the new ID.

## 7. Troubleshooting

### The extension cannot connect to the desktop application

Check the following:

- Omni Download Manager is installed correctly.
- The correct extension ID was provided during installation.
- The Native Messaging Host is registered for the browser you are using.
- The host configuration points to the correct location and the required executable is available.
- If the host was registered system-wide, the installation was performed with the necessary permissions.

### The extension shows Registered, but links are not sent

- Test the connection using the extension's popup interface.
- Try a direct download link.
- Check whether the **Send to Omni Download Manager** option appears in the right-click context menu.
- If the problem persists, inspect the application's logs and relevant messages in Windows Event Viewer.

### The extension stops working after installing the desktop application

Make sure the extension is installed in the same browser whose extension ID was registered during application setup. If you use multiple browsers, verify each browser's registration separately.

## 8. Additional Notes

- This guide applies to Omni Download Manager version 0.3.0.
- Manual installation through Developer Mode is different from installation through an official browser extension store.
- Publishing the extension through the Chrome Web Store or Microsoft Edge Add-ons requires a separate submission and review process.
- Menu labels and installation steps may vary slightly between browser versions.

---

**Project:** Omni Download Manager  
**Documentation version:** 0.3.0