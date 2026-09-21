# Stage 10.5 Blender smoke test

Stage 10.5 is the current default Moscow production mode.

It combines:

- selectable 5.5 / 5.1 m cast-iron or 6.1 / 5.6 m ten-block RC civil envelope;
- R65 running rails;
- modern LVT-M half-sleeper supports;
- APC-4 fastening preview;
- segmented modern contact-rail cover;
- dedicated contact-rail supports;
- R2K11/K1351.001-09 cable racks with literal adjacent double-U K1350.002 cradles;
- 16 representative service-cable routes using 8/11 levels per wall;
- nominal 25 mm deterministic irregular cable sag between 1.0 m rack supports;
- source-sized civil system: detailed ten-block 6.1/5.6 m RC option, while cast-iron detail remains deferred;
- one DN80-minimum current tunnel water main with periodic supports;
- raised Moscow walkway.

The timber/KD-65 path is preserved as a selectable legacy preset.

## 1. Generate the current modern scene

From the repository root:

    python examples/generate_stage10_production_tunnel.py \
      --rings 20 \
      --namespace stage10-5-modern

Stage 10.5 + modern is the default. The explicit equivalent is:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.5 \
      --service-preset modern \
      --rings 20 \
      --namespace stage10-5-modern

The researched larger family can be generated with:

    python examples/generate_stage10_production_tunnel.py \
      --rings 20 \
      --namespace stage10-5-rc6100 \
      --civil-archetype rc_block_6100_5600

## 2. Verify in Blender 5.2.2 LTS

    blender --background --python scripts/blender_verify_stage10.py -- \
      examples/stage10_production_scene.json \
      --report examples/blender_stage10_runtime_report.json \
      --save-blend examples/stage10_production_scene.blend

Expected report:

    "stage": "10.5"
    "servicePreset": "modern"
    "result": "PASS"

## 3. Visual checklist

### Running track

Expected:

- no timber sleepers;
- no KD-65 baseplates;
- individual LVT-M blocks under each rail;
- the two support blocks do not bridge the central drain;
- APC-4 fastening preview is visible around each R65 rail seat.

The geometry is still an initial engineering preview for APC-4 small hardware:
do not interpret the clamp/regulator solids as factory CAD.

### Contact rail

Expected:

- support bracket uses the new dimensioned hook-channel silhouette;
- measurable drawing targets are approximately:
  - running-reference -> contact axis: 683 mm drawing callout (690 mm normative datum retained);
  - running-reference -> outer bracket envelope: 873 mm;
  - upper return/top-plate callout: 180 mm;
  - bracket top: +373 mm above UGR/reference;
  - lower/upper bend callouts: 155 / 90 mm;
- the generated bracket outer envelope should reach |x| ~= 1.633 m;
- the contact rail is visibly clamped, not floating:
  - two side jaws around the upper flange;
  - bridge plate above the rail;
  - short vertical insulator stack;
  - two visible through-bolts;
- the support base has a distinct steel plate and four anchors/dowels;
- the local support hood encloses clamp and bolt heads.

- RK contact rail remains on the negative profile-X side;
- working-surface position remains unchanged;
- the protective cover is a low smooth wrap, not the old tall rectangular box;
- the main cover is split into longitudinal spans;
- main-cover spans stop around support zones;
- a local rounded hood covers each fastening/support zone;
- contact supports have their own concrete support blocks;
- contact-support events do not coincide with running-rail support events.

If the modern scene contains the old single continuous
`production_contact_rail_cover`, that is a regression.

### Cable/service infrastructure

Expected:

