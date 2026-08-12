#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bin_dir=${V2CTX_BIN_DIR:-}

usage() {
    echo "usage: ./install.sh [--bin-dir PATH]"
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --bin-dir)
            if [ "$#" -lt 2 ]; then
                echo "error: --bin-dir requires a path" >&2
                exit 2
            fi
            bin_dir=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "error: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [ -z "$bin_dir" ]; then
    if [ -z "${HOME:-}" ]; then
        echo "error: HOME is not set; pass --bin-dir PATH" >&2
        exit 1
    fi
    bin_dir=$HOME/.local/bin
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "error: python3 was not found (Python 3.9 or newer is required)" >&2
    exit 1
fi
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)'; then
    echo "error: Python 3.9 or newer is required" >&2
    exit 1
fi

ffmpeg=${V2CTX_FFMPEG:-ffmpeg}
ffprobe=${V2CTX_FFPROBE:-ffprobe}
if ! "$ffmpeg" -version >/dev/null 2>&1; then
    echo "error: ffmpeg was not found; install ffmpeg before continuing" >&2
    exit 1
fi
if ! "$ffprobe" -version >/dev/null 2>&1; then
    echo "error: ffprobe was not found; install ffmpeg before continuing" >&2
    exit 1
fi

mkdir -p "$bin_dir"

for name in v2ctx v2ctx-mcp; do
    source_path=$project_root/$name
    target_path=$bin_dir/$name
    if [ -e "$target_path" ] || [ -L "$target_path" ]; then
        if [ -L "$target_path" ] && [ "$(readlink "$target_path")" = "$source_path" ]; then
            continue
        fi
        echo "error: refusing to overwrite unrelated path: $target_path" >&2
        exit 1
    fi
done

for name in v2ctx v2ctx-mcp; do
    source_path=$project_root/$name
    target_path=$bin_dir/$name
    if [ ! -L "$target_path" ]; then
        ln -s "$source_path" "$target_path"
    fi
done

"$bin_dir/v2ctx" --version
echo "Installed v2ctx and v2ctx-mcp in $bin_dir"

case ":${PATH:-}:" in
    *:"$bin_dir":*) ;;
    *) echo "Add $bin_dir to PATH to run v2ctx from any directory." ;;
esac
