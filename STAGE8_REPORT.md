# Stage 8 report — ancillary infrastructure

## Scope

Stage 8 reconstructs the ancillary-structure layer described in Section 2.4 and Table 4 of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, DOI 10.1016/j.autcon.2026.106924.

Implemented categories:

- pavement;
- walkway;
- two rail tracks;
- tube-like services: pipes, cables and power tracks.

As in the paper, ancillary geometry is intentionally coarser than the lining. Person and attachment are not modelled.

## Published Table-4 parameters

The implementation preserves the printed values and bounds:

| Parameter | Meaning | Reference | Bounds |
|---|---|---:|---:|
| h_pav | pavement height from invert | 0.25 r | 0.20 r – 0.30 r |
| h_walk | walkway height, Z | 0.60 r | 0.50 r – 0.60 r |
| w_walk | walkway width, X | 0.40 r | 0.40 r – 0.50 r |
| d_walk | walkway depth, Z | 0.04 r | 0.03 r – 0.34 r |
| s_walk | side | right | left / right |
| d_rail | rail depth, Z | 0.15–0.20 m | 0.10–0.50 m |
| w_rail | rail width, X | 0.15–0.20 m | 0.10–0.50 m |
| l_rail | rail spacing | 1.5 m | 1–2 m |
| r_tube | tube radius | 0.005 r – 0.05 r | 0.005 r – 0.05 r |

The unusual printed upper bound d_walk <= 0.34 r is preserved literally; it is not silently changed to 0.034 r. A separate physical-clearance validator rejects combinations where walkway/pavement or rail/intrados geometry is impossible.

## Reference configuration for r = 3.0 m

    pavement height     0.750 m
    walkway top height  1.800 m above invert
    walkway width       1.200 m
    walkway depth       0.120 m
    walkway side        right

    rail width          0.175 m
    rail depth          0.175 m
    centre spacing      1.500 m

The 0.175 m rail dimensions are midpoints of the paper's reference interval 0.15–0.20 m.

## Pavement reconstruction

The paper fixes pavement elevation but does not publish the full XZ polygon. Stage 8 reconstructs pavement as the circular segment between the intrados arc and a horizontal top chord:

    z_pav = -r + h_pav

The arc is adaptively tessellated with a coarse ancillary sagitta tolerance of 10 mm by default.

For r=3 m and h_pav=0.75 m:

    z_pav = -2.25 m

## Walkway reconstruction

The paper describes a quadrilateral prism attached horizontally to the intrados at h_walk. Stage 8 interprets h_walk as vertical height above invert:

    z_top    = -r + h_walk
    z_bottom = z_top - d_walk

The outer top/bottom vertices lie on the circular intrados. The inner vertices move horizontally toward the tunnel centre by w_walk.

Default right-side walkway:

    top z       -1.20 m
    bottom z    -1.32 m
    width        1.20 m
    depth        0.12 m

This interpretation is explicit metadata, not presented as unpublished author code.

## Rail-spacing ambiguity

Section 2.4 prose says rails are symmetrically offset from the midline by l_rail, while Table 4 describes l_rail as the spacing between rails. Those readings differ by a factor of two.

Both are implemented:

    TABLE4_CENTER_SPACING
        centres = +/- l_rail / 2

    PROSE_OFFSET_FROM_MIDLINE
        centres = +/- l_rail

The production/reference default follows Table 4. With l_rail=1.5 m, rail centres are x=-0.75 m and x=+0.75 m.

## Tube-like services

The paper gives tube radius bounds and says objects occupy predefined angular positions, but it does not publish the number of objects or angles.

The Stage-8 reference engineering layout is therefore explicit:

    pipe_right_upper          alpha  60 deg   radius 0.040 r
    power_track_right_mid     alpha  95 deg   radius 0.010 r
    cable_right_lower         alpha 110 deg   radius 0.008 r
    cable_left_lower          alpha 250 deg   radius 0.008 r
    power_track_left_mid      alpha 265 deg   radius 0.010 r
    pipe_left_upper           alpha 300 deg   radius 0.040 r

Each service circle is tangent to the intrados from inside:

    rho_centre = r - r_tube

The service count and angular positions are Stage-8 assumptions and are recorded as such.

## Sampling policy

Two modes exist:

    REFERENCE
    PUBLISHED_UNIFORM

REFERENCE returns the canonical values above.

PUBLISHED_UNIFORM samples all numerical Table-4 bounds uniformly, samples walkway side, and rejects physically invalid combinations. Tube radii are sampled within 0.005r–0.05r while the configured angular layout is retained.

## Continuous longitudinal alignment

A simple ring-local extrusion creates visible X/Z steps at ring interfaces after Stage 7.1 curvature/noise.

