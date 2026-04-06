from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .compiler import compile_file, compile_fountain_text
from .prompt import render_prompt
from .providers import SUPPORTED_PROVIDERS
from .renderpackage import package_fountain_file
from .validate import validate_document, validate_file

DEFAULT_PACKAGE_OUTPUT_DIR = Path.home() / "renderscript_out"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="renderscript")
    parser.add_argument("--version", action="version", version=f"RenderScript AI v{__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("version")

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("input", type=Path)
    compile_parser.add_argument("-o", "--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("file", type=Path)

    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument("input", type=Path)
    prompt_parser.add_argument("--target", type=str, default="universal")
    prompt_parser.add_argument("--mode", type=str, required=True)
    prompt_parser.add_argument("-o", "--output", type=Path, required=True)

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("input", type=Path)
    package_parser.add_argument("--provider", type=str, default="universal")
    package_parser.add_argument("--add-pack", dest="include_provider_prompts", action="append", default=[])
    package_parser.add_argument("--provider-version", type=str, default="")
    package_parser.add_argument("--scene", type=int)
    package_parser.add_argument("--duration-s", type=int, default=3)
    package_parser.add_argument("--project", type=str, default="project")
    package_parser.add_argument("-o", "--output", type=Path, default=DEFAULT_PACKAGE_OUTPUT_DIR)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "compile":
        try:
            compile_file(args.input, args.output)
            return 0
        except Exception as exc:
            print(exc)
            return 1

    if args.command == "validate":
        ok, message = validate_file(args.file)
        print(message)
        return 0 if ok else 1

    if args.command == "prompt":
        try:
            if args.target not in {"universal", "sora"}:
                raise ValueError("Unsupported target. Supported targets: universal, sora.")
            text = args.input.read_text(encoding="utf-8")
            compiled = compile_fountain_text(text, source_name=args.input.name)
            prompt_text = render_prompt(compiled, mode=args.mode)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(prompt_text, encoding="utf-8")
            return 0
        except Exception as exc:
            print(exc)
            return 1

    if args.command == "package":
        try:
            if args.duration_s <= 0:
                raise ValueError("--duration-s must be a positive integer")
            if args.provider not in SUPPORTED_PROVIDERS:
                raise ValueError(
                    f"Unsupported provider: {args.provider}. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
                )
            package_fountain_file(
                input_path=args.input,
                output_path=args.output,
                provider=args.provider,
                provider_version=args.provider_version,
                include_provider_prompts=args.include_provider_prompts,
                scene_ordinal=args.scene,
                duration_s=args.duration_s,
                project=args.project,
            )
            return 0
        except Exception as exc:
            print(exc)
            return 1

    if args.command == "version":
        print(f"RenderScript AI v{__version__}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
