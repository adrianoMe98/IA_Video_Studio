#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
exec docker compose -f compose.yaml -f compose.comfy.yaml --profile wan-tools run --rm model-download "$@"
