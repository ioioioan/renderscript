---
name: renderscript-package-handoff
description: Use when an agent needs to work from a RenderScript RenderPackage.zip or Project Bundle.zip to inspect package files, prepare safe AI-video workflow handoff batches, map shots to approved references, log takes and keepers, or build a local workflow adapter. Enforces creator approvals and forbids hidden code, credential handling, uploads, generation, spending, or external tool access without explicit approval.
---

# RenderScript Package Handoff

## Core Boundary

Treat RenderPackage as an inspectable production package, not runnable software.

Do not download third-party skills, run package-contained code, request credentials, upload files, generate video, spend credits, or operate external tools unless the creator explicitly approves that exact action.

Use this skill to turn package data into safe handoff batches for manual workflows, capable assistants, workspace agents, local tools, or custom developer workflows.

## Workflow

1. Inspect the package.
   - Open root creator files first when present: `RENDERPACKAGE.pdf`, `COPY_PASTE_PROMPTS.docx`, `KEEPER_SHEET.csv`, and the source `.fountain`.
   - Read `DEVELOPER_FILES/rpack.json`, `AGENT_ORCHESTRATION.md`, `action_plan.json`, `approval_checkpoints.json`, `bindings.csv`, and prompt packs.
   - For Project Bundles, read `project_manifest.json`, `project_index.json`, `project_refs/`, and each nested scene package summary before preparing batches.

2. Verify approvals.
   - Confirm every reference, voice reference, and shot prompt needed for the requested batch is approved.
   - Treat uploaded assets as source references, not decoration.
   - If any required reference or shot is unapproved, stop and ask for creator review.

3. Choose a handoff route.
   - Manual workflow: prepare copy/paste prompts and asset lists.
   - Package handoff: prepare a concise brief for a capable assistant or workspace.
   - Custom workflow: prepare deterministic JSON/Markdown batches for a developer-built adapter.
   - For target-specific guidance, read `references/target-workflows.md`.

4. Prepare the handoff batch.
   - Use stable shot IDs.
   - Include exact reference folders/assets to attach.
   - Include prompt text, continuity constraints, negative/drift notes, aspect ratio, duration hints, and stop conditions.
   - Keep batches small enough for review, usually one scene or 3-8 shots.
   - Use `references/handoff-template.md` when drafting the output.

5. Stop at checkpoints.
   - Stop before uploading assets, starting generation, spending credits, entering credentials, changing accounts, or selecting keepers.
   - Ask the creator to approve the next action and expected spend/tool access.
   - Log outcomes and keeper decisions only after the creator reviews takes.

## Safety Rules

Read `references/safety.md` before any task that touches external tools, uploads, credentials, payments, or generated media. If in doubt, stay in planning/handoff mode.

## Output Defaults

Prefer Markdown for human handoff and JSON only when the user or adapter needs structured data.

Default deliverables:

- `HANDOFF_BATCH.md` content for the selected scene or shot batch.
- Missing approval/reference checklist.
- Tool-specific notes that are clearly marked as assumptions.
- Take log update instructions.

Never claim a target model, agent, or platform will preserve continuity. Say what the package provides and where the creator must inspect output.
