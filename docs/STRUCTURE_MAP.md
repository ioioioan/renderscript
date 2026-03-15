# RenderScript Structure Map

This is a practical map of the repo.

It separates:

- source code
- tests
- assets/templates
- examples
- generated output

## Top-Level Map

```text
renderscript/
├── app/                     # FastAPI UI wrapper
├── bench/                   # Benchmark protocol and scoring data
├── docs/                    # Human-facing codebase documentation
├── examples/                # Example Fountain scripts and expected outputs
├── out/                     # Generated packages and scratch output (not source of truth)
├── renderscript/            # Core Python package
├── tests/                   # Regression tests
├── pyproject.toml           # Package metadata and dependencies
├── build_backend.py         # Minimal build backend
└── renderscript.schema.v0.1.json
```

## Core Python Package

```text
renderscript/
├── __init__.py
├── cli.py                   # CLI entrypoint
├── compiler.py              # Fountain -> internal document
├── fountain_parser.py       # Low-level Fountain parsing
├── ids.py                   # Deterministic id helpers
├── pdf_guide.py             # Creator Guide PDF rendering
├── prompt.py                # Older prompt-rendering path
├── providers.py             # Provider/adapter registry
├── renderpackage.py         # RenderPackage builder
├── validate.py              # Schema validation
├── assets/
│   ├── Example_scene_1_universal_renderpackage_v1.zip
│   └── branding/
│       ├── renderscript_logo_horizontal_mark_left_text_right_pad5_v3.png
│       ├── renderscript_logo_mark_blue_pad5.png
│       ├── youtube.svg
│       └── x.svg
└── templates/
    ├── creator_guide.css
    ├── creator_guide_runway.html
    └── creator_guide_universal.html
```

## UI Layer

```text
app/
├── main.py                  # FastAPI app
├── README.md                # Local UI run instructions
├── requirements.txt
├── static/
│   ├── styles.css
│   ├── sample_RenderPackage.zip
│   └── icons/
│       ├── github.svg
│       ├── x.svg
│       └── youtube.svg
└── templates/
    └── index.html           # Single-page UI
```

## Tests

```text
tests/
├── expected_package_paths.txt
├── test_app_ui.py
├── test_bench.py
├── test_cli_version.py
├── test_package_cli.py
├── test_pdf_guide.py
├── test_phase1a.py
├── test_prompt_cli.py
├── test_realistic_prompt_golden.py
├── test_stage_a_golden.py
└── test_strictness_failures.py
```

## Examples

```text
examples/
├── realistic.fountain
├── t1_dialogue_attribution.fountain
├── t2_character_continuity.fountain
├── t3_prop_dependency.fountain
├── t4_location_persistence.fountain
└── expected/
    ├── realistic.natural.txt
    ├── realistic.structured.txt
    ├── t1_dialogue_attribution.rscript
    ├── t2_character_continuity.rscript
    ├── t3_prop_dependency.rscript
    └── t4_location_persistence.rscript
```

## Generated Output

```text
out/
├── *.zip
├── debug_pdf/
├── pilot_renderpackage_v7/
├── universal_polish/
├── universal_ui_guide/
└── ...
```

Treat `out/` as generated artifacts, not canonical source.

## Responsibility Map

### Parse and compile

- `renderscript/fountain_parser.py`
- `renderscript/compiler.py`
- `renderscript/ids.py`
- `renderscript/validate.py`

### Build creator package

- `renderscript/renderpackage.py`
- `renderscript/providers.py`
- `renderscript/pdf_guide.py`
- `renderscript/templates/*`

### Deliver through interfaces

- `renderscript/cli.py`
- `app/main.py`
- `app/templates/index.html`
- `app/static/styles.css`

## Source of Truth Map

### For creator workflow output

The source of truth is:

- `renderscript/renderpackage.py`

### For provider ids, labels, and filenames

The source of truth is:

- `renderscript/providers.py`

### For Creator Guide PDF layout and copy

The source of truth is:

- `renderscript/pdf_guide.py`
- `renderscript/templates/creator_guide_universal.html`
- `renderscript/templates/creator_guide_runway.html`
- `renderscript/templates/creator_guide.css`

### For UI behavior

The source of truth is:

- `app/main.py`
- `app/templates/index.html`

### For expected behavior

The source of truth is:

- `tests/`

## High-Level Call Graph

```text
UI / CLI
  -> compiler.py
  -> renderpackage.py
      -> providers.py
      -> pdf_guide.py
          -> templates/*
      -> zip output
```

## Practical “Where Do I Look?” Map

### I want to add or rename a provider

Start here:

- `renderscript/providers.py`

Then check:

- `renderscript/renderpackage.py`
- `app/main.py`
- `app/templates/index.html`
- tests in `tests/test_package_cli.py` and `tests/test_app_ui.py`

### I want to change the package folder contents

Start here:

- `renderscript/renderpackage.py`

### I want to change the PDF guide wording

Start here:

- `renderscript/templates/creator_guide_universal.html`
- `renderscript/templates/creator_guide_runway.html`

### I want to change how Fountain is parsed

Start here:

- `renderscript/fountain_parser.py`
- `renderscript/compiler.py`

### I want to understand what the app does on submit

Start here:

- `app/main.py`

### I want to understand why a test is failing

Start here:

- the matching file in `tests/`
- then the module that test is targeting

## Quick Orientation For Future You

If you come back later and feel lost again:

1. Read `docs/CODEBASE_GUIDE.md`
2. Read `renderscript/cli.py`
3. Read `renderscript/renderpackage.py`
4. Use `tests/test_package_cli.py` as the behavioral spec
