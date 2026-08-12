import os
from pathlib import Path
import subprocess
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class InstallationTest(unittest.TestCase):
    def test_install_and_uninstall_round_trip_in_a_selected_bin_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            bin_dir = workspace / "bin"
            environment = self._environment_with_fake_media_tools(workspace)
            environment.pop("HOME", None)

            install = subprocess.run(
                [str(PROJECT_ROOT / "install.sh"), "--bin-dir", str(bin_dir)],
                cwd=workspace,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(install.returncode, 0, install.stderr)
            self.assertEqual((bin_dir / "v2ctx").resolve(), PROJECT_ROOT / "v2ctx")
            self.assertEqual((bin_dir / "v2ctx-mcp").resolve(), PROJECT_ROOT / "v2ctx-mcp")
            version = subprocess.run(
                [str(bin_dir / "v2ctx"), "--version"],
                cwd=workspace,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(version.returncode, 0, version.stderr)
            self.assertEqual(version.stdout.strip(), "v2ctx 0.1.0")

            uninstall = subprocess.run(
                [str(PROJECT_ROOT / "uninstall.sh"), "--bin-dir", str(bin_dir)],
                cwd=workspace,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            self.assertFalse((bin_dir / "v2ctx").exists())
            self.assertFalse((bin_dir / "v2ctx-mcp").exists())
            self.assertTrue((PROJECT_ROOT / "v2ctx").is_file())
            self.assertTrue((PROJECT_ROOT / "v2ctx-mcp").is_file())

    def test_help_does_not_require_a_home_directory(self) -> None:
        environment = os.environ.copy()
        environment.pop("HOME", None)

        for script_name in ("install.sh", "uninstall.sh"):
            result = subprocess.run(
                [str(PROJECT_ROOT / script_name), "--help"],
                cwd=PROJECT_ROOT.parent,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--bin-dir PATH", result.stdout)

    def test_install_refuses_to_overwrite_an_unrelated_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            bin_dir = workspace / "bin"
            bin_dir.mkdir()
            existing_command = bin_dir / "v2ctx"
            existing_command.write_text("user-owned\n", encoding="utf-8")
            environment = self._environment_with_fake_media_tools(workspace)

            install = subprocess.run(
                [str(PROJECT_ROOT / "install.sh"), "--bin-dir", str(bin_dir)],
                cwd=workspace,
                env=environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )

            self.assertNotEqual(install.returncode, 0)
            self.assertIn("refusing to overwrite unrelated path", install.stderr)
            self.assertEqual(existing_command.read_text(encoding="utf-8"), "user-owned\n")
            self.assertFalse((bin_dir / "v2ctx-mcp").exists())

    @staticmethod
    def _environment_with_fake_media_tools(workspace: Path) -> dict:
        fake_tool = workspace / "media-tool"
        fake_tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_tool.chmod(0o755)
        environment = os.environ.copy()
        environment.update(
            {
                "V2CTX_FFMPEG": str(fake_tool),
                "V2CTX_FFPROBE": str(fake_tool),
            }
        )
        return environment


if __name__ == "__main__":
    unittest.main()
