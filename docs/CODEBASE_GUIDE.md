# RenderScript Codebase Guide

Status: current orientation guide. If this conflicts with `docs/14_LATEST_RENDERPACKAGE_STATE_LOCK.md`, the state lock wins.

## Product Boundary

RenderScript turns one selected Fountain screenplay scene into an agent-actionable RenderPackage. For full screenplays, it can also build a Project Bundle that links one scene RenderPackage per scene. These outputs are for creators, agents, and developers; they are not auto-executable and they do not generate finished video.

The current package contract is:

```text
RENDERPACKAGE.pdf
COPY_PASTE_PROMPTS.docx
KEEPER_SHEET.csv
<source>.fountain
refs/
prompts/reference_prompts.md
assets/refs/
audio/voice_bible.md
generated_shots/
DEVELOPER_FILES/
```

Machine-readable files live under `DEVELOPER_FILES/`, especially `DEVELOPER_FILES/rpack.json`. Structured reference scaffolds also live in `prompts/reference_prompts.md`, `assets/refs/`, and `audio/`.

RenderPackage is also the input to repo-local, inspectable skills and adapters. The optional OpenClaw skill lives in `skills/renderscript-openclaw-handoff/`; it is text-first and approval-gated.

## Main Source Files

- `renderscript/fountain_parser.py`: reads Fountain text.
- `renderscript/compiler.py`: creates the structured `.rscript` document.
- `renderscript/renderpackage.py`: builds the RenderPackage zip.
- `renderscript/project.py`: builds Project Bundles with manifests, project refs, scene batches, and nested scene packages.
- `renderscript/pdf_guide.py`: renders the creator-facing `RENDERPACKAGE.pdf`.
- `renderscript/providers.py`: compatibility registry for optional execution templates.
- `renderscript/validate.py`: validates `.rscript` documents and RenderPackage zips.
- `renderscript/cli.py`: developer CLI entrypoint.
- `app/main.py`: FastAPI app and PromptTuner backend routes.
- `app/templates/index.html`: Studio UI.

## Package Builder

`renderscript/renderpackage.py` is the source of truth for generated package contents. It:

- selects one scene
- builds shot units and shot bindings
- creates reference folders under `refs/`
- writes structured reference prompt, visual reference, and voice-bible scaffolds
- writes creator-facing files at the package root
- writes action and orchestration files under `DEVELOPER_FILES/`
- writes canonical prompts under `DEVELOPER_FILES/prompt_packs/shot_prompts.md`
- writes optional example execution-template prompt packs
- preserves deterministic zip output order

Do not reintroduce old root paths such as `shots/`, `bindings/`, `keepers/`, `edit_guide/`, or `dev/` as current package structure.

## Project Builder

`renderscript/project.py` wraps the existing scene package builder. It writes:

- `PROJECT_OVERVIEW.md`
- `project_manifest.json`
- `project_index.json`
- `project_refs/`
- `scenes/sc_###/RENDERPACKAGE.zip`

Directory outputs can reuse matching scene packages when source hash, scene ID, and provider match. Zip outputs are portable inspection bundles.

## Execution Templates

Universal prompts are canonical. Non-canonical prompt packs are optional example execution templates. No AI-video provider or agent is the RenderScript product target.

Some compatibility names still exist in code, including `provider`, `target_provider`, and `ProviderAdapter`. Treat them as legacy surface area unless changing them is part of a deliberate compatibility migration.

## PromptTuner And Prompt Assist

PromptTuner is the package-WYSIWYG review step before export. Manual editing must always work.

Prompt Assist is optional and uses a backend proxy. Azure OpenAI keys must never be exposed in frontend bundles or package metadata.

Studio export is approval-gated. Every reference, voice reference, and shot prompt must be approved before single-scene or Project Bundle export unlocks.

## Where To Change Things

- Package structure: `renderscript/renderpackage.py`, `renderscript/validate.py`, package tests.
- PDF wording: `renderscript/templates/renderpackage_storyboard.html` and `renderscript/pdf_guide.py`.
- Prompt packs: `renderscript/renderpackage.py` and `renderscript/providers.py`.
- UI workflow: `app/templates/index.html`, `app/static/styles.css`, `app/main.py`.
- Public/source copy: `README.md` and `docs/*.md`.
- Optional OpenClaw skill: `skills/renderscript-openclaw-handoff/`.

## README Rule

When the package contract changes, update every README/readme-style file in the same PR. Remove obsolete docs rather than leaving contradictory instructions.

## Useful Commands

```bash
.venv/bin/python -m pytest -q
renderscript package examples/realistic.fountain --scene 1 -o /tmp/renderscript-package.zip
renderscript project examples/realistic.fountain --project pilot -o /tmp/renderscript-project.zip
renderscript validate /tmp/renderscript-package.zip
```
