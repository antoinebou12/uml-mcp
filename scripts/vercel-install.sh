#!/usr/bin/env bash
set -euo pipefail
# Long diagram runs: raise the default function max duration (e.g. 200s on Pro)
# in Vercel Project Settings → Functions. FastAPI preset uses root app.py;
# do not use vercel.json "functions" keyed to api/app.py (unmatched pattern).
# Vercel's Python is uv-managed (PEP 668); plain `python -m pip install` fails.
# `uv pip install` respects VIRTUAL_ENV and matches the platform default installer.
# Do not force-reinstall pydantic-core afterward: requirements.txt pins pydantic and
# pydantic-core as a matched pair; upgrading core alone breaks pydantic's version check.
uv pip install --no-compile --no-cache-dir --upgrade -r requirements.txt
python -c "import pydantic_core._pydantic_core; import pydantic; print('pydantic:', pydantic.__version__, 'pydantic_core: ok')"
