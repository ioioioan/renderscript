---
name: renderscript-openclaw-handoff
description: OpenClaw handoff for RenderScript RenderPackage.zip or Project Bundle.zip: inspect, verify approvals, batch shots, log takes; no uploads, generation, spend, creds without approval.
---

# RenderScript OpenClaw Handoff

## Core Boundary

Treat RenderPackage as an inspectable production package, not runnable software.

This is the optional RenderScript handoff skill for OpenClaw. Downstream AI-video tools remain creator-selected and approval-gated.

Do not download third-party skills, run package-contained code, request credentials, upload files, generate video, spend credits, or operate external tools unless the creator explicitly approves that exact action.

Use this skill to turn package data into safe OpenClaw handoff batches. Keep any video-tool execution outside RenderScript and under explicit creator control.

## Workflow

1. Inspect the package.
   - Open root creator files first when present: `RENDERPACKAGE.pdf`, `COPY_PASTE_PROMPTS.docx`, `KEEPER_SHEET.csv`, and the source `.fountain`.
   - Read `DEVELOPER_FILES/rpack.json`, `AGENT_ORCHESTRATION.md`, `action_plan.json`, `approval_checkpoints.json`, `bindings.csv`, and prompt packs.
   - For Project Bundles, read `project_manifest.json`, `project_index.json`, `project_refs/`, and each nested scene package summary before preparing batches.

2. Verify approvals.
   - Confirm every reference, voice reference, and shot prompt needed for the requested batch is approved.
   - Treat uploaded assets as source references, not decoration.
   - If any required reference or shot is unapproved, stop and ask for creator review.

3. Choose the OpenClaw handoff shape.
   - Planning only: prepare prompts, asset lists, and missing-approval notes.
   - Assisted execution: prepare a concise OpenClaw batch and stop before any external side effect.
   - Structured adapter: prepare deterministic JSON/Markdown for a user-owned OpenClaw workflow.
   - For target guidance, read `references/target-workflows.md`.

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
