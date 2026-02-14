# RenderScript Phase 1A — Stage A Benchmark Protocol

Goal:
Measure whether `.rscript` reduces structural drift and iteration cost compared to raw screenplay prompting.

Test Set:
- t1_dialogue_attribution.fountain
- t2_character_continuity.fountain
- t3_prop_dependency.fountain
- t4_location_persistence.fountain

For each script:
Run both pipelines:

A) Raw screenplay prompt
B) RenderScript structured input

Keep constant:
- Same model
- Same generation settings
- Same resolution
- Same temperature/creativity
- Same seed if supported

Record for each attempt:

1. Iteration Count
   Number of generations required to reach acceptable output.

2. Time to Acceptable (minutes)
   Measured from first generation to final usable output.

3. Structural Errors (count)
   Count:
   - Character misattribution
   - Missing dialogue
   - Prop disappearance
   - Location drift
   - Scene mismatch

4. Drift Score (0–5)
   0 = severe structural breakdown
   5 = perfect structural fidelity

Repeat:
Run each method 3–5 times per script.
Average results.

Success Criteria:
- ≥30% reduction in iteration count
- ≥30% reduction in structural errors
- ≥1.0 improvement in drift score
