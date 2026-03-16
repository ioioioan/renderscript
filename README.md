# RenderScript AI

RenderScript AI is an open-core screenplay-to-RenderPackage engine.

It converts one Fountain screenplay scene into a **RenderPackage**: a portable production kit for AI video workflows.

This repository contains the open-core engine and CLI.

The hosted UI lives separately at `renderscript.studio`.

## Product Boundary

RenderScript is intentionally narrow:

- Screenplay in
- RenderPackage out

It does **not**:

- render video
- execute provider APIs
- manage user accounts
- automate generation

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

## Install

```bash
python3 -m pip install -e .
```

## Run Tests

```bash
python3 -m pytest -q
```

## CLI

Build a package from a screenplay:

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal -o ./out/package.zip
```

Add an optional provider pack:

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal --add-pack grok.imagine -o ./out/package.zip
```

## Provider Adapters

Current adapters:

- Universal -> `universal`
- Runway Gen-4 References -> `runway.gen4_image_refs`
- Grok Imagine -> `grok.imagine`

Universal is the default workflow.
Provider packs are optional additions.

## Repo Layout

```text
renderscript/    Core engine
examples/        Example Fountain scripts
tests/           Regression tests
docs/            Project and codebase documentation
```

## Documentation

Start here:

- `docs/CODEBASE_GUIDE.md`
- `docs/STRUCTURE_MAP.md`

## License

Add your chosen open-source license before publishing.
