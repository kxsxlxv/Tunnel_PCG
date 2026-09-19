# Stage 8 Blender smoke test

## Generate a five-ring scene

    PYTHONPATH=src python examples/generate_stage8_tunnel.py --rings 5

Default Stage-8 generation uses:

    label policy                stsd_coarse
    ancillary sampling          reference
    ancillary transform         gravity_stitched
    bolts                       enabled
    lateral wavelength          50 m
    vertical wavelength         100 m

## Run the runtime verifier

    blender --background --python scripts/blender_verify_stage8.py -- \
        examples/stage8_tunnel_scene.json \
        --report examples/blender_stage8_runtime_report.json \
        --save-blend examples/stage8_tunnel_scene.blend

Expected values:

    ringCount                   5
    ancillary_pavement          5
    ancillary_walkway           5
    ancillary_rail             10
    ancillary_tube             30
    bolt heads                 90
    pocket cutters before      90
    Boolean operations        180
    cutters removed            90
    pre-Boolean objects       314
    surviving objects         224

Expected result:

    errors: []
    result: PASS

## Visual inspection

For r=3 m the reference layout should show:

- pavement top near local z=-2.25 m;
- rails centered near x=-0.75 m and x=+0.75 m;
- a right walkway about 1.2 m wide and 0.12 m deep, top near z=-1.2 m;
- large sidewall pipes plus smaller cable/power-track services;
- services following the gentle Stage-7.1 X/Z alignment;
- pavement/rails/walkway staying in the gravity frame rather than spinning with staggered lining joints.

Inspect one inter-ring boundary obliquely. Rails, walkway and tube services should meet continuously. The engine-neutral stress test measured maximum mismatch:

    8.88e-16 m

so any visible larger step would indicate Blender/import/display behaviour.

## Semantic labels

Default STSD-coarse:

    0  clutter
    1  segments
    2  walkway
    3  tubes

Pavement and rails intentionally remain class 0 in this policy.

Alternative Seg2Tunnel-like scene:

    PYTHONPATH=src python examples/generate_stage8_tunnel.py \
        --rings 5 \
        --label-policy seg2tunnel_like

Then all ancillary objects are class 0 and segment identities remain labels 1..6.

## If something looks wrong

Please provide Blender version, examples/blender_stage8_runtime_report.json, one cross-section screenshot, one oblique longitudinal screenshot, and if relevant a wireframe close-up at an inter-ring rail/tube boundary.
