# Stage 10.5 Blender smoke test

Stage 10.5 is the current default Moscow production mode.

It combines:

- 5.5 / 5.1 m Moscow civil shell;
- R65 running rails;
- modern LVT-M half-sleeper supports;
- APC-4 fastening preview;
- segmented modern contact-rail cover;
- dedicated contact-rail supports;
- R2K11 cable racks and representative cables;
- one DN80-minimum current tunnel water main;
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
- R2K11 rack objects appear on both tunnel walls;
- there is one rack per side per 1.0 m Moscow civil ring;
- each rack has 11 horn levels;
- representative cables remain visibly inside the tunnel;
- one water main is present on the weak-current side above UGR.

The current representative cable occupancy is intentionally not a project
cable schedule. Pipe placement is also explicitly fallback-constrained.

### Civil geometry

The Stage-10.4 civil contract is unchanged:

    intrados radius     2.550 m
    extrados radius     2.750 m
    ring pitch          1.000 m

The internal diameter should therefore remain approximately 5.10 m.

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
4. one full civil ring showing both R2K11 racks;
5. weak-current-side water main;
6. 50-100 m perspective view showing service density;
7. Blender statistics for a long scene.

Also send:

    examples/blender_stage10_runtime_report.json

A real Blender 5.2.2 PASS is still the authoritative runtime closure for the
current Stage-10.5 preset.
