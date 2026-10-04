"""Tintable SVG icons.

Icons are stored once as ``currentColor`` SVGs and rasterised on demand in the colour
and size requested, so they follow the active theme.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from omni_download_manager.utils.system import resource_dir

_cache: dict[tuple[str, str, int, float], QPixmap] = {}


@lru_cache(maxsize=None)
def _svg_source(name: str) -> str:
    return (resource_dir() / "icons" / f"{name}.svg").read_text(encoding="utf-8")


def icon_pixmap(name: str, color: str | QColor, size: int, dpr: float = 1.0) -> QPixmap:
    tint = QColor(color).name()
    key = (name, tint, size, dpr)
    cached = _cache.get(key)
    if cached is not None:
        return cached

    renderer = QSvgRenderer(QByteArray(_svg_source(name).replace("currentColor", tint).encode("utf-8")))
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
    painter.end()
    pixmap.setDevicePixelRatio(dpr)
    _cache[key] = pixmap
    return pixmap


def make_icon(name: str, color: str | QColor, size: int = 20) -> QIcon:
    return QIcon(icon_pixmap(name, color, size, dpr=2.0))


def logo_icon() -> QIcon:
    return QIcon(str(resource_dir() / "app.png"))