- old six generic Stage-8 tube assets are absent;
- R2K11 curved rack objects appear on both tunnel walls;
- there is one rack per side per 1.0 m Moscow civil ring;
- upright designation is K1351.001-09;
- each rack has 11 K1350.002 double horns;
- upright envelope is 1440 x 48 x 3 mm;
- each horn envelope is 169 x 40 x 87 mm at 4 mm steel;
- each horn provides two physical cable places, but only one is occupied on a used level;
- eight of eleven levels are populated per wall, producing 16 continuous cable routes total;
- each horn reads as two adjacent U-shaped cradles (`UU`), not as a W/omega;
- the first U begins directly at the upright; there is no horizontal shelf/neck before it;
- no central omega crest is present between the two U shapes;
- visual pair span is 154 mm, internal U clear diameter is 67 mm, central visual gap is 4 mm;
- cable centres sit in those U seats at 37.5 mm and 116.5 mm inward from the upright;
- cable sag is visibly non-uniform from span to span while remaining restrained around a nominal 25 mm;
- sag amplitude varies deterministically by +/-35% and its low point can shift by +/-0.12 span;
- cables remain visibly inside the tunnel intrados;
- negative-X/contact-rail wall is tagged strong-current and its rack midpoint is at tunnel/lining mid-height;
- positive-X/walkway wall is tagged weak-current;
- one DN80-class water main is present on the weak-current side above UGR;
- its preview center is profile z=+0.600 m;
- periodic water-main wall supports are visible at no more than 4.0 m spacing.

The 16-cable population is intentionally a moderate-density visual preset, not
a project-specific cable schedule. Exact pipe OD/wall thickness and support
hardware remain explicit fallbacks.

### Civil geometry

Two civil modes are available.

Default compatibility envelope:

    cast_iron_5500_5100
    intrados radius     2.550 m
    extrados radius     2.750 m
    ring pitch          1.000 m

This cast-iron mode should currently look deliberately simple. Detailed N/C/K
tubing geometry, ribs, rebates and fastenings are not considered resolved and
are not fabricated.

The civil mode to inspect for composite lining in this iteration is:

    --civil-archetype rc_block_6100_5600

Expected RC geometry:

    intrados radius             2.800 m
    extrados radius             3.050 m
    ring pitch                  1.000 m
    actual blocks per ring      10
    nominal angular span        36 degrees/block
    block volume source         0.46 m3
    block mass source           1.15 t
    working reinforcement       16 mm
    erection pins               22 mm
    permanent block bolts       none

Visually, one RC ring should resemble the **composite curved-segment language of
Stage 9**, but it must use the Moscow dimensions above. It is not a smooth tube
with ten lines drawn over it: the mesh contains ten disconnected full-depth
curved annular block components with explicit radial end faces.

The current 8 mm inter-block opening exists to make the composition readable
and is a visual fallback, not a researched joint-width claim. Exact radial-end
chamfers, pin holes/seats and reinforcement-mesh CAD remain deferred.

## 4. Polygon-count expectation

Stage 10.5 keeps the 118-vertex R65 profile but removes mathematically redundant
collinear longitudinal alignment samples before continuous sweeps.

Metadata should report:

    continuousSweepAlignmentCompaction = exact_zero_error_collinear

For a simple four-ring scene CI observes:

    railSourceAlignmentStations = 9
    railSweepAlignmentStations  = 4

For long scenes this should substantially reduce the two rail meshes versus
Stage 10.4 without changing their surface.

## 5. Legacy timber/KD-65 compatibility

Generate the preserved legacy option with:

    python examples/generate_stage10_production_tunnel.py \
      --domain-stage 10.5 \
      --service-preset legacy \
      --rings 20 \
      --namespace stage10-5-legacy

Expected legacy characteristics:

- timber sleepers remain;
- KD-65 hardware remains;
- legacy contact support chain remains;
- old Stage-8 six-service preview remains for compatibility;
- modern LVT/R2K11/water-main assets are not mixed into the legacy preset.

## 6. What to report after visual inspection

Useful screenshots:

1. close contact-rail support + local hood;
2. contact-cover span between two supports;
3. LVT-M/APC-4 rail seat and central drain;
4. close R2K11 horn view showing two literal U cradles and no W/omega crest;
5. one full 6.1/5.6 m RC ring clearly showing ten separate curved blocks;
6. close RC block joint showing the radial end faces / visual seam;
7. weak-current-side water main;
8. 50-100 m perspective view showing varied cable sag and service density;
9. Blender statistics for a long scene.

Also send:

    examples/blender_stage10_runtime_report.json

A real Blender 5.2.2 PASS is still the authoritative runtime closure for the
current Stage-10.5 preset.
