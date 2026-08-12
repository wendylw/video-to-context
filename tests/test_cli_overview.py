from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OverviewCommandTest(unittest.TestCase):
    def test_overview_prints_the_existing_markdown_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "sample-context"
            bundle.mkdir()
            report = "# Video Context\n\nA known overview.\n"
            (bundle / "report.md").write_text(report, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "video_to_context", "overview", str(bundle)],
                cwd=PROJECT_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, report)


if __name__ == "__main__":
    unittest.main()
