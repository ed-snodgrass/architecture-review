"""Command-line entry point for ArchR."""

import argparse
import sys

from .module import AnalysisError, load_module


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arch-r")
    commands = parser.add_subparsers(dest="command", required=True)
    analyze = commands.add_parser("analyze", help="Analyze a Java/Spring Maven module")
    analyze.add_argument("spring_module_path", help="Relative or absolute module directory")
    args = parser.parse_args(argv)
    try:
        load_module(args.spring_module_path)
        # Discovery and report writing are added in subsequent plan tasks.
    except AnalysisError as exc:
        print(f"arch-r: {exc}", file=sys.stderr)
        return 1
    return 0
