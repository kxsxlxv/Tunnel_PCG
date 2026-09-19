# Stage 5 report — engine-neutral scene model and Blender adapter

## 1. Scope

Stage 5 deliberately does **not** add bolt pockets, Boolean operations, ancillary structures, or LiDAR scanning. Its purpose is to establish a reliable boundary between the mathematically tested Stage 1–4 geometry and an actual DCC/simulator scene representation.

The new chain is:

```text
RingMesh / DeformedRingMesh / PrescribedJointSet
                    ↓
              ScenePackage
                    ↓
          versioned scene JSON
                    ↓
              Blender adapter
```

This separation allows future Unreal/USD/Isaac/HELIOS++ back ends to consume the same procedural truth without depending on Blender data structures.

## 2. Semantic metadata recovered from the paper

Section 2.5 of Yang et al. (2026) states that each Blender object is assigned custom properties named exactly:

```text
labelID
ringID
```

and that BlAInder extracts these values during virtual scanning.

For Seg2Tunnel synthesis, the article states:

- background clutter is class `0`;
- the six lining segments are classes `1–6`;
- joints and bolts are merged into clutter rather than separate segmentation classes.

Stage 5 reproduces this policy for the currently implemented object categories.

### Unpublished mapping

The article does not specify which procedural K/B/A segment corresponds to benchmark label S1, S2, ..., S6. The Stage-5 default therefore assigns numeric labels by canonical generator order:

```text
1 K
2 B1
3 A1
4 A2
5 A3
6 B2
```

This mapping is serialized in package metadata together with an explicit warning that it is a reimplementation convention.

## 3. `SceneObject`

Each engine-neutral object contains:

```text
name
vertices
faces
object_type
ring_id
label_id
instance_id
semantic_class
segment_id (optional)
segment_name (optional)
segment_kind (optional)
reconstruction (optional)
collection_path
extra_properties
```

The derived Blender custom-property dictionary contains:

```text
labelID
ringID
instanceID
objectType
semanticClass
segmentID
segmentName
segmentKind
reconstruction
```

plus scalar object-specific properties such as dislocation, rotation, joint width, etc.

All custom-property values are constrained to Blender-friendly scalar types before import.

## 4. Stable identifiers

Object names are deterministic. Example:

```text
R0012_SEG_00_K
R0012_JRAD_00_K_B1
R0012_JDISP_00_K_B1
```

Instance IDs currently reserve 1000 IDs per ring:

```text
instanceID = ringID * 1000 + localObjectIndex
```

This is intentionally simple and deterministic for the staged single-ring prototype. A network-scale ID allocator should replace it when multi-route scene assembly is introduced.

## 5. Physical-coherence rule

Stage 5 exposes two separate scene modes.

### A. `nominal_with_prescribed_joints`

Contains:

- six undeformed Stage-1 lining segments;
- six Stage-4 prescribed radial joints;
- optional front/back provisional circumferential outer-collar pieces.

### B. `deformed_with_displacement_joints`

Contains:

- six Stage-3 rigidly deformed lining segments;
- six Stage-3 displacement-induced gap meshes.

It does **not** include Stage-4 prescribed joint solids.

This distinction is intentional. Stage 4 reconstructed nominal prescribed joints, but no defensible mapping has yet been derived for transforming those solids when the adjacent segments undergo independent radial dislocation and relative rotation. Combining them now would mix incompatible geometry frames.

## 6. Scene JSON

Stage 5 introduces:

```text
schema = tunnel_scanner_scene
schemaVersion = 1
```

A scene JSON stores geometry, hierarchy, benchmark labels, engineering semantics, reconstruction provenance, and package-level assumptions.

Round-trip tests require:

```text
ScenePackage -> JSON-compatible dict -> JSON -> ScenePackage
```

to recover an equal dataclass object.

Unknown schema versions are rejected.

## 7. Blender adapter

`blender_adapter.py` imports `bpy` lazily. Therefore importing `tunnel_scanner_core` on ordinary Python does not require Blender.

The adapter uses Blender's data-block API:

```python
mesh = bpy.data.meshes.new(...)
mesh.from_pydata(vertices, [], faces)
mesh.validate(...)
mesh.update(calc_edges=True)
obj = bpy.data.objects.new(...)
collection.objects.link(obj)
obj["labelID"] = ...
obj["ringID"] = ...
```

No geometry creation depends on selection, active-object state, or Edit Mode.

Nested collection data-block names are qualified by their full parent path. This matters because Blender collection names are global data-block names: using a generic `Segments` data-block for every ring could inadvertently link one collection under several ring parents.

The logical hierarchy remains:

```text
TunnelScanner
└── Ring_0012
    ├── Segments
    └── Joints
        ├── PrescribedRadial
        ├── Circumferential_back
        └── Displacement
```

while Blender data-block names are path-qualified internally.

Metric scene units are set to metres (`METRIC`, scale 1.0).

## 8. Blender command-line importer

`scripts/blender_import_scene.py` is a standalone project-local entry point:

```bash
blender --background --python scripts/blender_import_scene.py -- \
    examples/stage5_deformed_scene.json \
    --save-blend examples/stage5_deformed_scene.blend
```

It adds `src/` to `sys.path`, reads a Stage-5 JSON package, builds the hierarchy and optionally saves the resulting `.blend` file.

## 9. Verification

### Automated suite

Final Stage-5 regression result:

```text
53 passed
```

New tests cover:

- nominal package object composition;
- deformed package object composition;
- exact `labelID` / `ringID` property spelling;
- fine segment labels 1–6;
- joint clutter label 0;
- stable names and instance IDs;
- collection paths;
- lossless JSON round-trip;
- schema-version rejection;
- invalid face rejection;
- fake-`bpy` creation of meshes, nested collections, units and custom properties;
- syntax compilation of the standalone Blender importer.

All Stage 1–4 tests remain enabled and pass.

### Stress verification

`verify_stage5_stress.py` generated:

```text
1000 nominal packages
1000 deformed packages
2000 total packages
30000 total SceneObjects
2000 JSON round-trips
```

Result:

```text
PASS
```

Maximum inherited Stage-3 closure error in this run:

```text
translation: 1.1957467920563633e-15 m
angle:       8.526512829121202e-14 deg
```

No duplicate object names or instance IDs were encountered within any package, and all custom-property values were Blender-compatible scalar types.

See `examples/stage5_verification.json` for the machine-readable result.

## 10. External verification still required

The current execution environment does not contain a Blender executable or the actual `bpy` module. Consequently:

- the adapter's architecture and API surface have been checked against current Blender documentation;
- its data-block behavior is exercised through a fake-`bpy` regression model;
- the import script is syntax-compiled;
- but an actual Blender runtime has **not** executed the code yet.

The next sensible verification is therefore a real Blender smoke test before adding Boolean-heavy bolt pockets.

## 11. Recommendation for Stage 6

Do **not** implement the full bolt system immediately.

Stage 6 should first perform a real Blender smoke test and visual/normal inspection of Stage-5 objects. Once that succeeds, add only the **bolt pocket + head geometry and two-stage Boolean procedure** from Section 2.3, with tests for:

- pocket local frame;
- pocket depth and trapezoid dimensions;
- head truncated-cone dimensions;
- Boolean manifoldness;
- semantic labels after Boolean operations;
- visibility of the recessed pocket from the intrados.

That keeps Blender API issues separate from bolt-geometry reconstruction issues.
