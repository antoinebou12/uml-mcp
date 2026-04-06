"""
Vercel serverless entry: loads the root FastAPI app from ``app.py``.
Configure ``functions`` in ``vercel.json`` for the root ``app.py`` entry
(FastAPI preset); rewrites route traffic to ``/``.
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
