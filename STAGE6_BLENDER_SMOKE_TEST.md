# Stage 6 Blender smoke test

## 1. Generate the scene

From the repository root:

```bash
PYTHONPATH=src python examples/generate_stage6_scene.py
```

This produces:

```text
examples/stage6_nominal_bolts_scene.json
examples/stage6_scene_summary.json
```

The canonical sample uses seed 5812 and Type-1 bolt placement:

```text
18 bolt assemblies
54 objects before Blender Boolean processing
36 expected objects after pocket cutters are removed
```

## 2. Run the automated Blender verifier

```bash
blender --background --python scripts/blender_verify_stage6.py -- \
    examples/stage6_nominal_bolts_scene.json \
    --report examples/blender_stage6_runtime_report.json \
    --save-blend examples/stage6_nominal_bolts_scene.blend
```

Expected final report:

```json
{
  "booleanOperationsApplied": 36,
  "boltHeads": 18,
  "removedPocketCutters": 18,
  "errors": [],
  "result": "PASS"
}
```

The exact post-Boolean vertex/face counts are Blender-version dependent, so the verifier checks invariants rather than hard-coding topology counts.

## 3. Visual inspection

Open:

```text
examples/stage6_nominal_bolts_scene.blend
```

Inspect the intrados from inside the ring.

Expected:

- three recessed bolt locations on each of the six segments;
- a tapered pocket/opening around each bolt;
- a small truncated-cone bolt head inside each recess;
- no visible Boolean cutter solids;
- no obvious segment/head interpenetration;
- the Stage-5.1 circular lining remains circular.

Use wireframe view around several pockets to check that the segment mesh was actually cut rather than simply covered by a head object.

## 4. Debug mode

To inspect the cutters before Boolean application:

```bash
blender --python scripts/blender_import_scene.py -- \
    examples/stage6_nominal_bolts_scene.json \
    --no-bolt-booleans
```

The `Bolts/Cutters` collection should then contain 18 tapered pyramid tools, each crossing the curved intrados slightly.

## 5. What to send back if it fails

Please provide:

- Blender version;
- `examples/blender_stage6_runtime_report.json`;
- terminal traceback if Blender exits non-zero;
- one screenshot from inside the ring;
- optionally one close wireframe screenshot of a failed pocket.

That is enough to distinguish Boolean-kernel issues from placement or mesh issues.
