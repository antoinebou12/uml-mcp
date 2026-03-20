"""
Vercel serverless entrypoint for ``api/app.py``.

This module loads the root FastAPI app so Vercel's ``functions`` configuration
can target the actual serverless file inside the ``api/`` directory.
"""
import importlib.util
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_root_app_path = os.path.join(ROOT, "app.py")
_spec = importlib.util.spec_from_file_location("root_app", _root_app_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app
