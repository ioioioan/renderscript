# RenderScript AI

RenderScript AI is an open-core screenplay-to-RenderPackage engine.

It converts one Fountain screenplay scene into a **RenderPackage**: a portable production kit for AI video workflows.

This repository contains the open-core engine and CLI.

The hosted UI lives separately at `renderscript.studio`.

## Why It Exists

Screenplays are written for humans. AI video workflows need structured inputs.

RenderScript sits between those two worlds. It takes one screenplay scene and turns it into a deterministic package with:

- shot planning
- reference bindings
- prompt packs
- creator docs
- machine-readable package data

## Product Boundary

RenderScript is intentionally narrow:

- Screenplay in
- RenderPackage out

It does **not**:

- render video
- execute provider APIs
- manage user accounts
- automate generation

## Who This Repo Is For

This open-core repo is for developers who want to:

- generate RenderPackages from the CLI
- inspect `dev/rpack.json`
- build provider adapters
- add validation or QA around package generation
- integrate RenderPackage into internal pipelines

If you want the hosted UI, that is a separate product surface.

## What A RenderPackage Contains

A RenderPackage typically includes:

- `CREATOR_GUIDE.pdf`
- `START_HERE.txt`
- `PACKAGE_MAP.md`
- shot planning files
- prompt packs
- reference bindings
- audio post-production docs
- `dev/rpack.json` as the machine-readable contract

## Quick Start

Install:

```bash
python3 -m pip install -e .
```

Run tests:

```bash
python3 -m pytest -q
```

Build a package:

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal -o ./out/package.zip
```

## CLI Examples

Build a package from a screenplay:

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal -o ./out/package.zip
```

Add an optional provider pack:

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal --add-pack grok.imagine -o ./out/package.zip
```

Use a different primary provider:

```bash
renderscript package path/to/script.fountain --scene 1 --provider runway.gen4_image_refs -o ./out/package.zip
```

## Provider Adapters

Current adapters:

- Universal -> `universal`
- Runway Gen-4 References -> `runway.gen4_image_refs`
- Grok Imagine -> `grok.imagine`

Universal is the default workflow.
Provider packs are optional additions.

## Core Ideas

- One scene in, one package out
- Universal workflow first
- Provider packs as optional additions
- Creator-facing files for workflow use
- `dev/rpack.json` as the machine-readable contract

## Repo Layout

```text
renderscript/    Core engine
examples/        Example Fountain scripts
tests/           Regression tests
docs/            Project and codebase documentation
```

## Examples

Example Fountain inputs live in `examples/`.

Those fixtures are also used by the test suite, so they are a good place to start if you want to understand the expected input shape and current behavior.

## Documentation

Start here:

- `docs/CODEBASE_GUIDE.md`
- `docs/STRUCTURE_MAP.md`

## License

Add your chosen open-source license before publishing.
