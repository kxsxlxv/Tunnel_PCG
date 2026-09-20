# Stage 10.3 Blender smoke test

This smoke test covers the Stage-10.3 legacy-contact-rail compatibility mode.
Stage 10.4 is now the current default.

## 1. Generate Stage 10.3

From the repository root:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.3 \
      --rings 20 \
      --namespace stage10-3-smoke

The explicit selector is required because the default `domainStage` is now 10.4.

Expected additions over Stage 10.2:

- one continuous RK contact rail on the negative-X/contact-rail side;
- one continuous protective-cover preview;
- periodic curved-channel brackets;
- one insulator envelope per bracket;
- three sleeper-attachment screws per bracket;
- one simplified retaining/fastening unit per bracket.

Expected nominal contact geometry:

    nearest running-rail inner face   x=-0.760 m profile
    contact rail axis                 x=-1.450 m profile
    RK working surface                z=+0.160 m profile
    RK working surface                z=-1.510 m core
    RK height                          0.118 m
    RK base width                      0.090 m
    RK top width                       0.080 m
    RK web width                       0.020 m

The protective cover must retain:

    eraMismatch = true
    modernFallbackIsNotHistoricalClaim = true

Its preview preserves the historical 223 mm working-surface-to-cover-top
envelope rather than copying the modern 111 mm product height literally.

## 2. Verify in Blender

Using Blender 5.2.2 LTS:

    blender --background --python scripts/blender_verify_stage10.py -- \
      examples/stage10_production_scene.json \
      --report examples/blender_stage10_runtime_report.json \
      --save-blend examples/stage10_production_scene.blend

Expected report result:

    "result": "PASS"

The verifier checks all Stage-10.1 and 10.2 contracts plus:

- contact-rail axis/working-surface datums;
- RK principal dimensions;
- protective-cover historical clearance/envelope metadata;
- strict era-mismatch markers;
- support count;
- 5.0 m target support pitch;
- sleeper-snapped support events;
- unresolved porcelain-profile marker;
- persistent IDs after Blender custom-property conversion.

## 3. Expected support chain

The deterministic target chain is 5.0 m with a 2.5 m phase, but the legacy
bracket is physically attached to a timber sleeper.

Targets are therefore snapped to the nearest 1680/km sleeper. The resulting
straight-track interval family is approximately:

    4.761904762 m
    5.357142857 m

Both remain inside the researched 4.5-5.4 m running-tunnel range.

## 4. Important civil-shell gap

A visible gap of several decimetres — around 0.4 m — remains expected when
explicitly generating Stage 10.3. The concrete already terminates against the
researched Moscow 5.1 m physical intrados, while that compatibility scene still
uses the old Stage-9 shell.

Do not extend or vertically move the track concrete to hide it.

The current Stage-10.4 default replaces the visible shell and walkway, closes
this interface, and treats a similar gap there as a regression.

## 5. Compatibility modes

Stage 10.2:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.2 \
      --rings 20 \
      --namespace stage10-2-smoke

Stage 10.1:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.1 \
      --rings 20 \
      --namespace stage10-1-smoke

The same Stage-10 Blender verifier supports Stage 10.1 through 10.4.
