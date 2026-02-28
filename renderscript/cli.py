from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .compiler import compile_file, compile_fountain_text, write_rscript
from .prompt import render_prompt
from .renderpackage import package_fountain_file
from .validate import validate_document, validate_file


CSV_HEADERS = [
    "timestamp",
    "label",
    "script_file",
    "compile_ms",
    "output_bytes",
    "schema_valid",
]


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def run_bench(input_dir: Path, out_csv: Path, label: str, emit_dir: Path | None = None) -> list[dict[str, str]]:
    scripts = sorted(input_dir.glob("*.fountain"), key=lambda p: p.name)
    rows: list[dict[str, str]] = []

    if emit_dir is not None:
        emit_dir.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    for script in scripts:
        text = script.read_text(encoding="utf-8")
        started = time.perf_counter_ns()
        compiled = compile_fountain_text(text, source_name=script.name)
        elapsed_ms = int((time.perf_counter_ns() - started) / 1_000_000)
        payload = json.dumps(compiled, indent=2, sort_keys=True) + "\n"
        ok, _ = validate_document(compiled)

        if emit_dir is not None:
            out_file = emit_dir / f"{script.stem}.rscript"
            write_rscript(compiled, out_file)

        rows.append(
            {
                "timestamp": _now_iso_utc(),
                "label": label,
                "script_file": script.name,
                "compile_ms": str(elapsed_ms),
                "output_bytes": str(len(payload.encode("utf-8"))),
                "schema_valid": "true" if ok else "false",
            }
        )

    write_header = not out_csv.exists() or out_csv.stat().st_size == 0
    with out_csv.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="renderscript")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("input", type=Path)
    compile_parser.add_argument("-o", "--output", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("file", type=Path)

    bench_parser = subparsers.add_parser("bench")
    bench_parser.add_argument("--input-dir", type=Path, required=True)
    bench_parser.add_argument("--out", type=Path, required=True)
    bench_parser.add_argument("--label", type=str, required=True)
    bench_parser.add_argument("--emit-dir", type=Path)

    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument("input", type=Path)
    prompt_parser.add_argument("--target", type=str, default="universal")
    prompt_parser.add_argument("--mode", type=str, required=True)
    prompt_parser.add_argument("-o", "--output", type=Path, required=True)

    package_parser = subparsers.add_parser("package")
    package_parser.add_argument("input", type=Path)
    package_parser.add_argument("--provider", type=str, required=True)
    package_parser.add_argument("--provider-version", type=str, default="")
    package_parser.add_argument("--scene", type=int)
    package_parser.add_argument("--duration-s", type=int, default=3)
    package_parser.add_argument("-o", "--output", type=Path, required=True)

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

    if args.command == "bench":
        try:
            rows = run_bench(args.input_dir, args.out, args.label, args.emit_dir)
            return 0 if all(row["schema_valid"] == "true" for row in rows) else 1
        except Exception as exc:
            print(exc)
            return 1

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
            package_fountain_file(
                input_path=args.input,
                output_path=args.output,
                provider=args.provider,
                provider_version=args.provider_version,
                scene_ordinal=args.scene,
                duration_s=args.duration_s,
            )
            return 0
        except Exception as exc:
            print(exc)
            return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
