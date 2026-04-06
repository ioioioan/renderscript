# RenderScript Codebase Guide

This document explains what the codebase does, how the major parts fit together, and where to start reading if the project feels larger than expected.

It is written for someone who needs a working mental model, not a line-by-line reference.

## What RenderScript Is

RenderScript converts one Fountain screenplay scene into a **RenderPackage**.

The product boundary is intentionally narrow:

- Screenplay in
- RenderPackage out

It does **not** render video, call provider APIs, manage users, or automate generation.

The core idea is:

1. Parse Fountain text into a deterministic internal document.
2. Convert one scene into a creator-facing package.
3. Export prompt packs, planning files, and machine-readable metadata.

## The Three Main Surfaces

There are three main ways to think about the codebase:

### 1. Compiler surface

This turns `.fountain` text into a structured internal document.

Relevant files:

- `renderscript/fountain_parser.py`
- `renderscript/compiler.py`
- `renderscript/ids.py`
- `renderscript/validate.py`
- `renderscript.schema.v0.1.json`

### 2. Packaging surface

This turns one compiled scene into a RenderPackage zip.

Relevant files:

- `renderscript/renderpackage.py`
- `renderscript/pdf_guide.py`
- `renderscript/providers.py`
- `renderscript/templates/*`

### 3. Delivery surface

This open-core repo exposes the system through the CLI.

Relevant file:

- `renderscript/cli.py`

The hosted UI exists separately at `renderscript.studio` and is not part of this public repo.

## Recommended Reading Order

If you want to understand the code quickly, read in this order:

1. `renderscript/cli.py`
2. `renderscript/compiler.py`
3. `renderscript/renderpackage.py`
4. `renderscript/providers.py`
5. `renderscript/pdf_guide.py`

That order follows the real product flow from input to output.

## End-to-End Data Flow

### A. Input

The user supplies a `.fountain` file.

This happens through:

- CLI: `renderscript package ...`
- or a separate hosted UI that wraps the same package engine

### B. Parsing

`renderscript/fountain_parser.py` tokenizes Fountain into scenes and beats.

It recognizes:

- scene headings
- action lines
- dialogue lines
- parentheticals
- transitions

It produces `ParsedScene` and `ParsedToken` objects.

### C. Compilation

`renderscript/compiler.py` converts parsed scenes into the internal JSON-like document.

The compiled document includes:

- `meta`
- `entities`
- `scenes`

Important details:

- character ids are generated deterministically
- location ids are generated deterministically
- scene ids are generated deterministically
- timestamps are deliberately fixed in the compiled document for deterministic outputs

This compiled document is the internal source for later steps.

### D. Validation

`renderscript/validate.py` validates compiled output against `renderscript.schema.v0.1.json`.

This is a lightweight in-repo validator, not a full external JSON schema engine.

### E. Packaging

`renderscript/renderpackage.py` is the largest and most important file in the repo.

It does several jobs:

- selects one scene
- builds shot units from scene beats
- expands or merges units into a bounded shot count
- creates shot bindings
- creates creator-facing CSVs
- creates prompt pack files
- creates audio-post helper files
- creates `PACKAGE_MAP.md` and `START_HERE.txt`
- writes `dev/rpack.json` and `dev/provenance.json`
- asks `pdf_guide.py` to render `CREATOR_GUIDE.pdf`
- writes the final zip in deterministic file order

If you only have time to understand one file after the compiler, make it `renderscript/renderpackage.py`.

### F. PDF guide rendering

`renderscript/pdf_guide.py` renders the Creator Guide PDF.

It works like this:

1. Build HTML from Jinja templates in `renderscript/templates/`
2. Prefer Playwright for HTML-to-PDF
3. Fall back to a simple internal PDF if HTML rendering fails

The guide is presentation logic, not package truth.
The machine truth still lives in `dev/rpack.json`.

### G. Delivery

#### CLI

`renderscript/cli.py` exposes commands such as:

- `compile`
- `validate`
- `prompt`
- `package`

The CLI is the main developer entry point.

#### Hosted UI

The hosted UI is intentionally separate from this open-core repo.

That separation keeps the public repository focused on:

- the engine
- the CLI
- tests
- examples

## The Important Internal Concepts

### 1. Compiled document

This is the internal screenplay representation created by `compiler.py`.

It is not the creator package.

### 2. RenderPackage

This is the exported zip creators actually use.

It contains:

- creator docs
- shot planning data
- prompt packs
- audio-post docs
- machine-readable package files

### 3. Provider registry

`renderscript/providers.py` is the single source of truth for provider adapters.

It defines:

- machine id
- creator-facing label
- prompt filename
- support status
- whether reference images are usually expected

Current providers:

- `universal`
- `runway.gen4_image_refs`
- `grok.imagine`

### 4. Machine truth vs creator UX

This is one of the most important architectural ideas in the repo.

- Creator-facing workflow files live in the package root and subfolders.
- Machine-readable truth lives in `dev/rpack.json`.

