import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_executable(path: Path, source: str) -> None:
    path.write_text(textwrap.dedent(source).lstrip(), encoding="utf-8")
    path.chmod(0o755)


class AnalyzeCommandTest(unittest.TestCase):
    def test_analyze_creates_an_ai_readable_context_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source_video = workspace / "login failure.mp4"
            source_video.write_bytes(b"original-video")

            fake_ffprobe = workspace / "ffprobe"
            make_executable(
                fake_ffprobe,
                """
                #!/usr/bin/env python3
                import json
                print(json.dumps({
                    "format": {"duration": "12.0", "format_name": "mov,mp4"},
                    "streams": [
                        {
                            "codec_type": "video",
                            "codec_name": "h264",
                            "width": 1280,
                            "height": 720,
                            "avg_frame_rate": "30/1",
                            "duration": "12.0"
                        },
                        {"codec_type": "audio", "codec_name": "aac"}
                    ]
                }))
                """,
            )

            fake_ffmpeg = workspace / "ffmpeg"
            make_executable(
                fake_ffmpeg,
                """
                #!/usr/bin/env python3
                from pathlib import Path
                import sys
                output = Path(sys.argv[-1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"fake-jpeg")
                """,
            )

            environment = os.environ.copy()
            environment["V2CTX_FFPROBE"] = str(fake_ffprobe)
            environment["V2CTX_FFMPEG"] = str(fake_ffmpeg)
            output_root = workspace / "contexts"

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "video_to_context",
                    "analyze",
                    str(source_video),
                    "--output",
                    str(output_root),
                    "--interval",
                    "4",
                    "--max-frames",
                    "3",
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
            bundle = Path(command_output["bundle_path"])
            manifest = json.loads((bundle / "manifest.json").read_text())

            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["video"]["duration_seconds"], 12.0)
            self.assertEqual(manifest["video"]["width"], 1280)
            self.assertEqual(manifest["video"]["height"], 720)
            self.assertEqual(manifest["video"]["fps"], 30.0)
            self.assertTrue(manifest["video"]["has_audio"])
            self.assertEqual(len(manifest["overview"]["frames"]), 3)
            self.assertTrue((bundle / manifest["overview"]["contact_sheet"]).is_file())
            self.assertTrue((bundle / "report.md").is_file())
            for frame in manifest["overview"]["frames"]:
                self.assertFalse(Path(frame["path"]).is_absolute())
                self.assertTrue((bundle / frame["path"]).is_file())
            self.assertEqual(source_video.read_bytes(), b"original-video")


if __name__ == "__main__":
    unittest.main()
