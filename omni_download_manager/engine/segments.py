"""Multi-part download planning, paths, and persisted segment state."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from omni_download_manager.constants import (
    DEFAULT_MULTIPART_CONNECTIONS,
    MIN_BYTES_PER_MULTIPART_SEGMENT,
    MIN_FILE_SIZE_FOR_MULTIPART,
    PARTIAL_SUFFIX,
)

logger = logging.getLogger(__name__)

SEGMENT_SUFFIX = ".seg"


@dataclass(frozen=True)
class SegmentSpec:
    index: int
    start: int
    end: int  # inclusive last byte

    @property
    def length(self) -> int:
        return self.end - self.start + 1


@dataclass(frozen=True)
class SegmentProgress:
    index: int
    start: int
    end: int
    downloaded: int

    @property
    def length(self) -> int:
        return self.end - self.start + 1

    @property
    def complete(self) -> bool:
        return self.downloaded >= self.length

    def fill(self) -> float:
        if self.length <= 0:
            return 1.0
        return max(0.0, min(1.0, self.downloaded / self.length))


@dataclass(frozen=True)
class MultiPartResumeState:
    total_bytes: int
    segments: tuple[SegmentProgress, ...]


def plan_segments(total_bytes: int, connection_count: int = DEFAULT_MULTIPART_CONNECTIONS) -> tuple[SegmentSpec, ...]:
    """Split ``total_bytes`` into contiguous non-overlapping ranges, or return empty if unsuitable."""
    if total_bytes < MIN_FILE_SIZE_FOR_MULTIPART:
        return ()
    max_parts = min(connection_count, total_bytes // MIN_BYTES_PER_MULTIPART_SEGMENT)
    if max_parts < 2:
        return ()
    parts = max_parts
    base = total_bytes // parts
    extra = total_bytes % parts
    specs: list[SegmentSpec] = []
    start = 0
    for index in range(parts):
        size = base + (1 if index < extra else 0)
        end = start + size - 1
        specs.append(SegmentSpec(index, start, end))
        start = end + 1
    assert start == total_bytes, (start, total_bytes)
    return tuple(specs)


def segment_file_path(directory: Path, filename: str, index: int) -> Path:
    return directory / f"{filename}{PARTIAL_SUFFIX}{SEGMENT_SUFFIX}{index}"


def list_segment_files(directory: Path, filename: str) -> list[Path]:
    pattern = f"{filename}{PARTIAL_SUFFIX}{SEGMENT_SUFFIX}*"
    paths = sorted(directory.glob(pattern), key=lambda p: int(p.name.rsplit(SEGMENT_SUFFIX, 1)[-1]))
    return paths


def has_segment_files(directory: Path, filename: str) -> bool:
    return bool(list_segment_files(directory, filename))


def remove_segment_files(directory: Path, filename: str) -> None:
    for path in list_segment_files(directory, filename):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Could not delete segment file %s", path, exc_info=True)
    leftovers = list_segment_files(directory, filename)
    if leftovers:
        # Should not happen: callers only clean up once every segment worker has
        # closed its file. Reported so an orphaned *.part.seg* is never silent.
        logger.warning(
            "Segment files left behind for %s: %s",
            filename,
            ", ".join(path.name for path in leftovers),
        )


def segment_downloaded_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def resume_state_from_specs(
    directory: Path, filename: str, total_bytes: int, specs: tuple[SegmentSpec, ...]
) -> MultiPartResumeState:
    segments: list[SegmentProgress] = []
    for spec in specs:
        downloaded = segment_downloaded_bytes(segment_file_path(directory, filename, spec.index))
        if downloaded > spec.length:
            downloaded = spec.length
        segments.append(
            SegmentProgress(spec.index, spec.start, spec.end, downloaded)
        )
    return MultiPartResumeState(total_bytes, tuple(segments))


def encode_multipart_state(state: MultiPartResumeState) -> str:
    payload = {
        "total_bytes": state.total_bytes,
        "segments": [
            {
                "index": s.index,
                "start": s.start,
                "end": s.end,
                "downloaded": s.downloaded,
            }
            for s in state.segments
        ],
    }
    return json.dumps(payload, separators=(",", ":"))


def decode_multipart_state(raw: str | None) -> MultiPartResumeState | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        segments = tuple(
            SegmentProgress(
                int(s["index"]),
                int(s["start"]),
                int(s["end"]),
                int(s["downloaded"]),
            )
            for s in data["segments"]
        )
        return MultiPartResumeState(int(data["total_bytes"]), segments)
    except (TypeError, ValueError, KeyError):
        logger.warning("Unreadable multipart state JSON", exc_info=True)
        return None


def segment_fill_from_state(state: MultiPartResumeState | None) -> tuple[float, ...] | None:
    if state is None or len(state.segments) < 2:
        return None
    return tuple(s.fill() for s in state.segments)


def total_downloaded_from_state(state: MultiPartResumeState) -> int:
    return sum(s.downloaded for s in state.segments)


def merge_segments_to_partial(directory: Path, filename: str, state: MultiPartResumeState) -> Path:
    """Concatenate segment files into ``filename.part`` in order."""
    part_path = directory / (filename + PARTIAL_SUFFIX)
    with open(part_path, "wb") as out:
        for segment in state.segments:
            seg_path = segment_file_path(directory, filename, segment.index)
            with open(seg_path, "rb") as handle:
                while True:
                    chunk = handle.read(256 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
    return part_path
