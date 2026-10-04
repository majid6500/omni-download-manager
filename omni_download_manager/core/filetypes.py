"""Coarse file categories, used for presentation only."""

from __future__ import annotations

from enum import Enum
from pathlib import Path


class FileCategory(str, Enum):
    ARCHIVE = "archive"
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    DOCUMENT = "document"
    PROGRAM = "program"
    OTHER = "other"

    @property
    def title(self) -> str:
        return {
            FileCategory.ARCHIVE: "Archives",
            FileCategory.VIDEO: "Videos",
            FileCategory.AUDIO: "Audio",
            FileCategory.IMAGE: "Images",
            FileCategory.DOCUMENT: "Documents",
            FileCategory.PROGRAM: "Programs",
            FileCategory.OTHER: "Other",
        }[self]


_EXTENSIONS: dict[FileCategory, frozenset[str]] = {
    FileCategory.ARCHIVE: frozenset("zip rar 7z tar gz bz2 xz zst iso img cab".split()),
    FileCategory.VIDEO: frozenset("mp4 mkv avi mov wmv flv webm m4v mpg mpeg".split()),
    FileCategory.AUDIO: frozenset("mp3 wav flac aac ogg m4a wma opus".split()),
    FileCategory.IMAGE: frozenset("jpg jpeg png gif bmp webp svg tif tiff ico heic".split()),
    FileCategory.DOCUMENT: frozenset("pdf doc docx xls xlsx ppt pptx txt rtf epub csv md odt".split()),
    FileCategory.PROGRAM: frozenset("exe msi apk dmg deb rpm appx msix bat".split()),
}


def categorize(filename: str) -> FileCategory:
    extension = Path(filename).suffix.lower().lstrip(".")
    for category, extensions in _EXTENSIONS.items():
        if extension in extensions:
            return category
    return FileCategory.OTHER


def badge_label(filename: str) -> str:
    extension = Path(filename).suffix.lstrip(".")
    if not extension or len(extension) > 4:
        return "FILE"
    return extension.upper()
