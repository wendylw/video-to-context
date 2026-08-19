---
name: video-to-context
description: Analyze local videos and screen recordings by converting them into timestamped AI-readable context bundles with metadata, contact sheets, and frames. Use automatically when the user provides or references a local MP4, MOV, MKV, or WebM file and asks to watch, inspect, debug, summarize, compare, or locate a moment, even if the user does not name this skill or ask for frame extraction.
---

# Video to Context

Use the MCP tools when available. Keep all processing local and progressively
increase frame density so the model receives only useful visual context.
Do not wait for the user to name this skill when the request matches its
description.

## Workflow

1. Call `analyze_video` with the local video path. Select `ui-debug` for screen
   recordings and `general` otherwise.
2. Call `get_video_overview`. Inspect the report and contact sheet before
   requesting more images.
3. Identify suspicious intervals. Call `inspect_time_range` at 2 fps first;
   narrow the interval before increasing the rate. Keep the frame count within
   the tool limit.
4. Call `get_frame` when one exact timestamp needs closer inspection.
5. Report observations with timestamps. Label causal explanations as inference.

Do not claim that audio or visible text was transcribed. Version 0.1 does not
perform speech-to-text or OCR. If a client cannot display returned images, use
the paths in `structuredContent` and inspect those local files with its image
viewer.

## CLI fallback

If MCP is unavailable, run the equivalent commands:

```bash
v2ctx analyze recording.mp4 --preset ui-debug --json
v2ctx overview /path/to/context-bundle
v2ctx inspect /path/to/context-bundle --from 00:01:20 --to 00:01:35 --fps 2 --json
v2ctx frame /path/to/context-bundle --at 00:01:27.500 --json
```

Never upload the source video or generated frames, and never modify or delete
the source. Write only to the requested context-bundle location.
