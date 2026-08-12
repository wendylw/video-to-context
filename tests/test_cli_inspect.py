import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InspectCommandTest(unittest.TestCase):
    def test_inspect_adds_dense_timestamped_frames_to_the_bundle(self) -> None:
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
                "preset": "ui-debug",
                "source": {
                    "path": str(source_video),
                    "name": source_video.name,
                    "size_bytes": 5,
                    "mtime_ns": 1,
                },
                "video": {
                    "duration_seconds": 10.0,
                    "width": 800,
                    "height": 600,
                    "fps": 30.0,
                    "video_codec": "h264",
                    "audio_codec": None,
                    "has_audio": False,
                    "format": "mov,mp4",
                },
                "overview": {
                    "interval_seconds": 2.0,
                    "max_frames": 1,
                    "contact_sheet": "contact-sheet.jpg",
                    "frames": [],
                },
                "inspections": [],
                "detail_frames": [],
            }
            (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (bundle / "report.md").write_text("# Video Context\n", encoding="utf-8")

            fake_ffmpeg = workspace / "ffmpeg"
            fake_ffmpeg.write_text(
                textwrap.dedent(
                    """
                    #!/usr/bin/env python3
                    from pathlib import Path
                    import sys
                    output = Path(sys.argv[-1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"dense-frame")
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
                    "inspect",
                    str(bundle),
                    "--from",
                    "00:00:02.000",
                    "--to",
                    "00:00:03.000",
                    "--fps",
                    "2",
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
            inspection = updated_manifest["inspections"][0]
            self.assertEqual(command_output["frame_count"], 2)
            self.assertEqual(
                command_output["contact_sheet"],
                inspection["contact_sheet"],
            )
            self.assertTrue((bundle / inspection["contact_sheet"]).is_file())
            self.assertEqual(inspection["start_seconds"], 2.0)
            self.assertEqual(inspection["end_seconds"], 3.0)
            self.assertEqual(
                [frame["timestamp_seconds"] for frame in inspection["frames"]],
                [2.0, 2.5],
            )
            for frame in inspection["frames"]:
                self.assertFalse(Path(frame["path"]).is_absolute())
                self.assertTrue((bundle / frame["path"]).is_file())


if __name__ == "__main__":
    unittest.main()
