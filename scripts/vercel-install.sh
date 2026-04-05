#!/usr/bin/env bash
set -euo pipefail
# Vercel's Python is uv-managed (PEP 668); plain `python -m pip install` fails.
# `uv pip install` respects VIRTUAL_ENV and matches the platform default installer.
uv pip install --no-compile --no-cache-dir --upgrade -r requirements.txt
uv pip install --no-compile --no-cache-dir --force-reinstall "pydantic-core>=2.27.0,<3"
python -c "import pydantic_core._pydantic_core; print('pydantic_core: ok')"
