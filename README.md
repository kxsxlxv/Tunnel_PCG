# Tunnel_PCG — Tunnel Scanner reimplementation

Current milestone: **Stage 6 — curved segmental lining + bolt pockets/heads + Blender Boolean embedding**.

The project reconstructs the geometry-generation side of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, while keeping every ambiguous or corrected part of the published formulation explicit.

## Implemented stages

- **Stage 1:** six-segment K/B/A ring, angle constraints, deterministic sampling.
- **Stage 2:** ring-wise radial dislocation/rotation and exact closure solver.
- **Stage 3:** mapping deformation states to rigid physical segment transforms.
- **Stage 4:** prescribed radial-joint reconstruction and provisional circumferential collar.
- **Stage 5:** engine-neutral ScenePackage, semantic IDs, JSON boundary, Blender adapter.
- **Stage 5.1:** adaptive cylindrical tessellation for render/LiDAR geometry; the tunnel is now genuinely circular rather than a six-sided control mesh.
- **Stage 6:** Table-3 bolt layouts, tapered bolt pockets, truncated-cone heads, Boolean-ready cutters, and Blender cavity/head embedding.

Detailed assumptions and verification are in the stage reports:

```text
STAGE1_REPORT.md
STAGE2_REPORT.md
STAGE3_REPORT.md
STAGE4_REPORT.md
STAGE5_REPORT.md
STAGE5_1_REPORT.md
STAGE6_REPORT.md
```

## Current geometry architecture

```text
published / analytical parameters
        |
        v
8-corner segment control geometry
        |
        +--> deformation / closure / joint constraints
        |
        v
Stage-5.1 adaptive cylindrical surface
        |
        v
ScenePackage + semantic metadata
        |
        +--> JSON
        |
        v
Blender adapter
        |
        +--> Stage-6 pocket/head Boolean pipeline
        |
        v
render / future LiDAR scanning
```

The analytical hexahedron is intentionally retained as the structural control representation. It is **not** used directly as the final visible/LiDAR-facing tunnel surface.

## Stage-6 bolt geometry

The implementation includes all three Table-3 placement families:

```text
Type 1 centred:       18 assemblies / six-segment ring
Type 2 lateral:       20 assemblies / six-segment ring
Type 3 joint-aligned: 24 assemblies / six-segment ring
```

The canonical Blender sample uses Type 1: three recessed bolt locations per segment.

Bolt heads and temporary pocket tools use `labelID=0` (clutter). The six lining segments retain labels `1..6`.

### Important published-formula ambiguities

Stage 6 does **not** silently copy several inconsistent expressions:

- printed Eq. (20) sends the pocket apex toward the tunnel void despite defining the normal outward and calling the apex embedded;
- Algorithm 1 adds an unscaled unit normal to a metric coordinate;
- Algorithm 1 introduces height ratio `eta` but publishes no numeric value;
- the pocket perturbation notation `N(0, 0.001 m^2)` conflicts with the text calling the disturbances small/bounded.

Both the diagnostic printed variants and the physically usable reconstruction are documented in `STAGE6_REPORT.md`.

## Tests

Current regression suite:

```text
75 tests passed
```

Stage-6 stress verification performed during development:

```text
1,000 rings
18,000 Type-1 bolt assemblies
100 rings with full manifold/volume checks

max pocket depth:        0.13384377 m
lining thickness:        0.35000000 m
max head vertex radius:  3.10746688 m
outer lining radius:     3.35000000 m
minimum Boolean mouth
overlap into tunnel:     0.00406394 m

PASS
```

An independent `trimesh 4.11.1` check validated 600 pocket/head/cutter meshes as watertight, winding-consistent, and positive-volume.

## Install and test

```bash
python -m pip install -e '.[test]'
pytest
```

## Generate the Stage-6 Blender scene

```bash
PYTHONPATH=src python examples/generate_stage6_scene.py
```

This produces:

```text
examples/stage6_nominal_bolts_scene.json
examples/stage6_scene_summary.json
```

The JSON contains 54 pre-Boolean objects:

```text
6 lining segments
6 radial joints
6 circumferential collar pieces
18 pocket cutters
18 bolt heads
```

## Run the real Blender verifier

```bash
blender --background --python scripts/blender_verify_stage6.py -- \
    examples/stage6_nominal_bolts_scene.json \
    --report examples/blender_stage6_runtime_report.json \
    --save-blend examples/stage6_nominal_bolts_scene.blend
```

Expected invariants:

```text
36 Boolean operations applied
18 pocket cutters removed
18 bolt heads retained
all 6 lining segments changed topology
all 6 post-Boolean segment meshes manifold
positive signed volume
result: PASS
```

See `STAGE6_BLENDER_SMOKE_TEST.md` for visual inspection and debug-mode instructions.

## Inspect cutters without applying Booleans

```bash
blender --python scripts/blender_import_scene.py -- \
    examples/stage6_nominal_bolts_scene.json \
    --no-bolt-booleans
```

## Current limitation

The physical cavity is cut correctly and the head is retained as clutter. The cavity wall itself currently remains part of the lining segment object and therefore inherits the segment label.

The paper describes an additional Boolean reconstruction intended to expose the pocket surface as a separately labelable clutter object, but the exact unpublished object sequence is not sufficiently specified to reproduce that semantics without risking a cavity-filling/occlusion artefact. That semantic refinement is intentionally deferred until the current real-Blender Boolean geometry is verified.

## Next validation gate

Before starting ancillary structures or multi-ring assembly, run the Stage-6 Blender verifier. The engine-neutral bolt geometry is tested; the remaining uncertainty is Blender Boolean runtime behaviour.
