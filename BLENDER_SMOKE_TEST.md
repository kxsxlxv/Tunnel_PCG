# Stage 5.1 Blender smoke test

Use the Stage-5.1 sample, not the old Stage-5 JSON.

## Automated runtime check

From the repository root:

```bash
blender --background --python scripts/blender_verify_stage5_1.py -- \
    examples/stage5_1_nominal_scene.json \
    --report examples/blender_stage5_1_runtime_report.json
```

Expected final result:

```text
"result": "PASS"
```

For seed 5812, the lining meshes should have approximately these counts:

```text
K      28 vertices / 26 faces
B1     84 vertices / 82 faces
A1     80 vertices / 78 faces
A2     76 vertices / 74 faces
A3     80 vertices / 78 faces
B2     84 vertices / 82 faces
```

The exact values are also embedded in `examples/stage5_1_geometry_metrics.json`.

## Visual check

Import/save the sample normally:

```bash
blender --background --python scripts/blender_import_scene.py -- \
    examples/stage5_1_nominal_scene.json \
    --save-blend examples/stage5_1_nominal_scene.blend
```

Open the `.blend` and view approximately along the tunnel axis. The inner opening must be circular rather than a six-sided polygon.

Flat shading may still show individual face normals. That is expected and can be visually smoothed later; the silhouette and LiDAR-intersection geometry should already follow the cylindrical tessellation.

If the automated verifier reports PASS but the viewport still looks wrong, send a screenshot plus Blender version. That would isolate the remaining issue to viewport shading/display rather than geometry serialization.
