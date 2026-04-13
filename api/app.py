"""
Legacy shim: re-exports the FastAPI ``app`` from the repo-root ``app.py``.

Vercel’s FastAPI preset discovers the app at the **project root** (``app.py``),
not under ``api/``. Do not set ``vercel.json`` ``functions`` to ``api/app.py``;
that pattern does not match the emitted function and breaks the build.
"""

import importlib.util
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_root_app_path = os.path.join(ROOT, "app.py")
_spec = importlib.util.spec_from_file_location("root_app", _root_app_path)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load FastAPI app module spec from {_root_app_path}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app
