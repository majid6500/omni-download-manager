"""Read-only status of the installed Chromium Native Messaging registrations."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HOST_NAME = "com.omni_download_manager"
_REGISTRY_KEYS = {
    "Chrome": rf"Software\Google\Chrome\NativeMessagingHosts\{HOST_NAME}",
    "Microsoft Edge": rf"Software\Microsoft\Edge\NativeMessagingHosts\{HOST_NAME}",
}


def registered_browsers() -> dict[str, bool]:
    result = {browser: False for browser in _REGISTRY_KEYS}
    if sys.platform != "win32":
        return result
    import winreg

    for browser, key_path in _REGISTRY_KEYS.items():
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            try:
                with winreg.OpenKey(hive, key_path) as key:
                    manifest = Path(winreg.QueryValueEx(key, None)[0])
                details = json.loads(manifest.read_text(encoding="utf-8"))
                host = Path(details["path"])
                if (
                    details.get("name") == HOST_NAME
                    and details.get("type") == "stdio"
                    and details.get("allowed_origins")
                    and host.is_file()
                ):
                    result[browser] = True
                    break
            except (OSError, ValueError, KeyError, TypeError):
                continue
    return result
