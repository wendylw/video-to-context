from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from .media import MediaTools


PRESETS = {
    "general": {"interval": 10.0, "max_frames": 12, "min_frames": 1},
    "ui-debug": {"interval": 2.0, "max_frames": 30, "min_frames": 2},
}
DEFAULT_PRESET = "general"
DEFAULT_INSPECT_FPS = 2.0
DEFAULT_MAX_INSPECTION_FRAMES = 120


class VideoContextError(RuntimeError):
    """Raised when a context bundle cannot be created or read."""


def analyze_video(
    video_path: Path,
    output_root: Path,
    preset: str = DEFAULT_PRESET,
    interval: Optional[float] = None,
    max_frames: Optional[int] = None,
    media_tools: Optional[MediaTools] = None,
) -> Dict[str, Any]:
    """Create a context bundle for one local video and return its summary."""
    source = video_path.expanduser().resolve()
    if not source.is_file():
        raise VideoContextError(f"video does not exist: {source}")
    if preset not in PRESETS:
        raise VideoContextError(f"unknown preset: {preset}")

    selected_interval = interval if interval is not None else PRESETS[preset]["interval"]
    selected_max = max_frames if max_frames is not None else PRESETS[preset]["max_frames"]
    if not math.isfinite(selected_interval) or selected_interval <= 0:
        raise VideoContextError("interval must be greater than zero")
    if selected_max <= 0:
        raise VideoContextError("max-frames must be greater than zero")

    tools = media_tools or MediaTools()
    raw_probe = tools.probe(source)
    video_metadata = _video_metadata(raw_probe)
    duration = video_metadata["duration_seconds"]
    timestamps = _overview_timestamps(
        duration,
        selected_interval,
        selected_max,
        PRESETS[preset]["min_frames"],
    )

    analysis_id = _analysis_id(source)
    source_stem = _safe_name(source.stem) or "video"
    bundle = output_root.expanduser().resolve() / f"{source_stem}-{analysis_id}"
    inspections = []
    detail_frames = []
    if (bundle / "manifest.json").is_file():
        previous_manifest = _read_manifest(bundle)
        if previous_manifest.get("analysis_id") == analysis_id:
            inspections = previous_manifest.get("inspections", [])
            detail_frames = previous_manifest.get("detail_frames", [])
    frames_dir = bundle / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    frame_records = []
    frame_paths = []
    for index, timestamp in enumerate(timestamps, start=1):
        label = format_timestamp(timestamp)
        relative_path = Path("frames") / f"overview-{index:03d}-{label.replace(':', '-')}.jpg"
        absolute_path = bundle / relative_path
        tools.extract_frame(source, timestamp, absolute_path)
        frame_paths.append(absolute_path)
        frame_records.append(_frame_record(timestamp, relative_path))

    contact_sheet = bundle / "contact-sheet.jpg"
    contact_sheet_layout = tools.create_contact_sheet(frame_paths, contact_sheet)

    source_stat = source.stat()
    manifest = {
        "schema_version": 1,
        "analysis_id": analysis_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "preset": preset,
        "source": {
            "path": str(source),
            "name": source.name,
            "size_bytes": source_stat.st_size,
            "mtime_ns": source_stat.st_mtime_ns,
        },
        "video": video_metadata,
        "overview": {
            "interval_seconds": selected_interval,
            "max_frames": selected_max,
            "contact_sheet": "contact-sheet.jpg",
            "contact_sheet_layout": contact_sheet_layout,
            "frames": frame_records,
        },
        "inspections": inspections,
        "detail_frames": detail_frames,
    }
    bundle.mkdir(parents=True, exist_ok=True)
    _persist_manifest(bundle, manifest)

    return {
        "analysis_id": analysis_id,
        "bundle_path": str(bundle),
        "manifest_path": str(bundle / "manifest.json"),
        "report_path": str(bundle / "report.md"),
        "overview_frame_count": len(frame_records),
    }