Stage 8 therefore gives every ancillary mesh at least three longitudinal stations:

    front
    centre
    back

In the production transform:

- the centre station passes through the current ring's Stage-7.1 X/Z centre offset;
- a shared boundary uses the midpoint between adjacent ring-centre offsets;
- neighbouring pieces therefore have identical boundary cross-sections.

Measured maximum inter-ring seam error in stress verification:

    8.881784197001252e-16 m

which is numerical floating-point noise.

## Axial ring-rotation ambiguity

Section 2.5 describes instantiated ring objects being translated/rotated during assembly. A literal application to ancillary structures would rotate pavement, rails and walkway around the tunnel axis with segment staggering.

Both interpretations are exposed.

GRAVITY_STITCHED is the production default:

- follows Stage-7.1 X/Z alignment;
- does not follow segment-ring axial stagger rotation;
- remains fixed in the gravity frame;
- stitches continuously between rings.

PAPER_RING_RIGID is the diagnostic literal pipeline reading:

- ancillary objects receive the same rigid axial rotation as the ring;
- continuous alignment stitching is disabled.

The selected policy is recorded on every object.

## Semantic policies

Seg2Tunnel-like:

    class 0     all non-lining / clutter
    classes 1–6 lining segments

STSD coarse:

    class 0  clutter
    class 1  segments
    class 2  walkway
    class 3  tubes

Under STSD coarse, pavement, rails, joints and bolts remain class 0. Pipes, cables and power tracks are all class 3.

The Stage-8 generator defaults to STSD coarse.

## Scene composition

One reference ring adds ten ancillary objects:

    1 pavement
    1 walkway
    2 rails
    6 tube-like services

Canonical five-ring scene with bolts:

    30 lining segments
    30 radial joints
    24 circumferential collar pieces
    90 bolt heads
    90 temporary pocket cutters
     5 pavement
     5 walkway
    10 rails
    30 tubes

    314 objects before Blender Booleans
    180 Boolean operations
     90 cutters removed
    224 surviving objects

Canonical thirteen-ring scene:

    78 lining segments
    78 radial joints
    72 circumferential collar pieces
    234 bolt heads
    234 temporary pocket cutters
     13 pavement
     13 walkway
     26 rails
     78 tubes

    826 objects before Blender Booleans
    468 Boolean operations
    234 cutters removed
    592 surviving objects

## Automated tests

Current regression suite:

    112 tests passed

Stage-8 tests cover Table-4 reference/bounds, the printed 0.34r depth bound, physical-clearance rejection, left/right walkway, pavement/rail geometry, both rail-spacing interpretations, tube containment, all three tube-like subtypes, manifold/positive volume, semantic policies, both ancillary transform policies, exact inter-ring stitching, centreline following, JSON round-trip and deterministic high-level assembly.

## Stress verification

Latest successful CI run:

    1,000 sampled Table-4 configurations
    10,000 standalone ancillary meshes
    100 complete five-ring scenes
    500 complete scene rings
    31,400 complete-scene objects
    5,000 ancillary scene objects
    20 JSON round-trips

Observed extrema:

    max sampled walkway depth     1.0176455393 m
    max rail vertex radius        2.6800219652 m
    max tube vertex radius        3.0000000000 m
    tunnel intrados radius        3.0000000000 m
    max inter-ring seam error     8.881784197e-16 m

    PASS

## Independent topology verification

A separate CI step uses trimesh 5.1.0. Production n-gon caps are fan-triangulated only inside the verifier because trimesh 5.x expects a homogeneous triangular face array.

Validation:

    250 sampled ancillary configurations
    2,500 standalone ancillary meshes
    314 canonical five-ring pre-Boolean objects
    failures: 0

All checked meshes are watertight, winding-consistent and positive-volume.

## Blender verification

Generate and verify:

    PYTHONPATH=src python examples/generate_stage8_tunnel.py --rings 5

    blender --background --python scripts/blender_verify_stage8.py -- \
        examples/stage8_tunnel_scene.json \
        --report examples/blender_stage8_runtime_report.json \
        --save-blend examples/stage8_tunnel_scene.blend

The verifier checks object counts, semantic IDs, transform policy, manifold/volume properties and inherited Stage-6 Boolean execution.

## Remaining limitations

Stage 8 remains intentionally coarse, as in the paper. It does not model sleepers/rail fasteners, power racks as separate geometry, pipe brackets, cable trays, or material/reflectance variation.

Per-ring ancillary pieces share coincident boundary cross-sections but remain separate closed objects to retain ringID metadata. Their coincident internal end caps are a deliberate representation trade-off.

## Status

The engine-neutral Stage-8 ancillary layer is complete and passes regression, stress and independent topology verification. The remaining validation gate is visual/runtime inspection in the user's Blender installation.
