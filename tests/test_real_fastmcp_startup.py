"""Production-startup smoke test using the real FastMCP package.

The normal test suite forces MOCK_FASTMCP before importing application modules. This
subprocess test prevents regressions where the real FastMCP server fails during app
construction and FastAPI silently falls back to a 503 /mcp route.
"""

from __future__ import annotations

import os
import subprocess
import sys


def test_real_fastmcp_http_app_initializes() -> None:
    env = os.environ.copy()
    env.update(
        {
            "USE_REAL_FASTMCP": "1",
            "MOCK_FASTMCP": "0",
            "TESTING": "0",
            "DEVELOPMENT": "0",
            "PYTHONUNBUFFERED": "1",
        }
    )

    code = """
import app
assert app._mcp_http_app is not None, 'FastMCP HTTP app did not initialize'
print('real FastMCP HTTP startup OK')
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, (
        "real FastMCP startup failed\n"
        f"stdout:\n{completed.stdout}\n"
        f"stderr:\n{completed.stderr}"
    )
