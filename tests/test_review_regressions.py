import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from video_to_context import cli, mcp_server
from video_to_context.core import (
    analyze_video,
    extract_video_frame,
    inspect_video_range,
)


class FakeMediaTools:
    def __init__(self, duration: float) -> None:
        self.duration = duration

    def probe(self, source: Path) -> dict:
        return {
            "format": {"duration": str(self.duration), "format_name": "mov,mp4"},
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 640,
                    "height": 360,
                    "avg_frame_rate": "30/1",
                    "duration": str(self.duration),
                }
            ],
        }

    def extract_frame(self, source: Path, timestamp: float, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-jpeg")

    def create_contact_sheet(self, frames: list, output: Path) -> dict:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-jpeg")
        return {"columns": len(frames), "rows": 1}


class ReviewRegressionTest(unittest.TestCase):
    def test_reanalysis_preserves_inspections_and_detail_frames(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "recording.mp4"
            source.write_bytes(b"video")
            tools = FakeMediaTools(duration=4.0)

            first = analyze_video(source, workspace / "contexts", media_tools=tools)
            bundle = Path(first["bundle_path"])
            inspect_video_range(bundle, 1.0, 2.0, 1.0, media_tools=tools)
            extract_video_frame(bundle, 2.5, media_tools=tools)

            analyze_video(source, workspace / "contexts", media_tools=tools)
            manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(len(manifest["inspections"]), 1)
            self.assertEqual(len(manifest["detail_frames"]), 1)

    def test_ui_debug_is_denser_for_a_short_clip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source = workspace / "short.mp4"
            source.write_bytes(b"video")
            tools = FakeMediaTools(duration=1.5)

            general = analyze_video(
                source, workspace / "general", preset="general", media_tools=tools
            )
            ui_debug = analyze_video(
                source, workspace / "ui", preset="ui-debug", media_tools=tools
            )

            self.assertGreater(
                ui_debug["overview_frame_count"], general["overview_frame_count"]
            )

    def test_cli_and_mcp_share_the_default_output_location(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "recording.mp4"
            source.write_bytes(b"video")
            expected = source.resolve().parent / "video-context"
            fake_result = {
                "bundle_path": str(expected / "recording-id"),
                "report_path": str(expected / "recording-id" / "report.md"),
            }

            with mock.patch.object(cli, "analyze_video", return_value=fake_result) as call:
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(cli.main(["analyze", str(source)]), 0)
                cli_output = call.call_args.args[1]

            with mock.patch.object(
                mcp_server, "analyze_video", return_value=fake_result
            ) as call:
                mcp_server._call_tool("analyze_video", {"path": str(source)})
                mcp_output = call.call_args.args[1]

            self.assertEqual(cli_output, expected)
            self.assertEqual(mcp_output, expected)


if __name__ == "__main__":
    unittest.main()
