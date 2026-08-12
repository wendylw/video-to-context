#!/bin/sh
set -eu

project_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
bin_dir=${V2CTX_BIN_DIR:-}

usage() {
    echo "usage: ./uninstall.sh [--bin-dir PATH]"
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

for name in v2ctx v2ctx-mcp; do
    source_path=$project_root/$name
    target_path=$bin_dir/$name
    if [ -e "$target_path" ] || [ -L "$target_path" ]; then
        if [ ! -L "$target_path" ] || [ "$(readlink "$target_path")" != "$source_path" ]; then
            echo "error: refusing to remove path not installed by this checkout: $target_path" >&2
            exit 1
        fi
    fi
done

removed=false
for name in v2ctx v2ctx-mcp; do
    target_path=$bin_dir/$name
    if [ -L "$target_path" ]; then
        rm -- "$target_path"
        removed=true
    fi
done

if [ "$removed" = true ]; then
    echo "Removed v2ctx and v2ctx-mcp links from $bin_dir"
else
    echo "Video to Context is not installed in $bin_dir"
fi