def get_video_overview(bundle_path: Path) -> Dict[str, Any]:
    """Read the Markdown overview from an existing context bundle."""
    bundle = _resolve_bundle(bundle_path)
    report_path = bundle / "report.md"
    if not report_path.is_file():
        raise VideoContextError(f"bundle report does not exist: {report_path}")
    return {
        "bundle_path": str(bundle),
        "report_path": str(report_path),
        "report": report_path.read_text(encoding="utf-8"),
    }


def inspect_video_range(
    bundle_path: Path,
    start: float,
    end: float,
    fps: float,
    max_frames: int = DEFAULT_MAX_INSPECTION_FRAMES,
    media_tools: Optional[MediaTools] = None,
) -> Dict[str, Any]:
    """Add densely sampled frames for a time range to an existing bundle."""
    bundle = _resolve_bundle(bundle_path)
    manifest = _read_manifest(bundle)
    duration = float(manifest["video"]["duration_seconds"])
    if not all(math.isfinite(value) for value in (start, end, fps, duration)):
        raise VideoContextError("range times, fps, and video duration must be finite")
    if start < 0:
        raise VideoContextError("start time must not be negative")
    if end <= start:
        raise VideoContextError("end time must be greater than start time")
    if end > duration:
        raise VideoContextError(
            f"end time {format_timestamp(end)} exceeds video duration "
            f"{format_timestamp(duration)}"
        )
    if fps <= 0:
        raise VideoContextError("fps must be greater than zero")
    if max_frames <= 0:
        raise VideoContextError("max-frames must be greater than zero")

    frame_count = int(math.ceil((end - start) * fps))
    if frame_count > max_frames:
        raise VideoContextError(
            f"range would create {frame_count} frames; narrow the range, lower fps, "
            f"or increase --max-frames"
        )

    source = Path(manifest["source"]["path"])
    if not source.is_file():
        raise VideoContextError(f"source video no longer exists: {source}")
    tools = media_tools or MediaTools()
    inspection_id = (
        f"{format_timestamp(start).replace(':', '-')}_to_"
        f"{format_timestamp(end).replace(':', '-')}_{_number_slug(fps)}fps"
    )
    relative_directory = Path("inspections") / inspection_id
    frames = []
    for index in range(frame_count):
        timestamp = round(start + index / fps, 3)
        label = format_timestamp(timestamp)
        relative_path = (
            relative_directory / f"frame-{index + 1:03d}-{label.replace(':', '-')}.jpg"
        )
        tools.extract_frame(source, timestamp, bundle / relative_path)
        frames.append(_frame_record(timestamp, relative_path))

    relative_contact_sheet = relative_directory / "contact-sheet.jpg"
    contact_sheet_layout = tools.create_contact_sheet(
        [bundle / frame["path"] for frame in frames], bundle / relative_contact_sheet
    )

    inspection = {
        "id": inspection_id,
        "start_seconds": start,
        "end_seconds": end,
        "fps": fps,
        "contact_sheet": relative_contact_sheet.as_posix(),
        "contact_sheet_layout": contact_sheet_layout,
        "frames": frames,
    }
    existing = [
        item for item in manifest.get("inspections", []) if item.get("id") != inspection_id
    ]
    manifest["inspections"] = existing + [inspection]
    _persist_manifest(bundle, manifest)
    return {
        "analysis_id": manifest["analysis_id"],
        "bundle_path": str(bundle),
        "inspection_id": inspection_id,
        "start_seconds": start,
        "end_seconds": end,
        "fps": fps,
        "frame_count": len(frames),
        "contact_sheet": relative_contact_sheet.as_posix(),
        "contact_sheet_path": str(bundle / relative_contact_sheet),
        "frames": frames,
    }


