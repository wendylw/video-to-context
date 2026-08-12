import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Dict, List


class MediaToolError(RuntimeError):
    """Raised when ffmpeg or ffprobe cannot complete an operation."""


class MediaTools:
    """Boundary around the external ffmpeg and ffprobe executables."""

    def __init__(self) -> None:
        self.ffmpeg = os.environ.get("V2CTX_FFMPEG", "ffmpeg")
        self.ffprobe = os.environ.get("V2CTX_FFPROBE", "ffprobe")

    def probe(self, video_path: Path) -> Dict[str, Any]:
        result = self._run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(video_path),
            ],
            "ffprobe",
        )
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise MediaToolError("ffprobe returned invalid JSON") from error

    def extract_frame(self, video_path: Path, timestamp: float, output: Path) -> None:
        output.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                self.ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-ss",
                f"{timestamp:.3f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(output),
            ],
            "ffmpeg",
        )

    def create_contact_sheet(self, frames: List[Path], output: Path) -> Dict[str, int]:
        if not frames:
            raise MediaToolError("cannot create a contact sheet without frames")
        columns = int(math.ceil(math.sqrt(len(frames))))
        rows = (len(frames) + columns - 1) // columns
        tile_width = min(480, max(120, (1920 - (columns + 1) * 8) // columns))
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="v2ctx-contact-sheet-") as temp_dir:
            staging = Path(temp_dir)
            for index, frame in enumerate(frames, start=1):
                staged_frame = staging / f"frame-{index:04d}.jpg"
                try:
                    staged_frame.symlink_to(frame.resolve())
                except OSError:
                    shutil.copyfile(frame, staged_frame)
            self._run(
                [
                    self.ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-framerate",
                    "1",
                    "-pattern_type",
                    "glob",
                    "-i",
                    str(staging / "frame-*.jpg"),
                    "-vf",
                    f"scale={tile_width}:-2,tile={columns}x{rows}:padding=8:margin=8",
                    "-frames:v",
                    "1",
                    str(output),
                ],
                "ffmpeg",
            )
        return {"columns": columns, "rows": rows}

    @staticmethod
    def _run(command: List[str], tool_name: str) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
        except FileNotFoundError as error:
            raise MediaToolError(
                f"{tool_name} was not found; install ffmpeg or configure its path"
            ) from error
        if result.returncode != 0:
            detail = result.stderr.strip() or f"exit status {result.returncode}"
            raise MediaToolError(f"{tool_name} failed: {detail}")
        return result
