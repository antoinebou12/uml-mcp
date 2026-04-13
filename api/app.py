"""
Vercel helper: exposes the FastAPI ``app`` from repo-root ``app.py``.

Default ``vercel.json`` uses root ``app.py`` as the serverless function; keep
this module if your Vercel ``functions`` entry is ``api/app.py`` instead.
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
