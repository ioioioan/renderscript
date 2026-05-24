# RenderScript

RenderScript turns screenplay scenes into agent-actionable RenderPackages for AI-video production: prompts, references, keeper sheets, generated-shot folders, and orchestration files in one portable package.

RenderScript is filmmaker-first in language, but the product is the same for creators, agents, and developers. Creators use the root files. Agents and developers use the structured files under `DEVELOPER_FILES/`.

The product direction is one-click deploy from a RenderPackage, scene batch, or project bundle to a linked or connected agent. That does not mean one-click finished video. RenderScript prepares and sends the structured production job; external agents and image/video models execute it with human approval gates.

## Current Product Truth

- RenderScript is an agent-actionable screenplay-to-AI-video workflow compiler.
- RenderPackage is the portable production object.
- RenderPackage is for creators and agents.
- RenderScript Project Bundle is the full-screenplay wrapper for multiple linked scene RenderPackages.
- RenderPackage is agent-actionable, not auto-executable.
- RenderScript is provider/model/agent agnostic.
- RenderScript does not generate finished video.
- RenderScript does not include executable workflow code in the standard package.
- One-click agent deploy is the north-star workflow direction, not the current package contract.
- Developers can build their own local, inspectable package handoff skills from `skills/renderscript-package-handoff/`.
- No Pro. No future-tier framing. MVP is the product.

RenderScript is agnostic: no named external agent or provider is the product target.

## Current Package Shape

```text
RENDERPACKAGE.pdf
COPY_PASTE_PROMPTS.docx
KEEPER_SHEET.csv
realistic.fountain
refs/
prompts/reference_prompts.md
assets/refs/
audio/voice_bible.md
generated_shots/
DEVELOPER_FILES/
```

`realistic.fountain` is the current example source file; real exports use the source screenplay filename.

`refs/` contains creator-facing reference folders and uploaded image assets. `prompts/reference_prompts.md`, `assets/refs/`, and `audio/` carry the structured visual and voice scaffolds used by PromptTuner and capable agents. Extracted references are scaffolds until the creator approves them as continuity anchors.

The open-core source authority lives in this README plus the compact docs in `docs/`.

## Current Project Bundle Shape

Use this when a Fountain screenplay has multiple scenes and the project needs one manifest with linked scene packages:

```text
PROJECT_OVERVIEW.md
project_manifest.json
project_index.json
project_refs/
  style_bible.md
  continuity_rules.md
  characters.json
  locations.json
scenes/
  sc_001/RENDERPACKAGE.zip
  sc_002/RENDERPACKAGE.zip
```

CLI:

```bash
renderscript project path/to/script.fountain --project pilot -o ./pilot_project_bundle_v1.zip
```

`project_manifest.json` tracks stable scene IDs, scene package paths, batch chunks, shared project refs, approval status, and incremental scene-package reuse metadata.

For implementation orientation, start with `docs/CODEBASE_GUIDE.md`.

## Local Skill Template

RenderPackage is designed to be safe input for developer-built workflows. The repo includes a text-first starter skill at `skills/renderscript-package-handoff/` for agents that need to inspect a RenderPackage, verify approvals, prepare handoff batches, and stop before uploads, generation, spending, credentials, or external tool access.

Do not treat random downloaded skills as trusted. Copy and adapt the local template in your own workspace so the workflow remains inspectable.

## License, Copyright, and Branding

RenderScript open-core source code and documentation are licensed under the Apache License, Version 2.0. See `LICENSE`.

Copyright 2026 Ioan Jones.

The Apache License allows use, modification, and distribution of the covered code and documentation, but it does not grant trademark rights. See `NOTICE` and `TRADEMARKS.md`.

RenderScript, RenderPackage, PromptTuner, associated logos, and other RenderScript branding assets are names, marks, and branding assets of Ioan Jones. Do not use them to identify a competing product, imply endorsement, or confuse users about the origin of a product or service.

## Repository Rule

When the RenderPackage contract changes, update every README/readme-style source file in the same PR. Remove obsolete docs rather than leaving contradictory instructions.
