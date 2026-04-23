#!/usr/bin/env bash
set -euo pipefail
tmp_requirements="$(mktemp)"
trap 'rm -f "$tmp_requirements"' EXIT

uv export --frozen --no-dev --no-hashes -o "$tmp_requirements"
uv pip install --no-compile --no-cache-dir -r "$tmp_requirements"
