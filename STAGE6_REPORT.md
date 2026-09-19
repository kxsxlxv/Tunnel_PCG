# Stage 6 report — bolt pockets, heads, and Blender Boolean embedding

## Scope

Stage 6 reconstructs Section 2.3 of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, DOI 10.1016/j.autcon.2026.106924.

The stage is deliberately split into two layers:

1. engine-neutral bolt geometry that can be numerically verified without Blender;
2. a Blender adapter that performs the actual cavity/head Boolean embedding.

Ancillary structures, multi-ring assembly, and LiDAR scanning remain outside this stage.

## Source geometry implemented

Table 3 dimensions are represented in metres with hard bounds:

| Parameter | Bounds |
|---|---:|
| pocket top width `w_t` | 70–90 mm |
| pocket bottom width `w_b` | 100–150 mm |
| pocket height `h_p` | 150–160 mm |
| penetration `p` | 110–120 mm |
| head radius `r_bolt` | 20–40 mm |
| head thickness `t_bolt` | 80–90 mm |
| protrusion `s` | 10–15 mm |
| joint arc offset `l_arc` | 180–230 mm |
| longitudinal offset `y_off` | 400 mm |

The implementation also reproduces:

- Eqs. (12)–(16): bolt surface point and local orthonormal frame;
- Eq. (17): four trapezoidal pocket-mouth vertices;
- Eq. (18): pocket-base centroid;
- Eq. (19): `d = p + s`;
- Eq. (20): tapered-pyramid apex, with the sign issue discussed below;
- Algorithm 1 face normal construction;
- a 12-vertex top ring and 12-vertex embedded ring;
- `r_bb = 0.7*r_bolt`;
- all three Table-3 placement families.

## Explicit reconstruction issues found in the paper

### 1. Eq. (20) apex sign

The paper defines `n` as the outward radial normal, away from the ring centroid, and states that the pyramid apex is embedded in the lining.

For an intrados surface, moving into the concrete therefore requires a positive radial displacement. Printed Eq. (20) instead uses:

```text
v4 = C - d(1+eps_d)n + eps_l*w_b*e_x
```

which moves the apex toward the tunnel void.

Stage 6 exposes both conventions:

```text
PHYSICAL_EMBEDDED
PAPER_PRINTED_INWARD_APEX
```

Production geometry uses `PHYSICAL_EMBEDDED`:

```text
v4 = C + d(1+eps_d)n + eps_l*w_b*e_x
```

The printed sign is retained as a diagnostic mode.

### 2. Algorithm 1 line 5 is dimensionally inconsistent

The printed expression is equivalent to:

```text
P_bolt = c + eta*|v4-c|*a_c + n_bolt
```

where `P_bolt` is a metric coordinate but `n_bolt` is a unit vector. A length multiplier is missing.

Table 3 separately defines `s` as the head protrusion toward the tunnel centre. Stage 6 therefore uses the dimensionally consistent reconstruction:

```text
P_top = c + eta*(v4-c) - s*n_bolt
```

The minus sign follows the paper's own outward definition of the pocket normal: tunnel-centre direction is inward.

### 3. The paper does not publish eta

Algorithm 1 accepts a relative height ratio `eta`, but Table 3 and the surrounding text do not publish a numeric value or range.

Stage 6 therefore makes it a normal configuration parameter:

```text
head_height_ratio = 0.35
```

This is an explicit engineering assumption intended to keep the head visibly recessed while remaining well inside the lining. It is recorded in ScenePackage metadata and is not presented as recovered author code.

### 4. Pocket perturbation notation is ambiguous

The paper describes the perturbations as small/bounded but prints:

```text
N(0, 0.001 m^2)
```

Interpreting the second parameter literally as variance would give a standard deviation of about 31.6 mm, inconsistent with "small" perturbations.

Stage 6 uses:

```text
metric sigma = 1 mm
relative sigma = 0.001
truncation = +/-3 sigma
```

The policy is configurable and written into scene metadata.

## Placement reconstruction

The generator implements all three Table-3 layouts.

### Type 1 — centred

For every segment:

```text
alpha = segment centre
y = -0.4, 0, +0.4 m
```

For a six-segment ring this gives 18 assemblies.

### Type 2 — lateral

For each segment:

```text
alpha = segment centre +/- theta_K
y = -0.4, +0.4 m
```

Candidates are retained only when they lie on the declared segment. For the six-segment geometry used here, the small K segment does not own valid Type-2 candidates, giving 20 assemblies.

### Type 3 — joint aligned

For each radial joint:

```text
delta_alpha = l_arc / R_outer
alpha_previous = alpha_joint - delta_alpha
alpha_next     = alpha_joint + delta_alpha
y = -0.4, +0.4 m
```

This yields 24 assemblies per ring.

## Curved-intrados Boolean correction

The original paper's pocket mouth is a planar trapezoid coplanar with the lining surface. That works with the paper's coarse planar segment representation.

