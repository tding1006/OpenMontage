#!/usr/bin/env bash
# Build asr/runtime.tar — a prebuilt faster-whisper venv + Whisper model packed
# into ONE file, so it can live on a slow network filesystem and be restored to
# local disk on demand.
#
# Why this exists
# ---------------
# Creating a venv directly on a FUSE network mount is pathological: ~40k tiny
# files, and `pip install numpy` never finished in 400s. Building on local disk
# takes ~8s; shipping a single tarball turns that back into ~26s of untar per
# fresh container.
#
# Requirements: python3 with venv, ffmpeg on PATH, a writable LOCAL disk.
#   PIP_INDEX   pypi mirror (default: the Volcengine mirror used in the sandbox)
#   HF_ENDPOINT huggingface mirror (default: https://hf-mirror.com)
#   MODEL_REPO  any CTranslate2-format repo (default: Systran/faster-whisper-small)
#
# Resulting layout inside the tarball (extracted with `tar -xf ... -C /`):
#   /root/v/bin/python
#   /root/models/whisper-small/...
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"     # .../coze-vefaas
TAR="$ROOT/asr/runtime.tar"
WORK="${WORK:-/root}"                        # MUST be local disk, not the network drive
MODEL_DIR="$WORK/models/whisper-small"
MODEL_REPO="${MODEL_REPO:-Systran/faster-whisper-small}"
PIP_INDEX="${PIP_INDEX:-https://mirrors.ivolces.com/pypi/simple}"
HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

if [ -f "$TAR" ]; then
  echo "[build] $TAR already exists ($(du -h "$TAR" | cut -f1)); remove it to rebuild" >&2
  exit 1
fi

echo "[build] venv -> $WORK/v" >&2
python3 -m venv "$WORK/v"
"$WORK/v/bin/pip" install -q --upgrade pip
"$WORK/v/bin/pip" install -q --index-url "$PIP_INDEX" faster-whisper

echo "[build] model  -> $MODEL_DIR ($MODEL_REPO via $HF_ENDPOINT)" >&2
HF_ENDPOINT="$HF_ENDPOINT" "$WORK/v/bin/python" - "$MODEL_REPO" "$MODEL_DIR" <<'PY'
import sys
from huggingface_hub import snapshot_download
repo, dest = sys.argv[1], sys.argv[2]
path = snapshot_download(repo_id=repo, local_dir=dest)
print(f"[build] downloaded to {path}", file=sys.stderr)
PY

echo "[build] packing -> $TAR" >&2
# Members are stored WITHOUT the leading slash, so `tar -xf $TAR -C /` restores
# them to /root/... exactly. Do not use `tar -C / -cf ... /root/...`.
tar -cf "$TAR" -C / root/v root/models

echo "[build] done: $(du -h "$TAR" | cut -f1)" >&2
echo "[build] verify: $ROOT/asr/asr.sh --help" >&2
