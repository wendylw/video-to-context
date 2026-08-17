# Video to Context v0.1 specification

## Purpose

Convert a local video into a timestamped, AI-readable context bundle without
uploading the source video.

## Public interfaces

The first release exposes the same capabilities through two public seams:

1. The `v2ctx` command-line interface.
2. The `v2ctx-mcp` stdio MCP server.

Host manifests for Codex, Claude, Gemini, and Kimi package the MCP seam for
native discovery; they do not add separate runtime APIs.

## Required behavior

- `v2ctx analyze VIDEO` probes the video and creates a context bundle containing
  `manifest.json`, `report.md`, an overview contact sheet, and timestamped JPEG
  frames.
- `v2ctx overview BUNDLE` prints the existing Markdown overview.
- `v2ctx inspect BUNDLE --from TIME --to TIME --fps FPS` extracts a denser set
  of frames for one suspicious time range and records them in the manifest.
- `v2ctx frame BUNDLE --at TIME` extracts a single timestamped frame.
- All commands support machine-readable JSON output where applicable.
- The `ui-debug` preset samples more densely than the general preset.
- The MCP server exposes `analyze_video`, `get_video_overview`,
  `inspect_time_range`, and `get_frame` with equivalent behavior.
- Processing is local. The program never uploads video or extracted artifacts.
- Python code supports the macOS system Python 3.9 and uses only the standard
  library. `ffmpeg` and `ffprobe` are explicit external runtime requirements.

## Context bundle

Each analysis directory contains durable relative paths so the bundle can be
moved as a unit. Re-running analysis for unchanged input may reuse the same
bundle; generated files must never overwrite the source video.

## Distribution and installation

- The GitHub repository can be run without a manual clone through `uvx`, and
  exposes both `v2ctx` and `v2ctx-mcp` package entry points.
- The repository exposes a Codex marketplace whose installable plugin bundles
  the Agent Skill and launches the GitHub `v2ctx-mcp` entry point through
  `uvx`; registering the MCP server alone remains an explicit fallback.
- Installed host guidance should route natural requests about a referenced
  local video to the workflow without requiring the user to name the Skill or
  MCP tools.
- `v2ctx-mcp --check` exercises MCP initialization and tool discovery, then
  prints the four available tool names for deterministic installation checks.
- A checkout can install self-locating CLI links into a caller-selected bin
  directory. Installation must refuse to overwrite unrelated files.
- Uninstallation removes only links created for this checkout; it never deletes
  the checkout, videos, context bundles, or unrelated configuration.
- The README gives an AI coding agent a deterministic install, verification,
  update, and uninstall workflow without granting permission to upload media or
  silently change unrelated global configuration.

## Non-goals for v0.1

- Speech-to-text and OCR engines.
- Remote video URLs or cloud uploads.
- Editing, transcoding, or splitting the source video into playable clips.
- A graphical user interface.
