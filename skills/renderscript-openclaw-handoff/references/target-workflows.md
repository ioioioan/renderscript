# OpenClaw Workflow Notes

This optional OpenClaw skill is one example of RenderScript agent handoff. These notes are planning guidance for what OpenClaw prepares and how creators choose downstream AI-video tools.

## Best Fit

RenderPackage is strongest when the downstream AI-video workflow supports:

- image references
- reusable character/style/location references
- multi-shot or batch planning
- clear prompt input
- controllable duration/aspect/camera settings
- repeatable take generation
- human keeper review

## OpenClaw Role

OpenClaw should:

- read the package and Project Bundle files
- prepare reviewed shot batches
- map shot IDs to approved references
- keep external tool steps explicit
- stop before uploads, generation, spending, credentials, or keeper selection
- log what inputs were used for each take after the creator reviews results

## Downstream Tool Selection

AI-video tools are not supported agents. Treat them as creator-selected execution targets.

When the creator names a tool:

- state what files and references would be sent
- keep batches small
- respect the tool's actual reference limits
- ask for approval before external access
- record which references were attached to each shot
- report drift instead of inventing missing continuity

## Unsupported Claims

Do not advertise support for any named agent, provider, or workflow as an official RenderScript integration unless it has been explicitly built and validated.

## Adapter Rule

A target adapter should translate RenderPackage data into the target workflow's expected input format. It must not invent missing continuity data or bypass approvals.
