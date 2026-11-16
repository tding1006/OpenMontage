#!/usr/bin/env bash
# Project-local OpenClaw CLI wrapper.
# System-wide install is blocked (home dir not writable for this agent), so the
# runtime lives in tools/openclaw with its own Node 24 and a project-local state dir.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"

export PATH="$ROOT/tools/node24/bin:$PATH"
export OPENCLAW_STATE_DIR="$ROOT/.openclaw"
export OPENCLAW_CONFIG_PATH="$ROOT/.openclaw/openclaw.json"
export OPENCLAW_WORKSPACE_DIR="$ROOT"

exec "$ROOT/tools/openclaw/node_modules/.bin/openclaw" "$@"
