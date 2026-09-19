# Stage 7.1 Blender visual check

Stage 7.1 changes only X/Z ring positions. The Stage-6 Boolean pipeline and Stage-7 multi-ring hierarchy are unchanged.

Generate five rings:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5

Then run:

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_1_runtime_report.json \
        --save-blend examples/stage7_1_tunnel_scene.blend

The structural verifier should still PASS.

## What should look different

With the new defaults:

    lambda_x = 50 m
    lambda_z = 100 m

and ring width 1.35 m, the sinusoidal centre shift between adjacent rings is bounded by approximately:

    X:          16.94 mm
    Z:           8.48 mm
    transverse: 18.95 mm

Axis noise with sigma=5 mm is added independently, so individual measured steps can be somewhat larger.

For seed 5812, the canonical five-ring path has a maximum adjacent transverse step of about 21 mm including noise, rather than the roughly 0.13 m seen with the old N-dependent default.

The total five-ring length remains:

    5 * 1.35 m = 6.75 m

apart from viewport/measurement rounding.

## Custom smoothness

A gentler curve:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py \
        --rings 5 \
        --lateral-wavelength-m 100 \
        --vertical-wavelength-m 200

A more visible curve:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py \
        --rings 5 \
        --lateral-wavelength-m 30 \
        --vertical-wavelength-m 60

The 0.1 m amplitude stays unchanged unless code/configuration explicitly changes it.
