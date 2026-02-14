from __future__ import annotations

import argparse
from pathlib import Path

from .compiler import compile_file
from .validate import validate_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="renderscript")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("input", type=Path)
    compile_parser.add_argument("-o", "--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("file", type=Path)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "compile":
        compile_file(args.input, args.output)
        return 0

    if args.command == "validate":
        ok, message = validate_file(args.file)
        print(message)
        return 0 if ok else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
