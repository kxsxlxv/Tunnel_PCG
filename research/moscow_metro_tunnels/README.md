# Moscow Metro tunnel procedural-generation technical base

Research workspace for high-fidelity procedural geometry of Moscow Metro running tunnels in Blender / synthetic LiDAR.

Research snapshot: **2026-09-21**.

## Status

- Stage 1 — normative baseline + tunnel typology: **complete**
- Stage 2 — structural geometry, clearance model, permanent way and Blender-PCG contract: **complete**
- Stage 3 — equipment/services, special structures, Moscow era anchors, rail-CAD parameters and expanded references: **complete**
- Stage 4 — executable engineering kernel, rail reconstruction, fixtures, schemas and tests: **complete**
- Stage 5 — georeferenced XY, terrain/vertical-profile methodology and 3D alignment pipeline: **complete**

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
- `16_geospatial_alignment_sources.md` — OSM, terrain DEM, CRS and vertical datum sources
- `17_vertical_profile_reconstruction.md` — reconstruction of tunnel Z from sparse public/project data
- `18_blender_route_generation_pipeline.md` — 3D route to Blender generation architecture
- `19_stage5_geospatial_alignment.md` — Stage-5 implementation summary

## Machine-readable research data

- `data/tunnel_types.json`
- `data/clearance_envelopes.json`
- `data/track_systems.json`
- `data/tunnel_equipment.json`
- `data/special_structures.json`
- `data/rail_profiles.json`
- `data/moscow_examples.json`
- `data/geospatial_sources.json`
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
- `alignment3d.py` — 3D chainage, grades, depth-datum conversion, parallel-transport frames and cant;
- `blender_adapter.py` — minimal optional bpy bridge;
- `tools_prepare_geospatial.py` — external GeoJSON + GeoTIFF -> local route/surface preprocessing;
- `schemas/route_alignment.schema.json` — georeferenced 3D alignment interchange;
- `schemas/` — route/archetype schemas;
- `fixtures/` — rail profiles, analytic primitives and clearance/reference metadata;
- `tests/` — executable unit tests.

Validation status:
- Stage 4 engineering kernel: **11 tests passed**;
- Stage 5 pure alignment kernel: **7 tests passed**;
- Stage 5 GeoJSON+GeoTIFF preprocessor: **1 test passed** with optional `geo` dependencies;
- Python compileall passed for the tested Stage-5 modules.

## Geospatial route principle

A credible 3D route is assembled as:

```
public/project XY
+ surface terrain
+ known Z anchors
+ metro engineering constraints
= uncertainty-aware 3D UGR alignment
```

Public OSM geometry is not treated as as-built survey.

Terrain DEM is not treated as tunnel elevation.

Absolute heights from different vertical datums are never mixed without transformation/calibration.

Blender receives only local Cartesian metres and already solved engineering alignment data.

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
10. Geospatial XY/Z sources retain CRS, vertical datum, source class and uncertainty.
11. Published station “depth” is not converted to UGR unless the depth datum is explicitly known.
12. GIS reprojection/DEM processing occurs outside Blender; Blender consumes local-metre engineering data.

## Known deliberately unresolved items

- complete lower `Oм` multi-device polygon topology from GOST Fig. 7;
- manufacturer/master rolling-caliber CAD equivalence of reconstructed R50/R65;
- exact finished lining ID/OD and vertical track placement for an unnamed generic “10 m-class” project;
- project-specific universal-ring taper/rotation sequences and exact bolt/dowel-pocket layouts;
- special-chamber dimensions without named project drawings;
- one survey-grade public XYZ dataset for the entire Moscow Metro network does not appear to be available; Z therefore requires section-specific evidence and constrained reconstruction.

The repository is suitable for an implementation agent to build both tunnel archetypes and geographically plausible 3D route alignments without silently confusing public-map geometry with survey truth.


## Koltsevaya real-route pilot

`examples/koltsevaya_line_v0/` contains the first real-route test: all 12 station anchors, current OSM route_master 1462012 with child routes 300607 Inner and 1462011 Outer, a clearly marked station-anchor XY fallback spline, curvature QA, Blender plan preview and route-master-aware acquisition tools. See `20_koltsevaya_line_pilot.md`.


## Stage 10 — first implementable cross-section

Selected implementation target:
`CAST_IRON_5500_R1000 + LEGACY_R65_TIMBER_KD65_2001_REFERENCE`.

Files:
- `21_stage10_initial_archetype.md` — engineering decision, readiness boundaries and unresolved details;
- `data/stage10_initial_profile.json` — deterministic machine profile with **zero null values**;
- `data/stage10_source_pinpoints.json` — page/figure/table/clause locator for every critical dimension.

The civil XZ section, legacy R65/timber/KD65 permanent way, raised walkway and contact-rail initial geometry are implementation-ready with explicit fallback metadata where needed.

The generic 5.5/5.1 cast-iron family is **not yet series-accurate ring LOD0-ready** because exact N/C/K angles, rib pattern, bolt-hole coordinates, grout-plug coordinate and rebate profile have not been located for one unambiguously identified factory series.


## Stage 11/22 — Koltsevaya physical topology

The Line-5 pilot now separates the two physical main tracks and treats turnouts/depot/service connections as a graph rather than a single polyline.

Files:
- `22_koltsevaya_track_topology_and_junctions.md`;
- `examples/koltsevaya_line_v0/track_topology.json`;
- `examples/koltsevaya_line_v0/junction_events.json`;
- `data/moscow_turnout_archetypes.json`;
- `data/koltsevaya_junction_source_pinpoints.json`;
- `reference_impl/tunnel_pcg_ref/osm_track_graph.py`.

The sourced identity is:
- `KOLTSEVAYA_TRACK_A` = I main / inner / clockwise;
- `KOLTSEVAYA_TRACK_B` = II main / outer / counterclockwise.

The selected first real junction is the Belorusskaya/Krasnaya-Presnya depot-side divergence. Direction-level OSM route IDs are resolved (Inner 300607 / Outer 1462011); exact current member way/node IDs, site Z, installed turnout project and actual chamber dimensions remain deliberately unresolved where no source was obtained. No second tunnel is produced by lateral offset.
