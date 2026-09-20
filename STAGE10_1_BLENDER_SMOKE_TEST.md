# Stage 10.1 Blender smoke test

This smoke test covers the current user-facing Stage 10 production pipeline. The
scene is still the bounded Stage 10.1 transitional scene: Stage-9 production
architecture plus the Moscow profile contract and R65 running rails. Permanent
way, contact rail, and Moscow civil shell geometry are not yet Stage-10
production geometry.

## 1. Generate a short scene

From the repository root:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.1 \
      --rings 20 \
      --namespace stage10-1-smoke

This writes:

    examples/stage10_production_scene.json
    examples/stage10_production_scene_summary.json

The generator validates before serialization that:

- scene metadata is tagged as Stage 10.1;
- the expected Moscow profile ID/SHA is present;
- both running rails use the R65 production profile;
- rail top is at local UGR z=0;
- the gauge plane is 13 mm below UGR;
- the distance between the two inner working faces is exactly 1.520 m within
  the Stage 10.1 floating-point tolerance.

## 2. Verify in Blender

Using Blender 5.2.2 LTS:

    blender --background --python scripts/blender_verify_stage10.py -- \
      examples/stage10_production_scene.json \
      --report examples/blender_stage10_runtime_report.json \
      --save-blend examples/stage10_production_scene.blend

The verifier uses the same Blender adapter/finalization path as Stage 9, then
checks the Stage 10.1 contract instead of the old 16-vertex generic-rail
contract.

Expected result:

    "result": "PASS"

The report also records:

- Moscow profile ID and SHA;
- R65 profile vertex count;
- inner working-face X coordinates;
- reconstructed working-face gauge;
- local UGR and gauge-measurement datums;
- Blender Boolean count;
- stripped lining cap/interface counts;
- deferred Stage 10.2/10.3/10.4 subsystem markers.

## Important interpretation

UGR z=0 is the **profile** engineering datum. It is translated into the existing production core, whose local Z origin is the lining axis:

    profile UGR z = 0.000 m  -> core UGR z = -1.670 m
    profile R65 base -0.180  -> core R65 base = -1.850 m

With a perturbed Stage-9 alignment the world-space rail top is therefore:

    world rail top z = -1.670 m + station.offset_z_m

The verifier explicitly checks this profile/core distinction. It must not assert that either core-local or world-space rail top is z=0.

The current scene still contains Stage-8/9 transitional pavement, walkway and
service tubes. Their metadata is deliberately marked transitional until Stage
10.2-10.4. Do not interpret them as the final Moscow permanent way/civil shell.

The Stage-9 generator and verifier remain available separately and continue to
validate the old generic-rail compatibility path.
