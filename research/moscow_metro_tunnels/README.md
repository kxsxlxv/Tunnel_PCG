# Moscow Metro tunnel procedural-generation technical base

Research workspace for high-fidelity procedural geometry of Moscow Metro running tunnels in Blender / synthetic LiDAR.

Research snapshot: **2026-09-19**.

## Status

- Stage 1 — normative baseline + tunnel typology: **complete**
- Stage 2 — structural geometry, clearance model, permanent way and Blender-PCG contract: **complete**
- Stage 3 — equipment/services, special structures, Moscow era anchors, rail-CAD parameters and expanded references: **complete**
- Stage 4 — executable engineering kernel, rail reconstruction, fixtures, schemas and tests: **complete**

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
- `13_rail_profile_cad.md` — R50/R65 CAD reconstruction source data
- `14_reference_measurement_and_photogrammetry.md` — calibrated photo measurement method
- `15_stage4_reference_sdk.md` — executable reference SDK, QA and limitations

## Machine-readable research data

- `data/tunnel_types.json`
- `data/clearance_envelopes.json`
- `data/track_systems.json`
- `data/tunnel_equipment.json`
- `data/special_structures.json`
- `data/rail_profiles.json`
- `data/moscow_examples.json`
- `data/source_register.csv`

## Executable reference implementation

`reference_impl/` is isolated from the existing production code.

It contains:

- `tunnel_pcg_ref/geometry.py` — analytic 2D geometry primitives;
- `track.py` — gauge/cant rules;
- `contact_rail.py` — physical third-rail placement and side logic;
- `clearances.py` — Cмк, upper Oм, curve corrections and b_R table;
- `rail_profiles.py` — analytic R50/R65 engineering reconstruction;
- `rings.py` — discrete ring sequences;
- `events.py` — deterministic subsystem placement and special-structure overrides;
- `blender_adapter.py` — minimal optional bpy bridge;
- `schemas/` — route/archetype JSON Schemas;
- `fixtures/` — rail profiles, analytic primitives and clearance reference data;
- `tests/` — executable unit tests.

Local pre-upload validation:
- **11/11 unit tests passed**;
- Python `compileall` passed;
- R50/R65 height and base width reproduce nominal dimensions;
- reconstructed head width residual is <0.03 mm;
- R50 area residual +0.231%, centroid residual -0.107 mm;
- R65 area residual +0.154%, centroid residual -0.154 mm.

These rail sections are engineering reconstructions from the published GOST construction geometry, suitable as a high-fidelity synthetic-LiDAR reference. They are not represented as manufacturer rolling-caliber master CAD.

## Non-negotiable implementation rules

1. Physical structure, clearance envelope, operational tolerance and condition/randomization are separate layers.
2. Nominal TBM class never uniquely determines finished lining.
3. Segmental/tubing tunnels are discrete rings at LiDAR LOD0.
4. Unknown project geometry stays `null`; the agent must not invent values.
5. Construction archetype is selectable per individual running tunnel/track, not merely per line or station pair.
6. Services have independent longitudinal phases/pitches; never synchronize all tunnel equipment to ring seams.
7. Photos can infer morphology/dimensions only through explicit calibrated-inference metadata.
8. GOST clearance envelopes are validators, not physical tunnel-wall presets.
9. Project-specific values always override generic reference families when provenance is stronger.

## Known deliberately unresolved items

- complete lower `Oм` multi-device polygon topology from GOST Fig. 7 — raw dimensions are retained rather than guessed;
- manufacturer/master rolling-caliber CAD equivalence of the reconstructed R50/R65 sections;
- exact finished lining ID/OD and vertical track placement for an unnamed generic “10 m-class” project;
- project-specific universal-ring taper/rotation sequences and exact bolt/dowel-pocket layouts;
- special-chamber dimensions without named project drawings.

The repository is now suitable for an implementation agent to begin coding against executable rules rather than prose alone.
