# Video to Context

Use the `video-to-context` MCP tools for local videos and screen recordings.

1. Call `analyze_video` first. Use `ui-debug` for product recordings and
   `general` for other video.
2. Read `get_video_overview` and inspect its contact sheet before requesting
   more frames.
3. Call `inspect_time_range` only for suspicious intervals. Start at 2 fps and
   narrow the interval before increasing density.
4. Call `get_frame` for one exact moment.

Keep observed evidence separate from inference and cite timestamps. Never claim
that speech or on-screen text was transcribed: v0.1 does not include OCR or
speech-to-text. Processing is local; never upload the source or generated
frames.
