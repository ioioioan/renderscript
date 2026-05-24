# Target Workflow Notes

These notes are planning guidance, not official integrations.

## Best Fit

RenderPackage is strongest when the target workflow supports:

- image references
- reusable character/style/location references
- multi-shot or batch planning
- clear prompt input
- controllable duration/aspect/camera settings
- repeatable take generation
- human keeper review

## Current Priority Targets

Seedance-style multimodal video workflows:

- Good fit when the workflow accepts text plus image/audio/video references.
- Use RenderPackage reference folders and approved prompt scaffolds as the source of truth.
- Keep batches small and log which references were attached to each shot.

Runway Gen-4 reference workflows:

- Good fit for reusable image references, character/style/object continuity, and manual shot-by-shot generation.
- Use up to the target workflow's current reference limits; do not assume every package reference can be attached at once.

Higgsfield-style workflow platforms:

- Treat as workflow/orchestration targets, not just raw models.
- Use RenderPackage as a structured brief and asset checklist.
- Validate the actual tool behavior before claiming support.

Mitte-style agent/workflow systems:

- Treat as "needs validation" until a real creator workflow succeeds.
- Prepare clean handoff batches and approval checkpoints rather than assuming automation.

Grok Imagine:

- Treat as unsupported until proven otherwise in repeated production tests.
- Do not advertise as a recommended route.

## Adapter Rule

A target adapter should translate RenderPackage data into the target workflow's expected input format. It must not invent missing continuity data or bypass approvals.
