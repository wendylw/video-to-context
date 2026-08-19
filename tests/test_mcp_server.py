import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class McpServerTest(unittest.TestCase):
    def test_server_supports_stateless_mcp_discovery(self) -> None:
        server = subprocess.Popen(
            [sys.executable, "-m", "video_to_context.mcp_server"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self._stop_server, server)

        response = self._request(
            server,
            {
                "jsonrpc": "2.0",
                "id": "discover",
                "method": "server/discover",
                "params": {
                    "_meta": {
                        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                        "io.modelcontextprotocol/clientInfo": {
                            "name": "test-client",
                            "version": "1.0",
                        },
                        "io.modelcontextprotocol/clientCapabilities": {},
                    }
                },
            },
        )

        result = response["result"]
        self.assertEqual(result["resultType"], "complete")
        self.assertIn("2026-07-28", result["supportedVersions"])
        self.assertEqual(result["capabilities"], {"tools": {}})

    def test_server_exposes_the_four_video_context_tools(self) -> None:
        server = subprocess.Popen(
            [sys.executable, "-m", "video_to_context.mcp_server"],
            cwd=PROJECT_ROOT,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.addCleanup(self._stop_server, server)

        initialize = self._request(
            server,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0"},
                },
            },
        )
        self.assertEqual(initialize["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(initialize["result"]["capabilities"], {"tools": {}})
        self.assertIn("automatically", initialize["result"]["instructions"])
        self.assertIn("local video", initialize["result"]["instructions"])

        self._notify(
            server,
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        )
        tools = self._request(
            server,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        self.assertEqual(
            [tool["name"] for tool in tools["result"]["tools"]],
            [
                "analyze_video",
                "get_video_overview",
                "inspect_time_range",
                "get_frame",
            ],
        )
        analyze_tool = next(
            tool
            for tool in tools["result"]["tools"]
            if tool["name"] == "analyze_video"
        )
        self.assertIn("Use automatically", analyze_tool["description"])
        self.assertIn(
            "even when they do not name this tool", analyze_tool["description"]
        )

    def test_analyze_video_returns_structured_paths_and_a_contact_sheet_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            source_video = workspace / "demo.mp4"
            source_video.write_bytes(b"video")
            fake_ffprobe = workspace / "ffprobe"
            fake_ffprobe.write_text(
                textwrap.dedent(
                    """
                    #!/usr/bin/env python3
                    import json
                    print(json.dumps({
                        "format": {"duration": "5.0", "format_name": "mov,mp4"},
                        "streams": [{
                            "codec_type": "video", "codec_name": "h264",
                            "width": 640, "height": 360,
                            "avg_frame_rate": "24/1", "duration": "5.0"
                        }]
                    }))
                    """
                ).lstrip(),
                encoding="utf-8",
            )
            fake_ffprobe.chmod(0o755)
            fake_ffmpeg = workspace / "ffmpeg"
            fake_ffmpeg.write_text(
                textwrap.dedent(
                    """
                    #!/usr/bin/env python3
                    from pathlib import Path
                    import sys
                    output = Path(sys.argv[-1])
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"fake-jpeg")
                    """
                ).lstrip(),
                encoding="utf-8",
            )
            fake_ffmpeg.chmod(0o755)
            environment = os.environ.copy()
            environment["V2CTX_FFPROBE"] = str(fake_ffprobe)
            environment["V2CTX_FFMPEG"] = str(fake_ffmpeg)

            server = subprocess.Popen(
                [sys.executable, "-m", "video_to_context.mcp_server"],
                cwd=PROJECT_ROOT,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.addCleanup(self._stop_server, server)
            self._request(
                server,
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test-client", "version": "1.0"},
                    },
                },
            )

            response = self._request(
                server,
                {
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "analyze_video",
                        "arguments": {
                            "path": str(source_video),
                            "output": str(workspace / "contexts"),
                            "max_frames": 1,
                        },
                    },
                },
            )

            result = response["result"]
            self.assertFalse(result["isError"])
            self.assertEqual(result["structuredContent"]["overview_frame_count"], 1)
            self.assertEqual([item["type"] for item in result["content"]], ["text", "image"])
            self.assertEqual(result["content"][1]["mimeType"], "image/jpeg")

            inspection_response = self._request(
                server,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "inspect_time_range",
                        "arguments": {
                            "bundle": result["structuredContent"]["bundle_path"],
                            "start": 1,
                            "end": 2,
                            "fps": 2,
                        },
                    },
                },
            )["result"]
            self.assertEqual(inspection_response["structuredContent"]["frame_count"], 2)
            self.assertEqual(
                [item["type"] for item in inspection_response["content"]],
                ["text", "image"],
            )

            overview_response = self._request(
                server,
                {
                    "jsonrpc": "2.0",
                    "id": 4,
                    "method": "tools/call",
                    "params": {
                        "name": "get_video_overview",
                        "arguments": {
                            "bundle": result["structuredContent"]["bundle_path"]
                        },
                    },
                },
            )["result"]
            self.assertIn("# Video Context", overview_response["structuredContent"]["report"])
            self.assertEqual(
                [item["type"] for item in overview_response["content"]],
                ["text", "image"],
            )

            frame_response = self._request(
                server,
                {
                    "jsonrpc": "2.0",
                    "id": 5,
                    "method": "tools/call",
                    "params": {
                        "name": "get_frame",
                        "arguments": {
                            "bundle": result["structuredContent"]["bundle_path"],
                            "timestamp": "00:00:02.250",
                        },
                    },
                },
            )["result"]
            self.assertEqual(
                frame_response["structuredContent"]["frame"]["timestamp_seconds"],
                2.25,
            )
            self.assertEqual(
                [item["type"] for item in frame_response["content"]],
                ["text", "image"],
            )

    def _request(self, server: subprocess.Popen, message: dict) -> dict:
        self._notify(server, message)
        assert server.stdout is not None
        response = server.stdout.readline()
        if not response:
            assert server.stderr is not None
            self.fail(f"MCP server exited without a response: {server.stderr.read()}")
        return json.loads(response)

    def _notify(self, server: subprocess.Popen, message: dict) -> None:
        assert server.stdin is not None
        server.stdin.write(json.dumps(message) + "\n")
        server.stdin.flush()

    @staticmethod
    def _stop_server(server: subprocess.Popen) -> None:
        if server.poll() is None:
            server.terminate()
        server.communicate(timeout=5)


if __name__ == "__main__":
    unittest.main()
