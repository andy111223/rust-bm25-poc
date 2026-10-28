#!/usr/bin/env bash
set -euo pipefail
LEGAL_SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$LEGAL_SCRIPT_DIR/agent.py" "$@"
