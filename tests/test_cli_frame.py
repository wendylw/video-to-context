import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FrameCommandTest(unittest.TestCase):
    def test_frame_rejects_a_non_finite_timestamp_without_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "context"
            bundle.mkdir()
            source_video = Path(temp_dir) / "video.mp4"
            source_video.write_bytes(b"video")
            (bundle / "manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "video": {"duration_seconds": 10.0},
                        "source": {"path": str(source_video)},
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "video_to_context",
                    "frame",
                    str(bundle),
                    "--at",
                    "nan",
                ],
                cwd=PROJECT_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("invalid timestamp", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_frame_extracts_and_records_one_exact_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source_video = workspace / "bug.mp4"
            source_video.write_bytes(b"video")
            bundle = workspace / "bug-context"
            bundle.mkdir()
            manifest = {
                "schema_version": 1,
                "analysis_id": "known-analysis",
                "created_at": "2026-08-12T00:00:00+00:00",
                "preset": "general",
                "source": {"path": str(source_video), "name": "bug.mp4"},
                "video": {
                    "duration_seconds": 10.0,
                    "width": 800,
                    "height": 600,
                    "fps": 30.0,
                    "has_audio": False,
                },
                "overview": {
                    "interval_seconds": 10.0,
                    "max_frames": 1,
                    "contact_sheet": "contact-sheet.jpg",
                    "frames": [],
                },
                "inspections": [],
                "detail_frames": [],
            }
            (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            fake_ffmpeg = workspace / "ffmpeg"
            fake_ffmpeg.write_text(
                textwrap.dedent(
                    """
                    #!/usr/bin/env python3
                    from pathlib import Path
                    import sys
                    output = Path(sys.argv[-1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"exact-frame")
                    """
                ).lstrip(),
                encoding="utf-8",
            )
            fake_ffmpeg.chmod(0o755)
            environment = os.environ.copy()
            environment["V2CTX_FFMPEG"] = str(fake_ffmpeg)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "video_to_context",
                    "frame",
                    str(bundle),
                    "--at",
                    "00:00:02.250",
                    "--json",
                ],
                cwd=PROJECT_ROOT,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            command_output = json.loads(result.stdout)
            updated_manifest = json.loads((bundle / "manifest.json").read_text())
            recorded_frame = updated_manifest["detail_frames"][0]
            self.assertEqual(recorded_frame["timestamp_seconds"], 2.25)
            self.assertEqual(command_output["frame"], recorded_frame)
            self.assertTrue((bundle / recorded_frame["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
