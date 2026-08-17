"""Dependency-free MCP stdio adapter for Video to Context."""

import base64
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

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


LEGACY_PROTOCOL_VERSIONS = {
    "2024-11-05",
    "2025-03-26",
    "2025-06-18",
    "2025-11-25",
}
DEFAULT_PROTOCOL_VERSION = "2025-11-25"
MODERN_PROTOCOL_VERSION = "2026-07-28"
SERVER_INSTRUCTIONS = (
    "Use these tools automatically when a user provides or references a local "
    "video or screen recording and asks to watch, inspect, debug, summarize, "
    "compare, or locate a moment, even if they do not name a tool. Call "
    "analyze_video first, read get_video_overview, then inspect only suspicious "
    "ranges or exact frames to control context size."
)


TOOLS = [
    {
        "name": "analyze_video",
        "title": "Analyze local video",
        "description": (
            "Use automatically as the first step when a user provides or references "
            "a local video or screen recording and asks to watch, inspect, debug, "
            "summarize, compare, or locate a moment, even when they do not name this "
            "tool. Create a local AI-readable context bundle with video metadata, "
            "timestamped overview frames, a contact sheet, and a Markdown report."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local video file path."},
                "output": {
                    "type": "string",
                    "description": "Optional directory in which to create the bundle.",
                },
                "preset": {
                    "type": "string",
                    "enum": sorted(PRESETS),
                    "default": DEFAULT_PRESET,
                },
                "interval": {"type": "number", "exclusiveMinimum": 0},
                "max_frames": {"type": "integer", "minimum": 1},
            },
            "required": ["path"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_video_overview",
        "title": "Read video overview",
        "description": (
            "Read an existing context bundle's Markdown report and return its "
            "overview contact sheet for visual inspection."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "bundle": {"type": "string", "description": "Context bundle path."}
            },
            "required": ["bundle"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False},
    },
    {
        "name": "inspect_time_range",
        "title": "Inspect video time range",
        "description": (
            "Extract denser timestamped frames from a suspicious range in an "
            "existing context bundle. Use after reading the overview."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "bundle": {"type": "string"},
                "start": {
                    "type": ["number", "string"],
                    "description": "Start in seconds or HH:MM:SS.mmm.",
                },
                "end": {
                    "type": ["number", "string"],
                    "description": "End in seconds or HH:MM:SS.mmm.",
                },
                "fps": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "default": DEFAULT_INSPECT_FPS,
                },
                "max_frames": {
                    "type": "integer",
                    "minimum": 1,
                    "default": DEFAULT_MAX_INSPECTION_FRAMES,
                },
            },
            "required": ["bundle", "start", "end"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": True},
    },
    {
        "name": "get_frame",
        "title": "Get exact video frame",
        "description": (
            "Extract one exact frame from an existing context bundle and return "
            "it as an image with its timestamp and local path."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "bundle": {"type": "string"},
                "timestamp": {
                    "type": ["number", "string"],
                    "description": "Timestamp in seconds or HH:MM:SS.mmm.",
                },
            },
            "required": ["bundle", "timestamp"],
            "additionalProperties": False,
        },
        "annotations": {"destructiveHint": False, "idempotentHint": True},
    },
]


