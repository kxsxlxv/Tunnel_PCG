# Moscow Metro tunnel procedural-generation technical base

Research workspace for high-fidelity procedural geometry of Moscow Metro running tunnels in Blender / synthetic LiDAR.

Research snapshot: **2026-09-19**.

## Status

- Stage 1 — normative baseline + tunnel typology: **complete**
- Stage 2 — structural geometry, clearance model, permanent way and Blender-PCG contract: **complete**
- Stage 3 — equipment/services, special structures, Moscow era anchors, rail-CAD parameters and expanded references: **complete**
- Stage 4 — exact CAD primitive solving, executable validation fixtures and implementation-facing reference package: pending

## Main documents

- `00_scope_and_method.md` — scope and evidence rules
- `01_standards_and_norms.md` — standards/codes
- `02_tunnel_typology.md` — tunnel archetypes
- `03_geometry_and_dimensions.md` — verified dimensions
- `04_clearance_envelopes.md` — ГОСТ C/O clearance logic
- `04_lining_and_joints.md` — lining topology/details
- `05_track_and_contact_rail.md` — permanent way + third rail
- `06_tunnel_equipment.md` — cables, lights, water, signs, visible signaling equipment
- `07_photo_reference_catalog.md` — photographic + dimensioned drawing catalog
- `08_blender_pcg_spec.md` — procedural-generator architecture
- `09_parameter_confidence_matrix.md` — hard-code vs unresolved gates
- `10_stage2_validation_checklist.md` — first-generator acceptance checks
- `11_special_structures.md` — cross passages, bellmouths, switch chambers, TBM chambers, portals
- `12_moscow_era_section_map.md` — evidence-based Moscow era/project anchors
- `13_rail_profile_cad.md` — R50/R65 exact-CAD reconstruction data
- `14_reference_measurement_and_photogrammetry.md` — calibrated photo measurement method

## Machine-readable data

- `data/tunnel_types.json`
- `data/clearance_envelopes.json`
- `data/track_systems.json`
- `data/tunnel_equipment.json`
- `data/special_structures.json`
- `data/rail_profiles.json`
- `data/moscow_examples.json`
- `data/source_register.csv`

## Non-negotiable implementation rules

1. Physical structure, clearance envelope, operational tolerance and condition/randomization are separate layers.
2. Nominal TBM class never uniquely determines finished lining.
3. Segmental/tubing tunnels are discrete rings at LiDAR LOD0.
4. Unknown project geometry stays `null`; the agent must not invent values.
5. Construction archetype is selectable per individual running tunnel/track, not merely per line or station pair.
6. Services have independent longitudinal phases/pitches; never synchronize all tunnel equipment to ring seams.
7. Photos can infer morphology/dimensions only through explicit calibrated-inference metadata.
8. Rail profile LOD0 must eventually use solved ГОСТ analytic primitives, not an I-beam approximation.

## Stage 4 target

Produce executable engineering fixtures:
- solved R50/R65 ordered line/arc primitives + tests against ГОСТ template dimensions;
- exact programmatic Cмк/Oм cross-section generators;
- fixture meshes/CSV coordinate samples for representative tunnel archetypes;
- JSON Schema validation;
- unit tests for gauge/cant/contact-rail/clearance/event placement;
- optional isolated reference Blender-Python package under this research directory without touching existing project code.
