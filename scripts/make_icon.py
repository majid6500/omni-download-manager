"""Copy the root application icons into the bundled application resources.

Run: python scripts/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

import shutil


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    resources = root / "omni_download_manager" / "resources"
    assets = (
        (root / "icon.ico", resources / "app.ico", b"\x00\x00\x01\x00"),
        (root / "icon.png", resources / "app.png", b"\x89PNG\r\n\x1a\n"),
    )
    for source, target, signature in assets:
        data = source.read_bytes()
        if not data.startswith(signature):
            raise ValueError(f"Not a valid icon file: {source}")
        shutil.copyfile(source, target)
        print(f"Copied {source} to {target} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
