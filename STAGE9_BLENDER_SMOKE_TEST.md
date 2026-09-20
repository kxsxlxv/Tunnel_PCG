# Stage 9 Blender smoke test

Stage 9 changes production topology substantially, so one real-Blender verification is required before Stage 10.

## Recommended short scene

Generate 20 rings:

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --rings 20 \
        --namespace stage9-smoke

Run Blender:

    blender --background --python scripts/blender_verify_stage9.py -- \
        examples/stage9_production_scene.json \
        --report examples/blender_stage9_runtime_report.json \
        --save-blend examples/stage9_production_scene.blend

Expected verifier result:

    "errors": []
    "result": "PASS"

## What to inspect visually

### Rails

The rails should no longer look like rectangular bars.

Each rail cross-section has:

    broad foot
    narrow web
    broad head

with 16 profile vertices.

The profile is deliberately generic and low-poly. Stage 10 will replace it with the selected Moscow/Russian rail standard.

### Infrastructure continuity

Look obliquely along:

- both rails;
- walkway edge;
- sidewall tubes/services.

There should be no per-ring steps or duplicated ancillary end caps.

### Lining interfaces

After Boolean processing the Blender adapter removes:

- hidden internal front/back lining caps;
- hidden radial segment-to-segment boundary surfaces.

There should be no visible z-fighting at these interfaces.

The tunnel start/end remain capped.

### Bolt geometry

Bolt recesses and retained heads must remain correctly aligned after the Stage-9 stitched centreline mapping.

## Optional chunk test

Generate about 100 m as localized Blender chunks:

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --length-m 100 \
        --chunk-m 25 \
        --chunks-only \
        --localize-chunks-for-blender \
        --namespace stage9-chunk-smoke

The output directory contains:

    manifest.json
    chunk_00000.json
    chunk_00001.json
    ...

Chunk metadata contains the world transform needed to restore canonical global coordinates.

At a chunk boundary:

- one complete lining ring belongs to only one chunk;
- rails/tubes/walkway cross-sections must match exactly;
- no internal infrastructure end cap is generated.

## What to send back

Please provide:

- Blender version;
- blender_stage9_runtime_report.json;
- one interior oblique screenshot showing rails and lining;
- one close-up screenshot at an inter-ring boundary;
- one rail cross-section screenshot if the silhouette looks wrong.
