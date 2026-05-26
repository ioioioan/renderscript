# RenderScript OpenClaw Skill

Status: active developer surface.

RenderPackage is agent and provider agnostic. This repository includes an optional OpenClaw skill because it is the one agent-specific skill currently built here. The package remains a safe, inspectable production object that developers can also adapt into their own local tools and workflow adapters.

The repo includes an optional OpenClaw skill:

```text
skills/renderscript-openclaw-handoff/
  SKILL.md
  references/
    safety.md
    handoff-template.md
    target-workflows.md
```

## Purpose

The skill teaches OpenClaw how to inspect a RenderPackage or Project Bundle, verify approvals, prepare handoff batches, map shots to approved references, and stop before any external side effect.

It is intentionally text-first. It includes no executable scripts.

In plain terms, a skill is an instruction folder for OpenClaw. This one tells the agent how to read RenderScript's package structure and where the approval boundaries are. It does not generate video, connect accounts, request credentials, upload assets, or spend credits.

Developer setup:

1. Install OpenClaw separately.
2. Copy `skills/renderscript-openclaw-handoff/` into `~/.openclaw/workspace/skills/renderscript-openclaw-handoff/`.
3. Inspect `SKILL.md` and the files in `references/`.
4. Run `openclaw skills check`.
5. Give OpenClaw an exported RenderPackage zip or Project Bundle only after the creator has approved the package.

## Positioning

Do not ask developers to download random black-box skills from the internet.

Do encourage developers to:

- inspect the RenderPackage contract
- copy the local OpenClaw skill into `~/.openclaw/workspace/skills/`
- adapt downstream tool notes only after testing
- keep the skill repo-local and auditable
- add scripts only after review, testing, and explicit need

## Safety Boundary

The starter skill must not:

- request credentials
- handle API keys
- upload assets without approval
- submit generation jobs without approval
- spend credits without approval
- run package-contained code
- claim provider support before a real workflow succeeds

## Target Workflow Direction

RenderPackage is most useful when agents or local tools prepare controlled handoff batches for serious AI-video workflows that accept useful references, preserve some continuity, and support controlled take generation.

Priority validation targets should be package handoff flows into reference-capable models and workflow layers. Downstream tools may be useful execution targets, but each must be validated with real creator tests before public support claims.

Specific generation tools should remain unsupported until repeated production tests prove otherwise.

## Product Rule

RenderScript provides the package format, approval gates, prompt scaffolds, reference structure, and optional OpenClaw skill.

Developers build their own adapters around that transparent package. RenderScript should not become a marketplace for opaque skills.