def main(arguments: Optional[List[str]] = None) -> int:
    command_arguments = list(arguments) if arguments is not None else sys.argv[1:]
    if command_arguments == ["--check"]:
        initialize_response = _handle_message(
            {
                "jsonrpc": "2.0",
                "id": "check-initialize",
                "method": "initialize",
                "params": {
                    "protocolVersion": DEFAULT_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "v2ctx-mcp-check", "version": __version__},
                },
            }
        )
        tools_response = _handle_message(
            {
                "jsonrpc": "2.0",
                "id": "check-tools",
                "method": "tools/list",
                "params": {},
            }
        )
        if initialize_response is None or tools_response is None:
            print("MCP self-check failed", file=sys.stderr)
            return 1
        server_info = initialize_response["result"]["serverInfo"]
        print(
            json.dumps(
                {
                    "server": server_info["name"],
                    "version": server_info["version"],
                    "protocol": initialize_response["result"]["protocolVersion"],
                    "tools": [
                        tool["name"] for tool in tools_response["result"]["tools"]
                    ],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if command_arguments:
        print("usage: v2ctx-mcp [--check]", file=sys.stderr)
        return 2

    for line in sys.stdin:
        try:
            message = json.loads(line)
            response = _handle_message(message)
        except json.JSONDecodeError:
            response = _error(None, -32700, "Parse error")
        except Exception as error:  # Keep protocol failures on the JSON-RPC channel.
            response = _error(None, -32603, f"Internal error: {error}")
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


def _handle_message(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    request_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if request_id is None:
        return None
    if method == "server/discover":
        return _result(
            request_id,
            {
                "resultType": "complete",
                "supportedVersions": [MODERN_PROTOCOL_VERSION],
                "capabilities": {"tools": {}},
                "_meta": {
                    "io.modelcontextprotocol/serverInfo": {
                        "name": "video-to-context",
                        "version": __version__,
                    }
                },
                "instructions": SERVER_INSTRUCTIONS,
                "ttlMs": 3_600_000,
                "cacheScope": "public",
            },
        )
    if method == "initialize":
        requested = params.get("protocolVersion")
        protocol_version = (
            requested if requested in LEGACY_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        )
        return _result(
            request_id,
            {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "video-to-context",
                    "title": "Video to Context",
                    "version": __version__,
                    "description": "Turn local video into timestamped context for AI agents.",
                },
                "instructions": SERVER_INSTRUCTIONS,
            },
        )
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(
            request_id,
            {
                "resultType": "complete",
                "tools": TOOLS,
                "ttlMs": 3_600_000,
                "cacheScope": "public",
            },
        )
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            tool_result = _call_tool(tool_name, arguments)
        except (VideoContextError, MediaToolError, OSError, TypeError, ValueError) as error:
            tool_result = {
                "resultType": "complete",
                "content": [{"type": "text", "text": f"Video context error: {error}"}],
                "isError": True,
            }
        return _result(request_id, tool_result)
    return _error(request_id, -32601, f"Method not found: {method}")


def _call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "analyze_video":
        source = Path(_required(arguments, "path"))
        output_value = arguments.get("output")
        output = (
            Path(output_value)
            if output_value
            else default_output_root(source)
        )
        result = analyze_video(
            source,
            output,
            preset=arguments.get("preset", DEFAULT_PRESET),
            interval=arguments.get("interval"),
            max_frames=arguments.get("max_frames"),
        )
        image_path = Path(result["bundle_path"]) / "contact-sheet.jpg"
        return _tool_success(result, [image_path])
    if name == "get_video_overview":
        result = get_video_overview(Path(_required(arguments, "bundle")))
        image_path = Path(result["bundle_path"]) / "contact-sheet.jpg"
        return _tool_success(result, [image_path] if image_path.is_file() else [])
    if name == "inspect_time_range":
        result = inspect_video_range(
            Path(_required(arguments, "bundle")),
            _time_value(_required(arguments, "start")),
            _time_value(_required(arguments, "end")),
            float(arguments.get("fps", DEFAULT_INSPECT_FPS)),
            max_frames=int(
                arguments.get("max_frames", DEFAULT_MAX_INSPECTION_FRAMES)
            ),
        )
        return _tool_success(result, [Path(result["contact_sheet_path"])])
    if name == "get_frame":
        result = extract_video_frame(
            Path(_required(arguments, "bundle")),
            _time_value(_required(arguments, "timestamp")),
        )
        return _tool_success(result, [Path(result["frame_path"])])
    raise VideoContextError(f"unknown tool: {name}")


def _required(arguments: Dict[str, Any], name: str) -> Any:
    if name not in arguments:
        raise VideoContextError(f"missing required argument: {name}")
    return arguments[name]


def _time_value(value: Any) -> float:
    if isinstance(value, bool):
        raise VideoContextError(f"invalid timestamp: {value}")
    if isinstance(value, (int, float)):
        return round(float(value), 3)
    if isinstance(value, str):
        return parse_timestamp(value)
    raise VideoContextError(f"invalid timestamp: {value}")


def _tool_success(data: Dict[str, Any], images: list) -> Dict[str, Any]:
    content = [
        {
            "type": "text",
            "text": json.dumps(data, ensure_ascii=False, indent=2),
        }
    ]
    for path in images:
        if path.is_file():
            content.append(
                {
                    "type": "image",
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                    "mimeType": "image/jpeg",
                }
            )
    return {
        "resultType": "complete",
        "content": content,
        "structuredContent": data,
        "isError": False,
    }


def _result(request_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


if __name__ == "__main__":
    raise SystemExit(main())
