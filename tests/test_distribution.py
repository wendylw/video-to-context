import json
from pathlib import Path
import subprocess
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class DistributionTest(unittest.TestCase):
    def test_cli_reports_its_version(self) -> None:
        result = subprocess.run(
            [str(PROJECT_ROOT / "v2ctx"), "--version"],
            cwd=PROJECT_ROOT.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "v2ctx 0.1.0")

    def test_cli_launcher_runs_from_outside_the_repository(self) -> None:
        result = subprocess.run(
            [str(PROJECT_ROOT / "v2ctx"), "--help"],
            cwd=PROJECT_ROOT.parent,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Turn video into timestamped context", result.stdout)

    def test_native_manifests_all_declare_video_to_context(self) -> None:
        manifest_paths = [
            PROJECT_ROOT / ".codex-plugin" / "plugin.json",
            PROJECT_ROOT / ".claude-plugin" / "plugin.json",
            PROJECT_ROOT / "kimi.plugin.json",
            PROJECT_ROOT / "gemini-extension.json",
        ]

        manifests = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
        self.assertEqual([item["name"] for item in manifests], ["video-to-context"] * 4)
        self.assertEqual([item["version"] for item in manifests], ["0.1.0"] * 4)


if __name__ == "__main__":
    unittest.main()