def extract_video_frame(
    bundle_path: Path,
    timestamp: float,
    media_tools: Optional[MediaTools] = None,
) -> Dict[str, Any]:
    """Extract and record one exact frame in an existing context bundle."""
    bundle = _resolve_bundle(bundle_path)
    manifest = _read_manifest(bundle)
    duration = float(manifest["video"]["duration_seconds"])
    if not math.isfinite(duration):
        raise VideoContextError("bundle contains an invalid video duration")
    if not math.isfinite(timestamp):
        raise VideoContextError(f"invalid timestamp: {timestamp}")
    if timestamp < 0 or timestamp >= duration:
        raise VideoContextError(
            f"timestamp must be between 00:00:00.000 and "
            f"{format_timestamp(duration)} (exclusive)"
        )

    source = Path(manifest["source"]["path"])
    if not source.is_file():
        raise VideoContextError(f"source video no longer exists: {source}")
    label = format_timestamp(timestamp)
    relative_path = Path("frames") / f"detail-{label.replace(':', '-')}.jpg"
    tools = media_tools or MediaTools()
    tools.extract_frame(source, timestamp, bundle / relative_path)
    frame = _frame_record(timestamp, relative_path)
    existing = [
        item
        for item in manifest.get("detail_frames", [])
        if item.get("timestamp_seconds") != timestamp
    ]
    manifest["detail_frames"] = existing + [frame]
    _persist_manifest(bundle, manifest)
    return {
        "analysis_id": manifest["analysis_id"],
        "bundle_path": str(bundle),
        "frame_path": str(bundle / relative_path),
        "frame": frame,
    }


