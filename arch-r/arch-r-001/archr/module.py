"""Validate conventional Maven modules and read their project identity."""

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET


class AnalysisError(Exception):
    """An input cannot be analyzed safely."""


@dataclass(frozen=True)
class Module:
    path: Path
    source_root: Path
    name: str

    @property
    def report_filename(self) -> str:
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", self.name)
        return f"arch-r-report-{safe_name}.md"


def _require_directory(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        if not stat.S_ISDIR(mode):
            raise AnalysisError(f"Not a directory: {path}")
        # Check permission bits too, so privileged execution does not silently
        # accept directories which are explicitly marked unreadable.
        if (not mode & 0o444 or not mode & 0o111
                or not os.access(path, os.R_OK | os.X_OK)):
            raise AnalysisError(f"Directory is not readable/searchable: {path}")
        with os.scandir(path) as entries:
            next(entries, None)
    except FileNotFoundError as exc:
        raise AnalysisError(f"Directory does not exist: {path}") from exc
    except OSError as exc:
        raise AnalysisError(f"Cannot read directory: {path}: {exc.strerror}") from exc


def _project_name(path: Path) -> str:
    try:
        root = ET.parse(path / "pom.xml").getroot()
        # Only a direct project child counts; a parent's artifactId is not
        # the identity of this module. Support normal Maven XML namespaces.
        if root.tag == "project":
            artifact = root.find("artifactId")
        elif root.tag.startswith("{") and root.tag.endswith("}project"):
            namespace = root.tag.split("}", 1)[0] + "}"
            artifact = root.find(f"{namespace}artifactId")
        else:
            artifact = None
        if artifact is not None and artifact.text and artifact.text.strip():
            return artifact.text.strip()
    except (OSError, ET.ParseError):
        pass
    return path.name


def load_module(raw_path: str) -> Module:
    try:
        path = Path(raw_path).resolve()
    except (OSError, RuntimeError, ValueError) as exc:
        raise AnalysisError(f"Invalid module path: {raw_path}") from exc
    _require_directory(path)
    source_root = path / "src" / "main" / "java"
    _require_directory(source_root)
    return Module(path, source_root, _project_name(path))
