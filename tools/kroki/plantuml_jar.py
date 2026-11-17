"""Local PlantUML rendering via ``plantuml.jar`` and a JRE.

Offline / privacy-friendly alternative to the HTTP PlantUML server fallback.
The JAR is never committed; download it with ``scripts/download_plantuml_jar.py``
or set ``PLANTUML_JAR_PATH``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

#: Formats the PlantUML CLI accepts with ``-t<format>``.
JAR_OUTPUT_FORMATS = frozenset({"png", "svg", "pdf", "eps", "txt"})

#: Default download location used by ``scripts/download_plantuml_jar.py``.
DEFAULT_VENDOR_JAR = (
    Path(__file__).resolve().parents[2] / "vendor" / "plantuml" / "plantuml.jar"
)


class PlantUMLJarError(Exception):
    """Local PlantUML JAR rendering failed."""


class JavaNotFoundError(PlantUMLJarError):
    """No usable Java executable was found."""


class PlantUMLJarNotFoundError(PlantUMLJarError):
    """``plantuml.jar`` was not found at a configured or default path."""


def resolve_java_path(explicit: str | None = None) -> str:
    """Return a Java executable path or raise ``JavaNotFoundError``."""
    candidates: list[str] = []
    if explicit:
        candidates.append(explicit)
    env_java = os.environ.get("JAVA_PATH")
    if env_java:
        candidates.append(env_java)
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidates.append(
            str(Path(java_home) / "bin" / ("java.exe" if os.name == "nt" else "java"))
        )
    which = shutil.which("java")
    if which:
        candidates.append(which)

    seen: set[str] = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if Path(path).is_file() or shutil.which(path):
            return path

    if os.name == "nt":
        for base in (
            Path(r"C:\Program Files\Eclipse Adoptium"),
            Path(r"C:\Program Files\Microsoft\jdk"),
            Path(r"C:\Program Files\Java"),
            Path(r"C:\Program Files (x86)\Java"),
        ):
            if not base.is_dir():
                continue
            for child in sorted(base.iterdir(), reverse=True):
                exe = child / "bin" / "java.exe"
                if exe.is_file():
                    return str(exe)

    raise JavaNotFoundError(
        "Java Runtime Environment not found. Install Java 11+ or set JAVA_PATH / JAVA_HOME."
    )


def resolve_jar_path(explicit: str | None = None) -> Path:
    """Return the path to ``plantuml.jar`` or raise ``PlantUMLJarNotFoundError``."""
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env_jar = os.environ.get("PLANTUML_JAR_PATH")
    if env_jar:
        candidates.append(Path(env_jar))
    candidates.extend(
        [
            DEFAULT_VENDOR_JAR,
            Path.home() / ".plantuml" / "plantuml.jar",
            Path("/usr/local/share/plantuml/plantuml.jar"),
            Path("/opt/plantuml/plantuml.jar"),
        ]
    )
    checked: list[str] = []
    for path in candidates:
        checked.append(str(path))
        if path.is_file():
            return path
    raise PlantUMLJarNotFoundError(
        "plantuml.jar not found. Checked:\n"
        + "\n".join(f"  - {p}" for p in checked)
        + "\nDownload with: uv run python scripts/download_plantuml_jar.py"
    )


def jar_available(
    *,
    jar_path: str | None = None,
    java_path: str | None = None,
) -> bool:
    """True when both Java and ``plantuml.jar`` can be resolved without raising."""
    try:
        resolve_java_path(java_path)
        resolve_jar_path(jar_path)
    except PlantUMLJarError:
        return False
    return True


def render_plantuml_jar(
    diagram_code: str,
    output_format: str = "svg",
    *,
    jar_path: str | None = None,
    java_path: str | None = None,
    timeout: float = 30.0,
) -> bytes:
    """Render PlantUML source with the local JAR and return the file bytes.

    Args:
        diagram_code: PlantUML source (preferably already wrapped).
        output_format: One of ``JAR_OUTPUT_FORMATS``.
        jar_path: Optional override for ``plantuml.jar``.
        java_path: Optional override for the Java executable.
        timeout: Subprocess timeout in seconds.

    Returns:
        Rendered diagram bytes.

    Raises:
        PlantUMLJarError: When Java/JAR are missing, the format is unsupported,
            or PlantUML exits non-zero.
    """
    fmt = output_format.lower()
    if fmt not in JAR_OUTPUT_FORMATS:
        raise PlantUMLJarError(
            f"Unsupported PlantUML JAR format '{output_format}'. "
            f"Supported: {', '.join(sorted(JAR_OUTPUT_FORMATS))}"
        )

    java = resolve_java_path(java_path)
    jar = resolve_jar_path(jar_path)

    with tempfile.TemporaryDirectory(prefix="uml-mcp-plantuml-") as tmp:
        tmp_dir = Path(tmp)
        input_path = tmp_dir / "diagram.puml"
        input_path.write_text(diagram_code, encoding="utf-8")
        cmd = [
            java,
            "-jar",
            str(jar),
            f"-t{fmt}",
            "-charset",
            "UTF-8",
            "-o",
            str(tmp_dir),
            str(input_path),
        ]
        logger.debug("Running PlantUML JAR: %s", " ".join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PlantUMLJarError(f"PlantUML JAR timed out after {timeout}s") from exc
        except OSError as exc:
            raise PlantUMLJarError(f"Failed to execute PlantUML JAR: {exc}") from exc

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "unknown error").strip()
            raise PlantUMLJarError(
                f"PlantUML JAR failed (exit {result.returncode}): {detail}"
            )

        output_path = tmp_dir / f"diagram.{fmt}"
        if not output_path.is_file():
            # PlantUML sometimes writes next to the input with a different stem.
            matches = list(tmp_dir.glob(f"*.{fmt}"))
            if not matches:
                raise PlantUMLJarError(
                    f"PlantUML JAR produced no {fmt} file in {tmp_dir}"
                )
            output_path = matches[0]
        return output_path.read_bytes()
