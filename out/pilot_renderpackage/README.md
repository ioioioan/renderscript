# How to run this RenderPackage in Runway Gen-4 Image References

This package is prepared for `runway.gen4_image_refs` workflows.

## Drift warnings

- Reference quality and consistency still depend on source image quality.
- Overly broad prompt edits can reduce visual continuity across shots.
- Re-check identity, wardrobe, and location consistency after each run.

## Steps

1. Open Runway and start a Gen-4 image generation workflow.
2. Enable **References** for the generation task.
3. For each shot, review required references in `bindings/bindings.csv`.
4. Add up to 3 references in Runway for that shot as needed.
5. Paste the shot prompt from `prompts/runway.gen4_image_refs_prompts.md`.
6. Generate, review drift, and iterate while preserving shot intent.
