# Stage 10.4 Blender smoke test

This smoke test covers the current default Moscow production mode through the
initial 5.5/5.1 civil shell and raised walkway.

## 1. Generate Stage 10.4

From the repository root:

    python examples/generate_stage10_production_tunnel.py \
      --rings 20 \
      --namespace stage10-4-smoke

Stage 10.4 is now a compatibility mode; `--domain-stage 10.4` is required because Stage 10.5 modern is the current default.

Expected scene changes relative to Stage 10.3:

- Stage-9 `lining_segment` objects are absent;
- Stage-9 lining bolt heads/cutters are absent;
- old `production_walkway` is absent;
- `production_moscow_civil_shell_ring` objects appear at 1.0 m pitch;
- one `production_moscow_walkway` appears;
- permanent way and contact rail remain present;
- the former visible gap between track concrete and old tubings is closed by the
  new Moscow intrados.

## 2. Verify in Blender

Using Blender 5.2.2 LTS:

    blender --background --python scripts/blender_verify_stage10.py -- \
      examples/stage10_production_scene.json \
      --report examples/blender_stage10_runtime_report.json \
      --save-blend examples/stage10_production_scene.blend

Expected report:

    "stage": "10.4"
    "result": "PASS"

The verifier checks:

- no Stage-9 lining/bolt objects remain;
- intrados radius = 2.550 m;
- extrados radius = 2.750 m;
- structural depth = 0.200 m;
- Moscow civil ring pitch = 1.000 m;
- no false series-accurate N/C/K LOD0 claim;
- walkway top = profile +0.200 m / core -1.470 m;
- walkway inner edge = +1.660 m;
- walkway outer edge is the physical intrados intersection;
- track concrete is partitioned at the walkway;
- hidden concrete/walkway/lining contact faces are omitted;
- Stage-10.1 R65/gauge, Stage-10.2 permanent way and Stage-10.3 contact rail
  remain valid.

Because Stage 10.4 no longer contains legacy `lining_segment` geometry, the
old Blender cleanup counters for Stage-9 internal segment caps/interfaces are
expected to be zero in this mode.

## 3. Visual interpretation

The large several-decimetre gap seen in Stage 10.2/10.3 was a transitional
civil mismatch and was expected there.

It should **not** remain in Stage 10.4.

The track concrete, raised walkway and visible civil shell now share the same
physical 5.1 m intrados. A comparable visible gap after regenerating a Stage
10.4 JSON should be reported as a bug.

The new civil shell is intentionally smooth between the 1.0 m ring seams.
Series-accurate cast-iron N/C/K ribs, bolts and key geometry are still disabled
rather than guessed.

## 4. Compatibility modes

Stage 10.3:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.3 \
      --rings 20 \
      --namespace stage10-3-smoke

Stage 10.2 and 10.1 remain selectable in the same way.