If you are building tooling, `dev/rpack.json` matters most.
If you are helping creators use the package, the docs and prompt files matter most.

## What the Major Files Do

### `renderscript/fountain_parser.py`

Low-level Fountain parsing.

Responsibilities:

- detect scene boundaries
- classify lines as action/dialogue/etc.
- enforce simple formatting assumptions

### `renderscript/compiler.py`

Builds the structured internal document from parsed scenes.

Responsibilities:

- assign ids
- normalize entities
- assemble scenes and beats
- produce deterministic output

### `renderscript/ids.py`

Small deterministic id helpers used by the compiler.

### `renderscript/prompt.py`

Older prompt rendering path for structured and natural text prompts.

This is separate from RenderPackage prompt-pack generation.

### `renderscript/renderpackage.py`

Main package builder.

Responsibilities:

- scene extraction
- shot planning
- bindings creation
- prompt pack generation
- audio helper generation
- package map generation
- rpack/provenance generation
- final zip assembly

### `renderscript/pdf_guide.py`

Creator Guide PDF rendering.

Responsibilities:

- render HTML templates
- run Playwright PDF conversion
- provide fallback PDF mode
- emit renderer debug metadata

### `renderscript/providers.py`

Adapter registry.

Use this when:

- adding a provider
- changing provider labels
- changing prompt filenames
- wiring new provider packs into UI and packaging

### `renderscript/validate.py`

Schema validation for compiled documents.

### `renderscript/cli.py`

Command-line entrypoint and argument parsing.

### `tests/`

Regression protection for:

- compiler behavior
- prompts
- packaging
- PDF guide

## The Package Builder Mental Model

The package builder is easier to follow if you split it into five sub-problems:

### 1. Turn scene beats into shot units

The builder starts with screenplay beats and turns them into intermediate units.

These units may be:

- action-driven
- dialogue-driven
- parenthetical-derived
- merged or expanded coverage units

### 2. Normalize shot count

The code tries to keep shot count in a stable range.

It will:

- split action-heavy material
- expand short dialogue scenes into useful coverage
- merge less important units when needed

### 3. Bind references

Each shot gets deterministic reference ids for:

- characters
- locations
- style
- props

### 4. Render package files

The builder writes:

- `shots/shot_list.csv`
- `shots/bindings.csv`
- `keepers/scoring_sheet.csv`
- prompt pack markdown files
- audio-post docs
- `PACKAGE_MAP.md`
- `START_HERE.txt`
- `CREATOR_GUIDE.pdf`

### 5. Emit machine metadata

The builder writes:

- `dev/rpack.json`
- `dev/provenance.json`

These are the package contract for engineering use.

## Where To Make Changes

### If you want to change screenplay parsing

Start in:

- `renderscript/fountain_parser.py`
- `renderscript/compiler.py`

### If you want to change shot planning

Start in:

- `renderscript/renderpackage.py`

Look for:

- unit building
- shot expansion
- bindings generation

### If you want to change provider support

Start in:

- `renderscript/providers.py`
- `renderscript/renderpackage.py`

### If you want to change the Creator Guide

Start in:

- `renderscript/pdf_guide.py`
- `renderscript/templates/creator_guide_universal.html`
- `renderscript/templates/creator_guide_runway.html`
- `renderscript/templates/creator_guide.css`

## What To Ignore At First

If you are trying to regain understanding quickly, ignore these at first:

- `out/`
- `.venv/`
- `.pytest_cache/`
- old generated zip artifacts
- temporary output text files at repo root

Those are outputs or environment artifacts, not core source.

## What `out/` Means

The `out/` directory contains historical generated package examples and older package layouts.

Important:

- it is useful as visual reference
- it is **not** the source of truth for current behavior
- current package logic lives in `renderscript/renderpackage.py`

If you are unsure whether something in `out/` is still current, trust the code and tests, not the old generated artifact.

## Current Architectural Truths

These are the important stable rules in the codebase today:

- Universal workflow is the default.
- Provider packs are optional additions.
- RenderPackage is export-only.
- The package is creator-first.
- `dev/rpack.json` is the machine-readable contract.
- The hosted UI is separate from this open-core repo.

## Useful Commands

### Run tests

```bash
python3 -m pytest -q
```

### Build a package from CLI

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal -o ./out/package.zip
```

### Build a package with an extra provider pack

```bash
renderscript package path/to/script.fountain --scene 1 --provider universal --add-pack grok.imagine -o ./out/package.zip
```

## If You Want One Sentence Per Layer

- `fountain_parser.py`: read Fountain and classify lines
- `compiler.py`: turn parsed scenes into deterministic internal data
- `renderpackage.py`: turn one scene into the final creator package
- `pdf_guide.py`: render the package guide PDF
- `cli.py`: expose the system to developers

## Short Summary

If the codebase feels big, the simplest accurate mental model is:

**RenderScript parses Fountain into a deterministic scene document, then packages one scene into a creator-facing zip with prompt packs and machine-readable metadata.**
