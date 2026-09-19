# Stage 7 Blender smoke test

Stage 6 already verified one-ring bolt Booleans. Stage 7 specifically verifies multi-ring transforms, collections, local bolt indices, and Boolean targets.

## Quick test: five rings

Generate:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5

Run:

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_runtime_report.json \
        --save-blend examples/stage7_tunnel_scene.blend

Expected:

    5 rings
    30 lining segments
    90 bolt heads
    90 pocket cutters
    180 Boolean operations
    90 removed cutters
    174 surviving objects
    result: PASS

The verifier scopes itself to the imported Stage-7 root collection, so unrelated objects elsewhere in the blend file do not contaminate the result.

## Visual inspection

Open examples/stage7_tunnel_scene.blend and check:

- five consecutive rings along +Y;
- small X/Z centreline displacement;
- visible ring-to-ring joint staggering with the default CLI strategy;
- three bolt pockets per segment;
- no cutter solids after Boolean execution;
- no mixing of bolt cutters between different rings;
- circular Stage-5.1 lining in every ring.

Use an oblique longitudinal view from inside the tunnel.

## Geometry-only debug mode

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --no-booleans \
        --report examples/blender_stage7_runtime_report_no_booleans.json \
        --save-blend examples/stage7_tunnel_scene_no_booleans.blend

## Full 13-ring sample

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 13

This produces a 4–5 MB JSON scene with 696 objects before Boolean processing and 468 Boolean operations. It is intentionally generated locally rather than committed to GitHub.

## Failure data

If the verifier fails, provide:

- Blender version;
- examples/blender_stage7_runtime_report.json;
- terminal traceback;
- one oblique screenshot of all rings;
- if relevant, one close wireframe screenshot of the first failed ring.
