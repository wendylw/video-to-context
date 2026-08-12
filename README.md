# Video to Context

把本地视频转换成带时间戳、可供 AI 渐进读取的 Context Bundle。适合分析产品录屏、定位短暂报错，以及给无法直接观看视频的模型提供可验证的视觉证据。

视频和抽取出的画面默认只在本机处理，不会上传。

## 当前能力

- 读取时长、分辨率、帧率、编解码器和音频轨信息
- 按时间分布抽取概览帧并生成 contact sheet
- 对可疑时间段进行高密度抽帧
- 精确提取某个时间点的单帧
- 生成可搬移的 `manifest.json` 和 `report.md`
- 同时提供 CLI、MCP Server、Agent Skill，以及 Codex、Claude Code、Kimi Code、Gemini CLI 的插件清单

v0.1 暂不包含 OCR 和语音转录；输出中不会假装已经识别画面文字或音频内容。

## 运行要求

- macOS 或 Linux
- Python 3.9 或更新版本，仅使用标准库
- `ffmpeg` 与 `ffprobe`

macOS 可以使用 Homebrew 安装媒体工具：

```bash
brew install ffmpeg
```

## CLI

无需安装 Python 包，直接从仓库运行：

```bash
./v2ctx analyze ~/Downloads/login-bug.mp4 --preset ui-debug
```

如果希望在任意目录直接使用 `v2ctx`，可以把两个自定位入口链接到已在
`PATH` 中的目录：

```bash
ln -s /absolute/path/to/video-to-context/v2ctx ~/.local/bin/v2ctx
ln -s /absolute/path/to/video-to-context/v2ctx-mcp ~/.local/bin/v2ctx-mcp
```

默认在源视频旁的 `video-context/` 下创建 Context Bundle；也可以用
`--output` 指定其他目录。常用命令：

```bash
./v2ctx analyze recording.mp4 --preset general --json
./v2ctx overview video-context/recording-<id>
./v2ctx inspect video-context/recording-<id> \
  --from 00:01:20 --to 00:01:35 --fps 2 --json
./v2ctx frame video-context/recording-<id> --at 00:01:27.500 --json
```

`ui-debug` 比 `general` 抽帧更密。`inspect` 默认最多生成 120 帧，避免一次把过多图片塞给模型。

## Context Bundle

```text
recording-<analysis-id>/
├── manifest.json
├── report.md
├── contact-sheet.jpg
├── frames/
│   ├── overview-001-00-00-00.000.jpg
│   └── detail-00-01-27.500.jpg
└── inspections/
    └── 00-01-20.000_to_00-01-35.000_2fps/
        ├── contact-sheet.jpg
        └── frame-001-00-01-20.000.jpg
```

清单里的产物路径都是相对路径，因此整个目录可以作为一个单元移动。

## MCP 与插件

MCP Server 使用 stdio：

```bash
./v2ctx-mcp
```

它提供四个工具：

- `analyze_video`
- `get_video_overview`
- `inspect_time_range`
- `get_frame`

仓库同时包含各宿主的原生入口：

- Codex：`.codex-plugin/plugin.json` 和 `.mcp.json`
- Claude Code：`.claude-plugin/plugin.json`、`.mcp.json` 和 `skills/`
- Kimi Code：`kimi.plugin.json`
- Gemini CLI：`gemini-extension.json` 和 `GEMINI.md`

Codex 若暂时不通过 Plugin Marketplace 安装，可以直接注册 MCP 入口：

```bash
codex mcp add video-to-context -- /absolute/path/to/video-to-context/v2ctx-mcp
```

本地开发时可这样加载：

```bash
claude --plugin-dir /absolute/path/to/video-to-context
```

在 Kimi Code 内执行：

```text
/plugins install /absolute/path/to/video-to-context
/reload
```

Gemini CLI 使用本地链接：

```bash
gemini extensions link /absolute/path/to/video-to-context
```

也可以在任何支持 stdio MCP 的宿主中，把命令直接配置成 `/absolute/path/to/video-to-context/v2ctx-mcp`。

## AI 推荐工作流

```text
analyze_video
  → 查看 report + contact sheet
  → 定位可疑时间段
  → inspect_time_range
  → 必要时 get_frame
  → 用时间戳区分观察结果与推断
```

这种渐进方式可以控制图片数量，也不依赖底层模型必须原生支持视频。

## 测试

```bash
python3 -m unittest discover -s tests -v
```

项目采用 MIT License。
