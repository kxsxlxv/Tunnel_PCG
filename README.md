# Tunnel Scanner reimplementation — Stage 5

Stage 5 introduces the **representation boundary** between the tested procedural geometry core and Blender (or future engine/sensor back ends).

## What is implemented

The project now includes all Stage 1–4 functionality plus:

- engine-neutral `SceneObject` and `ScenePackage` data models;
- deterministic object names and instance IDs;
- exact Blender custom-property names `labelID` and `ringID` used by Tunnel Scanner;
- additional `segmentID`, `instanceID`, `objectType`, `semanticClass`, and reconstruction metadata;
- a Seg2Tunnel-like label policy:
  - lining segments: classes `1..6` in canonical generator order;
  - joints: class `0` (clutter), matching the policy described in Yang et al. (2026);
- two deliberately separate physically coherent package modes:
  - nominal segments + prescribed Stage-4 joints;
  - Stage-3 deformed segments + displacement-induced joints;
- lossless JSON serialization / deserialization;
- Blender adapter using the data-block API (`Mesh.from_pydata`, objects, collections, ID properties);
- standalone Blender import script.

Automated test result:

```text
53 passed
```

Stage-5 stress verification:

```text
2,000 scene packages
30,000 mesh objects validated
2,000 JSON round-trips
PASS
```

## Important semantic convention

Yang et al. state that the Seg2Tunnel synthesis uses background/clutter `0` and lining segment classes `1..6`, and that joints/bolts are merged into clutter. The article does **not** publish the correspondence between its procedural K/B/A segment names and benchmark S1–S6 class numbers.

Stage 5 therefore assigns `1..6` in the generator's canonical physical order:

```text
K, B1, A1, A2, A3, B2
```

and records that mapping in each scene package. This is an explicit reimplementation convention, not a claim about the unpublished author code.

## Why nominal and deformed packages are separate

Stage 4 reconstructs prescribed joint solids in the nominal ring frame. Stage 3 independently produces rigidly deformed segments and displacement-gap meshes. We have **not yet derived a defensible transform for the prescribed joint solids under ring-wise deformation**.

Therefore Stage 5 refuses to silently combine them into one physical scene:

```text
nominal_with_prescribed_joints
    segments + prescribed radial/circumferential joints

deformed_with_displacement_joints
    deformed segments + displacement-gap joints
```

This prevents a visually plausible but geometrically inconsistent Blender scene.

## Layout

```text
src/tunnel_scanner_core/
    angles.py
    config.py
    mesh.py
    deformation.py
    deformed_mesh.py
    joints.py
    scene.py             # Stage 5 engine-neutral objects/packages
    scene_io.py          # Stage 5 JSON schema
    blender_adapter.py   # Stage 5 lazy-bpy adapter
    io.py

scripts/
    blender_import_scene.py
    verify_stage5_stress.py
    ... previous verification scripts

examples/
    stage5_nominal_scene.json
    stage5_deformed_scene.json
    stage5_verification.json
    ... previous examples
```

## Generate examples

```bash
PYTHONPATH=src python examples/generate_stage5_scenes.py
```

## Run tests

```bash
python -m pip install -e '.[test]'
pytest
```

## Import into Blender

From the repository root:

```bash
blender --background --python scripts/blender_import_scene.py -- \
    examples/stage5_deformed_scene.json \
    --save-blend examples/stage5_deformed_scene.blend
```

Or use the UI Blender executable without `--background` if visual inspection is desired.

The adapter creates a hierarchy under `TunnelScanner`, uses metric units, builds one Blender mesh/object per `SceneObject`, and writes semantic custom properties onto the Blender object.

## Blender-runtime status

The adapter has been regression-tested with a purpose-built fake `bpy` data-block model, including hierarchy creation, meshes, validation calls, metric units, and object ID properties. Its source is also syntax-compiled outside Blender.

**A real Blender executable is not installed in the current execution environment**, so a genuine `.blend` runtime test has not yet been performed. That is the only major Stage-5 verification item that remains external to this environment.

See `STAGE5_REPORT.md` for the implementation decisions and verification details.
