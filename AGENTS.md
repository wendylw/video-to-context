# AGENTS.md

Instructions for AI coding assistants working on Video to Context.

## Project purpose

`video-to-context` converts local videos into timestamped context bundles that
AI agents can inspect progressively. It is a video preprocessor, not a video
editor, archive, OCR engine, or transcription service.

## Structure

- `video_to_context/core.py` — context-bundle domain operations
- `video_to_context/media.py` — `ffmpeg` and `ffprobe` process boundary
- `video_to_context/cli.py` — `v2ctx` command-line adapter
- `video_to_context/mcp_server.py` — dependency-free stdio MCP adapter
- `v2ctx` / `v2ctx-mcp` — self-locating launchers
- `skills/video-to-context/` — shared Agent Skill
- `.codex-plugin/`, `.claude-plugin/`, `kimi.plugin.json`, and
  `gemini-extension.json` — host-specific packaging
- `SPEC.md` — v0.1 behavioral contract

## Constraints

- Support Python 3.9 and use only the Python standard library at runtime.
- Treat `ffmpeg` and `ffprobe` as explicit external executables.
- Never upload videos or generated frames.
- Never modify or delete a source video.
- Keep generated artifact paths relative inside `manifest.json`; source paths
  may remain absolute so later inspection can reopen the original video.
- Preserve progressive disclosure: overview first, then a narrow inspected
  range, then an exact frame.
- Do not claim OCR or speech transcription exists until it is implemented and
  validated against real input.
- Video files and generated bundles may contain private material and must not be
  committed.

## Verification

Run the full standard-library suite:

```bash
python3 -m unittest discover -s tests -v
```

For media changes, also generate a synthetic video under `/private/tmp` with
real `ffmpeg`, run all four CLI commands, and inspect the contact sheet.

Validate packaging changes with:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py skills/video-to-context
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
claude plugin validate .
gemini extensions validate .
```
