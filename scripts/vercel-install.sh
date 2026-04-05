#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install -r requirements.txt --no-cache-dir
python -m pip install --force-reinstall --no-cache-dir "pydantic-core>=2.27.0,<3"
python -c "import pydantic_core._pydantic_core; print('pydantic_core: ok')"
