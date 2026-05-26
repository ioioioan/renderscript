# RenderScript

RenderScript turns screenplay scenes into agent-actionable RenderPackages for AI-video production: prompts, references, keeper sheets, generated-shot folders, and orchestration files in one portable package.

RenderScript is filmmaker-first in language, but the product is the same for creators, agents, and developers. Creators use the root files. Agents and developers use the structured files under `DEVELOPER_FILES/`.

The product direction is one-click deploy from a RenderPackage, scene batch, or project bundle to a linked or connected agent. That does not mean one-click finished video. RenderScript prepares and sends the structured production job; external agents and creator-selected image/video tools execute it with human approval gates.

RenderScript was originally created through the Codex plugin for VS Code. Ongoing development is now consolidated in Codex with the repository documentation as the source of truth.

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
- Developers who use OpenClaw can use the optional local, inspectable handoff skill from `skills/renderscript-openclaw-handoff/`.
- No Pro. No future-tier framing. MVP is the product.

OpenClaw is mentioned because this repo includes an optional skill for it. It is not the RenderScript product target, and RenderScript remains agent agnostic.

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

`refs/` contains creator-facing reference folders and uploaded image assets. `prompts/reference_prompts.md`, `assets/refs/`, and `audio/` carry the structured visual and voice scaffolds used by PromptTuner, agents, and local tools. Extracted references are scaffolds until the creator approves them as continuity anchors.

The current source authority lives in `docs/`, starting with `docs/14_LATEST_RENDERPACKAGE_STATE_LOCK.md`.

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

The current direction docs are:

- `docs/15_ONE_CLICK_AGENT_DEPLOY.md`
- `docs/16_FULL_PROJECT_MODE_MVP.md`
- `docs/17_LOCAL_SKILL_TEMPLATE.md`

## Optional OpenClaw Skill

RenderPackage is designed to be safe input for agent-assisted and developer-built workflows. The repo includes a text-first optional skill at `skills/renderscript-openclaw-handoff/` for OpenClaw users who want OpenClaw to inspect a RenderPackage, verify approvals, prepare handoff batches, and stop before uploads, generation, spending, credentials, or external tool access.

In plain terms, a skill is an instruction folder for OpenClaw. This one teaches the agent how to read the RenderPackage files and where to stop for creator approval. It does not generate video, connect accounts, request credentials, upload assets, or spend credits.

Do not treat random downloaded skills as trusted. If using OpenClaw, copy the RenderScript skill from the public repo or a tagged release into `~/.openclaw/workspace/skills/` so the workflow remains inspectable.

## License, Copyright, and Branding

RenderScript open-core source code and documentation are licensed under the Apache License, Version 2.0. See `LICENSE`.

Copyright 2026 Ioan Jones.

The Apache License allows use, modification, and distribution of the covered code and documentation, but it does not grant trademark rights. See `NOTICE` and `TRADEMARKS.md`.

RenderScript, RenderPackage, PromptTuner, associated logos, and other RenderScript branding assets are names, marks, and branding assets of Ioan Jones. Do not use them to identify a competing product, imply endorsement, or confuse users about the origin of a product or service.

## Repository Rule

When the RenderPackage contract changes, update every README/readme-style source file in the same PR. Remove obsolete docs rather than leaving contradictory instructions.
