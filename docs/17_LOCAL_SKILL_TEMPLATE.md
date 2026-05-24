# Local RenderPackage Skill Template

Status: active developer surface.

RenderPackage's clearest place in the workflow is as a safe, inspectable production package that developers can adapt into their own local skills and workflow adapters.

The repo includes a starter skill:

```text
skills/renderscript-package-handoff/
  SKILL.md
  references/
    safety.md
    handoff-template.md
    target-workflows.md
```

## Purpose

The skill teaches an agent how to inspect a RenderPackage or Project Bundle, verify approvals, prepare handoff batches, map shots to approved references, and stop before any external side effect.

It is intentionally text-first. It includes no executable scripts.

## Positioning

Do not ask developers to download random black-box skills from the internet.

Do encourage developers to:

- inspect the RenderPackage contract
- copy the local skill template into their own workspace
- adapt it for their own AI-video tools or studio pipeline
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

RenderPackage is most useful for serious AI-video workflows that accept useful references, preserve some continuity, and support controlled take generation.

Priority validation targets should be reference-capable models and workflow layers, not general consumer chat agents. Seedance-style multimodal video workflows, Runway reference workflows, Higgsfield-style workflow platforms, and Mitte-style orchestration tools may be useful targets, but each must be validated with real creator tests before public support claims.

Grok Imagine should remain unsupported until repeated production tests prove otherwise.

## Product Rule

RenderScript provides the package format, approval gates, prompt scaffolds, reference structure, and local skill template.

Developers build their own local skills and adapters around that transparent package. RenderScript should not become a marketplace for opaque skills.
