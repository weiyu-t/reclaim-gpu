#!/bin/sh
# Use the official binary unchanged. Keep its workspace on the container's
# native filesystem; Mac shared mounts caused intermittent generator crashes.
set -eu
arch=$(uname -m)
case "$arch" in
  x86_64|amd64) arch=amd64 ;;
  aarch64|arm64) arch=arm64 ;;
  *) echo "Unsupported architecture: $arch" >&2; exit 1 ;;
esac
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/data/prepped"
cp /app/data/prepped/*.parquet "$work/data/prepped/"
cp "/app/bin/mantisgrid-generate-linux-$arch" "$work/generate"
chmod +x "$work/generate"
# The official Go binary also completed with GC disabled in this environment.
# No input, rule, seed, or output format is changed.
GOGC=off "$work/generate" "$work/data"
mkdir -p /app/data/synthetic
cp "$work/data/synthetic/"* /app/data/synthetic/