Stage 5.1 replaced the intrados with a true curved cylindrical tessellation. A tangent-plane mouth would therefore touch the cylinder only near its centre and is a poor Boolean cutter.

The analytical pocket is left unchanged. A separate `BoltBooleanCutterMesh` moves only the four mouth vertices 5 mm toward the tunnel void:

```text
v_mouth_boolean = v_mouth - 0.005*n
```

The apex and penetration depth remain unchanged.

Across 1,000 random rings, the worst cutter mouth still crossed the intrados by at least about 4.064 mm, so all tested cutters had a genuine volume overlap with the curved lining.

## Scene representation

A Stage-6 nominal ScenePackage contains:

```text
6 curved lining segments
6 prescribed radial joints
6 circumferential collar pieces
18 pocket Boolean cutters
18 visible bolt heads
--------------------------------
54 objects before Blender Booleans
```

Bolt objects use `labelID=0`, matching the Seg2Tunnel clutter convention described by the paper.

Each cutter/head records:

```text
boltIndex
boltLayout
boltAlphaDeg
boltYM
booleanTarget
booleanOperation
segmentID
ringID
labelID
```

The package also records all reconstruction assumptions.

## Blender Boolean pipeline

For each bolt, operations are deterministic:

```text
1. lining segment DIFFERENCE pocket cutter
2. lining segment DIFFERENCE bolt head
3. delete pocket cutter
4. retain bolt head as visible labelID=0 object
```

The adapter requests Blender's Exact Boolean solver when available.

The second subtraction guarantees that the retained bolt head does not geometrically overlap the lining even if its sloping truncated-cone geometry extends beyond the ideal pocket boundary.

For a Type-1 ring:

```text
18 pocket cuts
18 head seating cuts
36 Boolean operations
18 cutter objects removed
36 objects survive
```

## Semantic limitation relative to the paper

The paper describes a second Boolean reconstruction intended to make the recessed pocket geometry independently labelable as clutter.

Stage 6 currently prioritises physically correct visible geometry:

- the cavity wall is part of the lining segment object and therefore retains the segment's label;
- the bolt head is clutter class 0;
- the temporary pocket cutter is deleted.

A separate clutter-labelled pocket-wall shell is **not yet reconstructed** because the exact author object/Boolean sequence is not specified sufficiently to reproduce it without risking a geometry that fills or occludes the cavity.

This limitation is explicitly written into ScenePackage metadata.

## Automated validation

### Regression suite

After Stage 6:

```text
75 tests collected
75 passed
```

New tests cover:

- Table-3 bounds across 1,000 sampled configurations;
- all three placement modes;
- ownership of Type-2/Type-3 placements;
- orthonormal pocket frames;
- Eq. (20) sign diagnostic;
- positive-volume/manifold pocket and head meshes;
- 12+12 truncated-cone dimensions;
- deterministic and bounded perturbations;
- Boolean mouth overlap;
- ScenePackage metadata and semantic IDs;
- deterministic pocket-before-head Boolean planning.

### Stress verification

`scripts/verify_stage6_stress.py` was run over:

```text
1,000 rings
18,000 Type-1 bolt assemblies
100 rings with full topology/volume checks
all three layout counts checked on every ring
```

Observed values:

```text
Type 1 count: 18
Type 2 count: 20
Type 3 count: 24

max pocket depth          = 0.13384377 m
lining thickness          = 0.35000000 m

max head vertex radius    = 3.10746688 m
outer lining radius       = 3.35000000 m

minimum cutter overlap
into tunnel void          = 0.00406394 m

max sampled metric
pocket perturbation       = 0.00299705 m
```

All tested heads remained inside the lining outer radius.

### Independent mesh-library validation

A separate `trimesh 4.11.1` check triangulated and examined 600 pocket/head/cutter meshes sampled across 100 rings.

All 600 were:

- watertight;
- winding-consistent;
- positive-volume.

## Real-Blender verification

A Blender runtime is not available in the current execution environment, so actual Boolean execution remains an external validation item.

Use:

```bash
PYTHONPATH=src python examples/generate_stage6_scene.py

blender --background --python scripts/blender_verify_stage6.py -- \
    examples/stage6_nominal_bolts_scene.json \
    --report examples/blender_stage6_runtime_report.json \
    --save-blend examples/stage6_nominal_bolts_scene.blend
```

The verifier checks:

- 36 Boolean operations were applied;
- all 18 pocket cutters were deleted;
- all 18 bolt heads remain with `labelID=0`;
- every lining segment changed topology;
- every resulting lining segment is manifold;
- every resulting lining segment has positive signed volume.

## Status

The engine-neutral Stage-6 bolt geometry is ready.

The next project stage should not begin until the real Blender Boolean verifier passes, because failures at this point would be Blender-kernel/runtime issues rather than unresolved analytical geometry.
