# Tunnel_PCG — Tunnel Scanner reimplementation

Current milestone: **Stage 8 — ancillary infrastructure**.

The repository reconstructs and extends the geometry-generation side of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*.

## Implemented

    Stage 1    six-segment K/B/A ring and angle constraints
    Stage 2    ring-wise dislocation/rotation closure solver
    Stage 3    deformation state -> rigid segment geometry
    Stage 4    prescribed joints
    Stage 5    ScenePackage + semantic IDs + Blender adapter
    Stage 5.1  curved render/LiDAR lining mesh
    Stage 6    bolt pockets, heads, Blender Boolean embedding
    Stage 7    multi-ring Eq. (21) assembly
    Stage 7.1  physical-wavelength centreline correction
    Stage 8    pavement, walkway, rails and tube-like services

Detailed reconstruction assumptions are in the STAGE*_REPORT.md files.

## Stage 8 reference geometry

For the default inner radius r=3 m:

    pavement height       0.75 m
    walkway height        1.80 m above invert
    walkway width         1.20 m
    walkway depth         0.12 m
    walkway side          right

    rail width            0.175 m
    rail depth            0.175 m
    rail centre spacing   1.50 m

Reference tube-like services include pipes, cables and power tracks. Their exact count/angular positions are not published by the paper, so the Stage-8 layout is explicit engineering configuration rather than hidden author-code reconstruction.

## Ancillary transform

Production default:

    gravity_stitched

Ancillary cross-sections pass through Stage-7.1 ring-centre offsets and share identical inter-ring boundary cross-sections. Pavement/rails/walkway/tubes do not spin with the independent segment-ring stagger angle.

A diagnostic literal mode is also implemented:

    paper_ring_rigid

See STAGE8_REPORT.md for the rationale.

## Semantic policies

Seg2Tunnel-like:

    0      clutter / all non-lining
    1..6   lining segments

STSD coarse:

    0  clutter
    1  segments
    2  walkway
    3  tubes

The Stage-8 generator defaults to STSD coarse.

## Generate a five-ring Stage-8 scene

    PYTHONPATH=src python examples/generate_stage8_tunnel.py --rings 5

Then verify in Blender:

    blender --background --python scripts/blender_verify_stage8.py -- \
        examples/stage8_tunnel_scene.json \
        --report examples/blender_stage8_runtime_report.json \
        --save-blend examples/stage8_tunnel_scene.blend

Expected five-ring scene:

    30 lining segments
    30 radial joints
    24 circumferential joint pieces
    90 bolt heads
    90 temporary pocket cutters
     5 pavement
     5 walkway
    10 rails
    30 tubes

    314 objects before Boolean processing
    180 Boolean operations
     90 cutters removed
    224 surviving objects

See STAGE8_BLENDER_SMOKE_TEST.md.

## Tests and CI

Install:

    python -m pip install -e '.[test]'

Run:

    pytest

Current regression result:

    113 tests passed

GitHub Actions additionally runs:

    scripts/verify_stage8_stress.py
    scripts/verify_stage8_trimesh.py

Latest successful Stage-8 verification:

    1,000 sampled Table-4 configs
    10,000 standalone ancillary meshes
    100 complete five-ring scenes
    31,400 full-scene objects
    20 JSON round-trips

    maximum inter-ring ancillary seam error:
    8.88e-16 m

    PASS

Independent trimesh 5.1.0 verification:

    250 sampled ancillary configs
    2,500 standalone ancillary meshes
    314 canonical five-ring scene objects
    0 failures

    PASS

## Source-fidelity notes

Stage 8 preserves the printed Table-4 bounds, including d_walk <= 0.34r.

The paper's prose and Table 4 disagree on whether l_rail is an offset from the centreline or total rail spacing. Both interpretations are implemented; the production default follows Table 4 and places rail centres at +/-l_rail/2.

The paper gives tube-radius bounds and says tube-like objects occupy predefined angular positions, but does not publish their count/angles. Those are explicit Stage-8 configuration values.

## Next validation gate

Before moving to virtual LiDAR/scanning, open the five-ring Stage-8 blend and visually confirm the pavement, walkway, rails, tube services and inter-ring continuity.
