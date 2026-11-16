#!/usr/bin/env bash
# Local ASR wrapper — unpack the prebuilt runtime on demand, then transcribe.
# The container filesystem is ephemeral, so the runtime lives as a single
# tarball on the project drive (asr/runtime.tar) and is restored to /root.
#
#   ./asr/asr.sh input.mp4                      # auto language, writes .srt + .json
#   ./asr/asr.sh input.mp4 --language zh --format srt,txt,json
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAR="$ROOT/asr/runtime.tar"
RUNTIME=/root

if [ ! -f "$TAR" ]; then
  echo "[asr] runtime.tar missing at $TAR" >&2
  exit 2
fi

if [ ! -x "$RUNTIME/v/bin/python" ]; then
  echo "[asr] restoring runtime from $(du -h "$TAR" | cut -f1) tarball (one-time per container)..." >&2
  tar -xf "$TAR" -C /
fi

export ASR_MODEL_DIR="${ASR_MODEL_DIR:-$RUNTIME/models/whisper-small}"
exec "$RUNTIME/v/bin/python" "$ROOT/asr/transcribe.py" "$@"