def parse_timestamp(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into seconds."""
    parts = value.strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise VideoContextError(f"invalid timestamp: {value}")
    try:
        numbers = [float(part) for part in parts]
    except ValueError as error:
        raise VideoContextError(f"invalid timestamp: {value}") from error
    if any(not math.isfinite(number) or number < 0 for number in numbers):
        raise VideoContextError(f"invalid timestamp: {value}")
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
    elif len(numbers) == 2:
        hours = 0.0
        minutes, seconds = numbers
    else:
        hours = 0.0
        minutes = 0.0
        seconds = numbers[0]
    if minutes >= 60 or seconds >= 60 and len(numbers) > 1:
        raise VideoContextError(f"invalid timestamp: {value}")
    return round(hours * 3600 + minutes * 60 + seconds, 3)


def format_timestamp(seconds: float) -> str:
    if not math.isfinite(seconds):
        raise VideoContextError(f"invalid timestamp: {seconds}")
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    whole_seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{milliseconds:03d}"


def _analysis_id(source: Path) -> str:
    stat = source.stat()
    identity = f"{source}\0{stat.st_size}\0{stat.st_mtime_ns}".encode("utf-8")
    return hashlib.sha256(identity).hexdigest()[:12]


def _resolve_bundle(bundle_path: Path) -> Path:
    candidate = bundle_path.expanduser().resolve()
    if candidate.name in {"manifest.json", "report.md"}:
        candidate = candidate.parent
    if not candidate.is_dir():
        raise VideoContextError(f"context bundle does not exist: {candidate}")
    return candidate


def default_output_root(video_path: Path) -> Path:
    """Return the shared CLI/MCP output location for a source video."""
    return video_path.expanduser().resolve().parent / "video-context"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._").lower()


def _number_slug(value: float) -> str:
    return f"{value:g}".replace(".", "-")


def _frame_record(timestamp: float, relative_path: Path) -> Dict[str, Any]:
    return {
        "timestamp_seconds": timestamp,
        "timestamp": format_timestamp(timestamp),
        "path": relative_path.as_posix(),
    }


def _overview_timestamps(
    duration: float, interval: float, max_frames: int, min_frames: int = 1
) -> List[float]:
    if duration <= 0:
        raise VideoContextError("video duration must be greater than zero")
    count = min(max_frames, max(min_frames, int(math.ceil(duration / interval))))
    last_timestamp = max(0.0, duration - min(0.05, duration / 10))
    if count == 1:
        return [round(last_timestamp / 2, 3)]
    return [round(index * last_timestamp / (count - 1), 3) for index in range(count)]


def _video_metadata(probe: Dict[str, Any]) -> Dict[str, Any]:
    streams = probe.get("streams", [])
    video_stream = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    if video_stream is None:
        raise VideoContextError("input does not contain a video stream")

    duration_value = video_stream.get("duration") or probe.get("format", {}).get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as error:
        raise VideoContextError("ffprobe did not report a valid video duration") from error
    if not math.isfinite(duration):
        raise VideoContextError("ffprobe did not report a finite video duration")

    return {
        "duration_seconds": duration,
        "width": int(video_stream.get("width", 0)),
        "height": int(video_stream.get("height", 0)),
        "fps": _parse_frame_rate(video_stream.get("avg_frame_rate", "0/1")),
        "video_codec": video_stream.get("codec_name"),
        "audio_codec": next(
            (
                stream.get("codec_name")
                for stream in streams
                if stream.get("codec_type") == "audio"
            ),
            None,
        ),
        "has_audio": any(stream.get("codec_type") == "audio" for stream in streams),
        "format": probe.get("format", {}).get("format_name"),
    }


def _parse_frame_rate(value: str) -> float:
    try:
        numerator, denominator = value.split("/", 1)
        if float(denominator) == 0:
            return 0.0
        frame_rate = float(numerator) / float(denominator)
        return round(frame_rate, 3) if math.isfinite(frame_rate) else 0.0
    except (AttributeError, ValueError):
        return 0.0


def _write_json(path: Path, value: Dict[str, Any]) -> None:
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_path.replace(path)


def _persist_manifest(bundle: Path, manifest: Dict[str, Any]) -> None:
    _write_json(bundle / "manifest.json", manifest)
    (bundle / "report.md").write_text(_render_report(manifest), encoding="utf-8")


def _read_manifest(bundle: Path) -> Dict[str, Any]:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise VideoContextError(f"bundle manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise VideoContextError(f"bundle manifest is invalid: {manifest_path}") from error
    if manifest.get("schema_version") != 1:
        raise VideoContextError("unsupported context bundle schema")
    return manifest


def _render_report(manifest: Dict[str, Any]) -> str:
    video = manifest["video"]
    source = manifest["source"]
    lines = [
        "# Video Context",
        "",
        f"- Source: `{source['name']}`",
        f"- Duration: `{format_timestamp(video['duration_seconds'])}`",
        f"- Resolution: `{video['width']}×{video['height']}`",
        f"- Frame rate: `{video['fps']} fps`",
        f"- Audio: `{'yes' if video['has_audio'] else 'no'}`",
        f"- Preset: `{manifest['preset']}`",
        "",
        "## Contact sheet",
        "",
        "![Overview contact sheet](contact-sheet.jpg)",
        "",
        "Cells follow the frame table from left to right, then top to bottom.",
        "",
        "## Overview frames",
        "",
        "| Timestamp | Frame |",
        "| --- | --- |",
    ]
    for frame in manifest["overview"]["frames"]:
        lines.append(f"| `{frame['timestamp']}` | [{frame['path']}]({frame['path']}) |")
    if manifest.get("inspections"):
        lines.extend(["", "## Inspected ranges", ""])
        for inspection in manifest["inspections"]:
            lines.extend(
                [
                    f"### {format_timestamp(inspection['start_seconds'])}–"
                    f"{format_timestamp(inspection['end_seconds'])} at "
                    f"{inspection['fps']:g} fps",
                    "",
                    f"![Inspected range contact sheet]({inspection['contact_sheet']})",
                    "",
                    "Cells follow the frame table from left to right, then top to bottom.",
                    "",
                    "| Timestamp | Frame |",
                    "| --- | --- |",
                ]
            )
            for frame in inspection["frames"]:
                lines.append(
                    f"| `{frame['timestamp']}` | [{frame['path']}]({frame['path']}) |"
                )
    if manifest.get("detail_frames"):
        lines.extend(
            [
                "",
                "## Detail frames",
                "",
                "| Timestamp | Frame |",
                "| --- | --- |",
            ]
        )
        for frame in manifest["detail_frames"]:
            lines.append(f"| `{frame['timestamp']}` | [{frame['path']}]({frame['path']}) |")
    lines.extend(["", "Generated locally by Video to Context.", ""])
    return "\n".join(lines)
