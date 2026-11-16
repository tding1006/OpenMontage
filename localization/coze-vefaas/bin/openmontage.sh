#!/usr/bin/env bash
# Wrapper for the fork-bound install / sync tool.
#
#   cd /path/to/Video_Maker && ./openmontage.sh status
#   cd /path/to/Video_Maker && ./openmontage.sh check
#   cd /path/to/Video_Maker && ./openmontage.sh apply --yes
#
# The project root is the current directory; override with OPENMONTAGE_ROOT.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export OPENMONTAGE_ROOT="${OPENMONTAGE_ROOT:-$PWD}"

exec python3 "$HERE/openmontage.py" "$@"
