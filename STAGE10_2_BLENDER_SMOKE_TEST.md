# Stage 10.2 Blender smoke test

This smoke test covers the Stage-10.2 compatibility mode: permanent way on top
of the Stage-10.1 R65/UGR/gauge contract. Stage 10.3 is now the default.

## 1. Generate a short Stage 10.2 scene

From the repository root:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.2 \
      --rings 20 \
      --namespace stage10-2-smoke

The explicit selector is now required because Stage 10.3 is the default.

The generator writes:

    examples/stage10_production_scene.json
    examples/stage10_production_scene_summary.json

Expected Stage-10.2 content includes:

- two continuous R65 running rails;
- one continuous Moscow track-concrete asset;
- periodic timber sleepers at 1680/km;
- two KD-65 assemblies per sleeper event;
- under-baseplate pads;
- rail-foot pads;
- 24 x 150 mm track screws;
- M22 clamp hardware with explicitly simplified spring clamps;
- 0.900 m central drain;
- 0.530 m drain depth below profile UGR;
- 3% crossfall;
- 50 x 25 mm water-release groove.

The old Stage-8/9 pavement must be absent.

## 2. Verify in Blender

Using Blender 5.2.2 LTS:

    blender --background --python scripts/blender_verify_stage10.py -- \
      examples/stage10_production_scene.json \
      --report examples/blender_stage10_runtime_report.json \
      --save-blend examples/stage10_production_scene.blend

Expected report result:

    "result": "PASS"

The verifier reads `productionGeometry.domainStage`. For Stage 10.2 it checks,
in addition to the Stage-10.1 R65/gauge/UGR contract:

- Stage-9 pavement count = 0;
- track-concrete count = 1;
- sleeper count matches scene metadata;
- one grouped under-pad/baseplate/rail-pad/screw/clamp object per sleeper event;
- the continuous R65 underside is preserved and only rail-pad contact spans are omitted;
- drain width/depth and crossfall metadata;
- sleeper dimensions/top datum;
- KD-65 plan dimensions;
- persistent IDs survive Blender property conversion.

## 3. Expected vertical stack

Profile frame:

    R65 head / UGR                 0.000 m
    R65 base                      -0.180 m
    rail-pad base                 -0.194 m
    KD-65 rail seat               -0.194 m
    baseplate bottom              -0.214 m
    under-pad bottom/sleeper top  -0.220 m
    sleeper bottom                -0.385 m

Production core frame:

    R65 head / UGR                -1.670 m
    R65 base                      -1.850 m
    sleeper top                   -1.890 m
    sleeper bottom                -2.055 m

With a perturbed alignment, the relevant `station.offset_z_m` is added to
these core-local values.

## 4. Transitional geometry note

The track concrete already uses the researched Moscow 5.1 m intrados as its
physical lower boundary. The visible lining is still Stage-9 geometry until
Stage 10.4.

As a result, the bottom of the track-concrete fill may visibly stop above the
current Stage-9 shell. That is expected for Stage 10.2. It does not mean that
the R65/sleeper/KD-65 vertical datums are wrong.

The Stage-8/9 walkway and service tubes also remain transitional. Contact rail
arrives in Stage 10.3; Moscow civil shell/walkway in Stage 10.4.

## 5. Stage 10.1 compatibility

To reproduce the previous Stage-10.1 rails-only scene:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.1 \
      --rings 20 \
      --namespace stage10-1-smoke

The same `scripts/blender_verify_stage10.py` verifier supports Stage 10.1,
10.2 and 10.3.
