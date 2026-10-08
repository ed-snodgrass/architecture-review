"""Command-line entry point for ArchR."""

import argparse
import os
from pathlib import Path
import sys
import tempfile

from .discovery import discover_clients
from .module import AnalysisError, load_module
from .report import render_report


def write_report(filename: str, content: str) -> None:
    """Replace the report atomically, preserving an existing report on failure."""
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=Path.cwd(),
            prefix=".arch-r-", suffix=".tmp", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        os.replace(temporary, Path.cwd() / filename)
    except OSError as exc:
        raise AnalysisError(f"Cannot write report {filename}: {exc.strerror or exc}") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arch-r")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Analyze a Java/Spring Maven module")
    analyze.add_argument("spring_module_path", help="Relative or absolute module directory")
    args = parser.parse_args(argv)
    try:
        module = load_module(args.spring_module_path)
        clients = discover_clients(module)
        content = render_report(module, clients)
        write_report(module.report_filename, content)
    except AnalysisError as exc:
        print(f"arch-r: {exc}", file=sys.stderr)
        return 1
    return 0
