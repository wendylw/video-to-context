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
- 从 GitHub 安装时需要 `git` 和网络连接

macOS 可以使用 Homebrew 安装媒体工具：

```bash
brew install ffmpeg
```

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install ffmpeg
```

安装后可以检查：

```bash
python3 --version
git --version
ffmpeg -version
ffprobe -version
```

## 最快使用：无需手动下载仓库

如果已经安装 [uv](https://docs.astral.sh/uv/)，可以直接从 GitHub 运行：

```bash
uvx --from git+https://github.com/wendylw/video-to-context \
  v2ctx analyze /absolute/path/to/recording.mp4 --preset ui-debug
```

这不需要 `git clone` 或把项目长期安装到 Python 环境。`uvx` 会在首次运行时
自动下载代码到本机缓存；视频和抽取帧仍只在本机处理。`ffmpeg` / `ffprobe`
依然需要预先安装。

直接注册远程仓库提供的 MCP Server：

```bash
# Codex
codex mcp add video-to-context -- \
  uvx --from git+https://github.com/wendylw/video-to-context v2ctx-mcp

# Claude Code（用户级）
claude mcp add --scope user video-to-context -- \
  uvx --from git+https://github.com/wendylw/video-to-context v2ctx-mcp
```

Gemini CLI 和 Kimi Code 可以直接安装 GitHub 仓库中的原生包装：

```bash
gemini extensions install https://github.com/wendylw/video-to-context
```

在 Kimi Code 会话中执行：

```text
/plugins install https://github.com/wendylw/video-to-context
/reload
```

安装第三方扩展前请自行审阅仓库内容；首次安装时宿主可能要求确认信任。

## 交给 AI 自动安装

把下面这段话原样交给拥有终端与文件权限的 Codex、Claude Code、Gemini CLI
或 Kimi Code：

```text
请阅读 https://github.com/wendylw/video-to-context 的 README。
先确认操作系统、Python >= 3.9、git、ffmpeg、ffprobe、uv，以及当前 AI 宿主。
优先使用 README 的 GitHub + uvx 方式为当前宿主安装 video-to-context；
如果宿主支持 GitHub extension/plugin，则使用对应的原生安装方式。
不要上传任何视频或生成帧，不要覆盖已有 MCP 配置，不要修改无关全局配置。
遇到同名配置或需要安装系统依赖时先征求我的同意。
完成后验证 v2ctx --version，并确认 MCP 能列出 analyze_video、
get_video_overview、inspect_time_range、get_frame 四个工具。
最后汇报执行过的命令、修改的配置和卸载方法。
```

普通网页聊天 AI 没有本机终端权限，只能解释步骤，不能替你完成安装。

## 持久本地安装

需要反复使用或参与开发时，可以保留一个 checkout：

```bash
git clone https://github.com/wendylw/video-to-context.git
cd video-to-context
./install.sh
```

脚本检查 Python、`ffmpeg` 和 `ffprobe`，然后在 `~/.local/bin` 创建两个指向
checkout 的链接；它不会复制视频、修改 AI 客户端配置或覆盖同名文件。若该
目录不在 `PATH`，按脚本提示加入即可。也可以选择安装目录：

```bash
./install.sh --bin-dir /your/bin/directory
```

更新与卸载：

```bash
git pull --ff-only
./uninstall.sh
```

卸载脚本只移除由当前 checkout 创建的命令链接，不删除仓库、视频、Context
Bundle 或 AI 客户端配置。自定义安装目录卸载时需传入同一个 `--bin-dir`。

## CLI

在仓库目录中也可以不运行安装脚本，直接执行：

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

使用本地 checkout 时，Codex 可以直接注册 MCP 入口：

```bash
codex mcp add video-to-context -- /absolute/path/to/video-to-context/v2ctx-mcp
```

Claude Code 本地开发时可这样加载：

```bash
claude --plugin-dir /absolute/path/to/video-to-context
```

Kimi Code 本地开发时执行：

```text
/plugins install /absolute/path/to/video-to-context
/reload
```

Gemini CLI 本地开发时使用链接：

```bash
gemini extensions link /absolute/path/to/video-to-context
```

也可以在任何支持 stdio MCP 的宿主中，把命令直接配置成 `/absolute/path/to/video-to-context/v2ctx-mcp`。

### 验证和卸载宿主配置

```bash
codex mcp list
claude mcp list
gemini extensions list
```

Kimi Code 使用 `/plugins list` 查看状态。正常连接后应能看到四个 MCP 工具：
`analyze_video`、`get_video_overview`、`inspect_time_range`、`get_frame`。

移除免 clone 的宿主配置：

```bash
codex mcp remove video-to-context
claude mcp remove --scope user video-to-context
gemini extensions uninstall video-to-context
```

Kimi Code 使用 `/plugins remove video-to-context`，随后 `/reload`。

刷新 GitHub + `uvx` 缓存到最新代码：

```bash
uvx --refresh --from git+https://github.com/wendylw/video-to-context \
  v2ctx --version
```

Gemini 使用 `gemini extensions update video-to-context`；Kimi Code 再次运行
`/plugins install https://github.com/wendylw/video-to-context` 后 `/reload`。

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

## 常见问题

- `ffmpeg was not found`：先安装 `ffmpeg`，并确认 `ffmpeg -version` 与
  `ffprobe -version` 都能运行。
- `uvx: command not found`：按 [uv 官方安装文档](https://docs.astral.sh/uv/getting-started/installation/)
  安装 uv，或改用持久本地安装方式。
- MCP 显示未连接：先在终端单独运行免 clone 的 `v2ctx --version` 命令，确认
  GitHub 可访问，再重启 AI 客户端。
- AI 看不到刚安装的工具：Claude/Gemini/Kimi 通常需要重启、`/reload` 或开启
  新会话。
- 视频路径错误：MCP 工具接收本机绝对路径；远程服务器或网页 AI 无法读取你
  电脑上的路径。
- 隐私边界：工具不会主动上传内容，但 AI 宿主如何处理工具返回的图片取决于
  宿主本身；敏感视频请先确认所用 AI 客户端的数据策略。

项目采用 MIT License。
