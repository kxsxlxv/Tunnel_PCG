# Tunnel Scanner reimplementation — Stage 5.1

Stage 5.1 fixes the visible/sensor-facing polygonization exposed by the first real Blender smoke test. Stages 1–5 remain intact as the analytical, kinematic, joint, semantic, and Blender-adapter layers; Stage 5.1 adds a **derived curved surface representation** for rendering and LiDAR ray intersection.

## Why Stage 5 looked hexagonal

The Stage-1 analytical segment intentionally follows the paper's eight-corner/hexahedral description. With one chord across a 65–75° A/B segment, however, the chord-to-circle deviation is hundreds of millimetres. That control mesh is appropriate for published corner constraints, but not as final LiDAR/render geometry.

Stage 5.1 therefore keeps the eight-corner mesh as the source of truth for:

- angular closure;
- deformation/joint boundary conditions;
- segment rigid transforms;
- published reconstruction assumptions.

It derives a separate adaptive cylindrical mesh for Blender/sensor export.

## Adaptive meshing rule

For radius `R` and requested maximum sagitta `eps`, the largest permitted chord angle is

```text
delta_max = 2 * acos(1 - eps / R)
```

The default is:

```text
max_sagitta_m = 0.002   # 2 mm
```

A segment can have slightly different front/back angular boundaries. Stage 5.1 therefore uses a two-dimensional `(u,v)` surface grid rather than only subdividing around the circumference.

Let:

```text
U = max(front_span, back_span)
V = max(|back_start-front_start|, |back_end-front_end|)
```

The grid `(Nu,Nv)` is chosen to minimize cell count subject to the conservative diagonal bound:

```text
U/Nu + V/Nv <= delta_max
```

Every intrados/extrados grid vertex is placed directly on a cylinder:

```text
x = radius * sin(alpha)
z = radius * cos(alpha)
```

so front/back taper never drags intermediate vertices off the cylindrical surface.

## Canonical seed 5812

At the default 2 mm tolerance:

```text
segment   Nu   Nv   vertices   faces   conservative sagitta
K          6    1       28       26       1.788 mm
B1        20    1       84       82       1.894 mm
A1        19    1       80       78       1.875 mm
A2        18    1       76       74       1.851 mm
A3        19    1       80       78       1.875 mm
B2        20    1       84       82       1.894 mm
```

Total lining geometry for one ring is only 432 vertices / 420 faces, so the change is inexpensive.

For the same seed, the old one-chord outer-surface sagitta was approximately:

```text
K     53 mm
A   ~550 mm
B   ~614 mm
```

The exported lining is therefore no longer the coarse six-sided control mesh.

## What else was curved

The Stage-4 circumferential outer-collar reconstruction spans an entire K/B/A segment, so leaving it as a hexahedron could reintroduce a polygonal outer silhouette. Stage 5.1 now tessellates those collar pieces around the cylinder as well.

The narrow prescribed radial joints and displacement-gap joints remain their existing analytical solids. Their spans are small, and their exact boundary faces are useful for later reconstruction work.

## Automated verification

Regression suite:

```text
62 tests passed
```

Stage-5.1 geometric stress verification:

```text
5,000 nominal rings
30,000 curved segment meshes
1,000 deformed rings
max conservative sagitta: 1.999982 mm
max deformed local-radius error: 1.33e-15 m
max deformation closure error: 1.20e-15 m
PASS
```

An independent `trimesh` check was also run on 500 rings / 3,000 curved segment meshes and on all 18 objects in the canonical nominal scene. Every checked mesh was watertight, winding-consistent, and positive-volume.

The inherited Stage-5 serialization stress test also passes with the new geometry:

```text
2,000 ScenePackages
30,000 SceneObjects
2,000 JSON round-trips
PASS
```

## Layout additions

```text
src/tunnel_scanner_core/
    curved_mesh.py       # Stage 5.1 adaptive cylindrical surface generation
    ... previous modules

examples/
    generate_stage5_1_scenes.py
    stage5_1_nominal_scene.json
    stage5_1_nominal_scene.obj
    stage5_1_deformed_scene.json
    stage5_1_deformed_scene.obj
    stage5_1_geometry_metrics.json
    stage5_1_verification.json
    stage5_1_trimesh_verification.json

scripts/
    verify_stage5_1_stress.py
    blender_import_scene.py
```

## Generate the Stage-5.1 examples

From the repository root:

```bash
PYTHONPATH=src python examples/generate_stage5_1_scenes.py
```

## Run tests

```bash
python -m pip install -e '.[test]'
pytest
```

## Blender smoke test

Use the new JSON, not the old Stage-5 sample:

```bash
blender --background --python scripts/blender_import_scene.py -- \
    examples/stage5_1_nominal_scene.json \
    --save-blend examples/stage5_1_nominal_scene.blend
```

For visual inspection, omit `--background` or import from Blender's scripting workspace.

The inner opening should now be circular (within the configured geometric tolerance), not a six-sided opening. Blender may still show facet shading if the object is flat-shaded; that is a normal/shading issue, not the old half-metre geometric chord error. LiDAR ray geometry is determined by the actual tessellated mesh.

## Runtime status

The engine-neutral geometry, JSON boundary, and Blender adapter are regression-tested outside Blender. A real Blender executable is not present in the current execution environment, so Stage 5.1 still requires an external Blender smoke test. The user's previous Stage-5 test already confirmed the adapter path itself executes; the new test primarily verifies the changed mesh visually/runtime-side.

See `STAGE5_1_REPORT.md` for detailed design decisions and verification results.

## Automated Blender-side verifier

On a machine with Blender installed:

```bash
blender --background --python scripts/blender_verify_stage5_1.py -- \
    examples/stage5_1_nominal_scene.json \
    --report examples/blender_stage5_1_runtime_report.json
```

See `BLENDER_SMOKE_TEST.md` for the expected per-segment vertex/face counts and visual checks.
