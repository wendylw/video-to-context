import argparse
import json
from pathlib import Path
import sys
from typing import List, Optional

from . import __version__
from .core import (
    DEFAULT_INSPECT_FPS,
    DEFAULT_MAX_INSPECTION_FRAMES,
    DEFAULT_PRESET,
    PRESETS,
    VideoContextError,
    analyze_video,
    default_output_root,
    extract_video_frame,
    get_video_overview,
    inspect_video_range,
    parse_timestamp,
)
from .media import MediaToolError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="v2ctx", description="Turn video into timestamped context for AI agents."
    )
    parser.add_argument("--version", action="version", version=f"v2ctx {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)

    analyze = subcommands.add_parser("analyze", help="create a context bundle")
    analyze.add_argument("video", type=Path)
    analyze.add_argument("--output", type=Path, help="bundle root")
    analyze.add_argument("--preset", choices=sorted(PRESETS), default=DEFAULT_PRESET)
    analyze.add_argument("--interval", type=float)
    analyze.add_argument("--max-frames", type=int)
    analyze.add_argument("--json", action="store_true", help="print machine-readable output")

    overview = subcommands.add_parser("overview", help="print an existing bundle report")
    overview.add_argument("bundle", type=Path)
    overview.add_argument("--json", action="store_true", help="print machine-readable output")

    inspect = subcommands.add_parser("inspect", help="sample one time range densely")
    inspect.add_argument("bundle", type=Path)
    inspect.add_argument("--from", dest="start", required=True)
    inspect.add_argument("--to", dest="end", required=True)
    inspect.add_argument("--fps", type=float, default=DEFAULT_INSPECT_FPS)
    inspect.add_argument(
        "--max-frames", type=int, default=DEFAULT_MAX_INSPECTION_FRAMES
    )
    inspect.add_argument("--json", action="store_true", help="print machine-readable output")

    frame = subcommands.add_parser("frame", help="extract one exact video frame")
    frame.add_argument("bundle", type=Path)
    frame.add_argument("--at", required=True, dest="timestamp")
    frame.add_argument("--json", action="store_true", help="print machine-readable output")
    return parser


def main(arguments: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(arguments)
    try:
        if args.command == "analyze":
            result = analyze_video(
                args.video,
                args.output or default_output_root(args.video),
                preset=args.preset,
                interval=args.interval,
                max_frames=args.max_frames,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"Context bundle: {result['bundle_path']}")
                print(f"Report: {result['report_path']}")
            return 0
        if args.command == "overview":
            result = get_video_overview(args.bundle)
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(result["report"], end="")
            return 0
        if args.command == "inspect":
            result = inspect_video_range(
                args.bundle,
                parse_timestamp(args.start),
                parse_timestamp(args.end),
                args.fps,
                max_frames=args.max_frames,
            )
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"Inspection: {result['inspection_id']}")
                print(f"Frames: {result['frame_count']}")
            return 0
        if args.command == "frame":
            result = extract_video_frame(args.bundle, parse_timestamp(args.timestamp))
            if args.json:
                print(json.dumps(result, ensure_ascii=False))
            else:
                print(f"Frame: {result['frame_path']}")
            return 0
    except (VideoContextError, MediaToolError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    parser.error("unknown command")
    return 2
