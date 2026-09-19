# Moscow Metro tunnel procedural-generation technical base

Research workspace for a high-fidelity procedural geometry model of Moscow Metro running tunnels for Blender / synthetic LiDAR.

Research snapshot: **2026-09-19**.

## Status

- Stage 1 — normative baseline + tunnel typology: **complete**
- Stage 2 — geometry, clearances, lining topology, track/contact rail, Blender-PCG contract: **complete**
- Stage 3 — equipment/services, route/era applicability map, exact profile vectorization, special structures: pending
- Stage 4 — implementation-facing test fixtures / optional reference generator code: pending

## Files

- `00_scope_and_method.md` — scope, terminology and source-confidence rules
- `01_standards_and_norms.md` — current and historical standards/codes
- `02_tunnel_typology.md` — running-tunnel archetype matrix
- `03_geometry_and_dimensions.md` — verified dimensions starter set
- `04_clearance_envelopes.md` — ГОСТ 23961-2024 C/O envelopes and curve rules
- `04_lining_and_joints.md` — cast-iron, legacy RC, monolithic and modern segment details
- `05_track_and_contact_rail.md` — rail, gauge, sleepers/LVT, concrete, drainage and third rail
- `07_photo_reference_catalog.md` — photographic and drawing references
- `08_blender_pcg_spec.md` — implementation contract for procedural generation
- `09_parameter_confidence_matrix.md` — values safe to hard-code vs project-specific unknowns
- `10_stage2_validation_checklist.md` — acceptance tests for the first generator
- `data/tunnel_types.json` — machine-readable tunnel archetypes
- `data/clearance_envelopes.json` — machine-readable normative envelope starter data
- `data/track_systems.json` — machine-readable permanent-way and contact-rail data
- `data/source_register.csv` — source register and confidence

## Critical implementation rules

1. **Physical tunnel geometry and normative clearance envelopes are different data layers.**
2. A nominal TBM diameter does not uniquely define finished lining ID/OD, segment count or track placement.
3. Segmental/tubing tunnels are constructed as discrete rings; do not model them as one continuously bent cylinder at high-fidelity LOD.
4. Track gauge is curve-radius-dependent.
5. Third-rail side/placement is rule-driven and can change at curves, turnouts and platforms.
6. Unknown project-specific dimensions remain `null`; the coding agent must not invent them.
7. Every hard geometric value should retain provenance and confidence.

## Next research stage

Stage 3 will concentrate on:
- exact vectorization of R50/R65 rail profiles including radii/fillets;
- fuller digitization of ГОСТ clearance polylines;
- cable racks, cables, luminaires, pipes, signs and signaling-visible equipment;
- Moscow line/section/era mapping of tunnel archetypes;
- cross passages, bellmouths, switch/crossover chambers and TBM launch/reception transitions;
- expanded photo/drawing catalog grouped by archetype and era.
