# Stage 4 Report — Prescribed Joint Geometry

## 1. Scope

Stage 4 reconstructs the **prescribed (design) joint geometry** described in Section 2.2 of Yang et al. (2026), while preserving the displacement-induced joint-gap model completed in Stage 3.

This stage remains independent of Blender. The goal is to establish a tested geometric interpretation before introducing `bpy`, Boolean modifiers, object metadata, or bolt pockets.

Implemented in this stage:

- Table-2 joint dimensions and bounded sampling;
- paper-literal radial joint reconstruction;
- explicit hexahedral topology for each radial joint;
- a separately labelled **provisional** circumferential outer-collar reconstruction;
- OBJ / JSON export;
- unit tests and randomized stress verification.

Not implemented in this stage:

- Blender objects or modifiers;
- Boolean subtraction;
- bolt pockets / bolt heads;
- sensor-facing joint grooves not explicitly specified by the paper;
- coupling nominal joint solids to deformed segment transforms.

---

## 2. Published constraints used

Section 2.2 states that a prescribed joint has:

- width `w_joi = 35–60 mm`;
- thickness `t_joi = 45–75 mm`, explicitly described as **in addition to** `t_seg`;
- angular offset

```text
theta_joi = w_joi / R_joi
```

where the radial distance for the corresponding joint corner is either

```text
R_joi = r + t_seg
```

or

```text
R_joi = r + t_seg + t_joi.
```

Because Stage 1 uses

```text
R = r + t_seg
```

these two radii simplify to

```text
R0 = R
R1 = R + t_joi.
```

The paper also states that joints and segments share a hexahedral geometry and can be modelled by the same general procedure used for the eight-vertex lining blocks.

Reference:

- Yang, W. et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, Automation in Construction 187, 106924. DOI: 10.1016/j.autcon.2026.106924.

---

## 3. Radial joint reconstruction

### 3.1 Why the reconstructed radial joint is an outer rib

The two explicit `R_joi` values are both at or **outside the segment extrados**:

```text
R
R + t_joi
```

not at the intrados radius `r`.

Therefore the most literal interpretation of the published equation is a narrow hexahedral solid occupying the radial band

```text
R <= radius <= R + t_joi
```

and centred on the segment-to-segment interface.

Stage 4 calls this reconstruction:

```text
PAPER_LITERAL_OUTER_RIB
```

This is deliberately not renamed to a generic "joint groove", because the published radii do not support an intrados recess without changing the paper's equation.

### 3.2 Constant arc width

Let

```text
R0 = R
R1 = R + t_joi
```

Then the angular widths are

```text
Delta_alpha_0 = w_joi / R0
Delta_alpha_1 = w_joi / R1.
```

They are stored internally in degrees after evaluating the equation in radians.

The construction therefore satisfies exactly:

```text
R0 * Delta_alpha_0 = w_joi
R1 * Delta_alpha_1 = w_joi.
```

The angular span becomes slightly smaller on the larger radius, so the prescribed **arc width** is constant.

This is important: the equation in the paper defines an arc-length relationship, not an equal-angle relationship.

---

## 4. Interface location

For every cyclic pair

```text
K -> B1
B1 -> A1
A1 -> A2
A2 -> A3
A3 -> B2
B2 -> K
```

Stage 1 already supplies coincident undeformed boundary angles on each longitudinal face.

For the front face:

```text
alpha_joint,f = alpha_prev,end,f = alpha_next,start,f
```

and similarly for the back face.

The final `B2 -> K` interface requires normalizing the K start angle by an integer multiple of `360 deg`; the implementation performs this explicitly rather than relying on modulo equality.

This allows tapered front/back ring geometry to be preserved. If the interface angle differs between front and back, the joint hexahedron twists consistently with the Stage-1 segment boundaries.

---

## 5. Eight radial-joint vertices

Let

```text
y_f = -L_seg/2
y_b = +L_seg/2
```

and define

```text
h0 = Delta_alpha_0 / 2
h1 = Delta_alpha_1 / 2.
```

For front interface angle `a_f` and back interface angle `a_b`, the eight corners are reconstructed as:

```text
v0 = P(R0, a_f - h0, y_f)
v1 = P(R0, a_f + h0, y_f)
v2 = P(R0, a_b - h0, y_b)
v3 = P(R0, a_b + h0, y_b)

v4 = P(R1, a_f - h1, y_f)
v5 = P(R1, a_f + h1, y_f)
v6 = P(R1, a_b - h1, y_b)
v7 = P(R1, a_b + h1, y_b)
```

with the same coordinate convention as Stage 1:

```text
x = radius * sin(alpha)
z = radius * cos(alpha).
```

The face topology is the same closed six-quad hexahedral topology used for the base segment representation.

---

## 6. Consequence for LiDAR visibility

The literal reconstruction is significant because it exposes an important limitation in the paper specification.

A solid located entirely at

```text
radius >= R
```

is on the **extrados side** of the lining. A scanner inside the tunnel does not directly see this outer rib through the concrete segment.

Therefore Stage 4 does **not** infer a LiDAR-facing intrados groove from `w_joi` and `t_joi`.

Doing so would require changing the radial levels to something such as

```text
r ... r + depth
```

or

```text
r - depth ... r,
```

neither of which is stated in Section 2.2.

This distinction is now explicit in the API and exported JSON. A future sensor-facing groove can be introduced as a separate model, but it must be labelled as an engineering extension rather than a recovered Tunnel Scanner equation.

---

## 7. Circumferential joint: what can and cannot be recovered

The paper states that the circumferential joint:

- aligns with the `x-z` ring plane;
- links successive rings;
- uses the dimensions reported in Table 2.

However, it does **not** publish a circumferential counterpart to the radial-joint angular construction, nor an explicit eight-vertex formula.

Stage 4 therefore implements a separately named provisional mode:

```text
CIRCUMFERENTIAL_OUTER_COLLAR
```

For a selected front/back ring face, each segment gets one hexahedral collar piece with:

```text
radial range: R .. R+t_joi
axial range:  w_joi
angular range: the segment's corresponding front/back angular extent.
```

Six pieces tile the complete ring face once.

This is useful for geometry export and future Blender experiments, but the code and report deliberately do **not** claim that this is the authors' exact implementation.

---

## 8. Sampling

The paper says the Table-2 joint dimensions are sampled with Gaussian randomization inside the stated bounds, but does not publish the Gaussian standard deviation.

Stage 4 uses the same explicit policy adopted in Stage 1:

```text
nominal = range midpoint
sigma   = (high-low)/6
```

followed by rejection outside the hard bounds.

Thus an unconstrained centred Gaussian would place approximately 99.7% of samples inside the range while the implemented sampler guarantees the reported bounds.

This sampling policy is a reconstruction choice, not a value published by the authors.

---

## 9. Code added

New module:

```text
src/tunnel_scanner_core/joints.py
```

Core types:

```text
JointRangeM
JointBounds
JointConfig
JointReconstruction
RadialJointMesh
CircumferentialJointMesh
PrescribedJointSet
```

Core functions:

```text
sample_joint_config()
build_prescribed_radial_joints()
build_circumferential_outer_collar()
build_prescribed_joint_set()
```

New exporters:

```text
write_prescribed_joints_json()
write_prescribed_joints_obj()
```

The package version is advanced to `0.4.0`.

---

## 10. Automated tests

Final Stage-4 suite:

```text
43 passed
```

The new tests verify:

1. deterministic joint sampling;
2. Table-2 hard bounds;
3. the exact published relation `theta_joi=w_joi/R_joi`;
4. exact constant arc width at both explicit radii;
5. exact added radial thickness `t_joi`;
6. radial vertices occur only at `R` and `R+t_joi`;
7. all six cyclic interfaces are located correctly, including `B2 -> K` wrapping;
8. every radial-joint mesh is a closed two-manifold hexahedron;
9. winding is normalized to positive volume;
10. radial joints never intrude inside the segment outer radius beyond floating-point tolerance;
11. joint ribs remain mutually separated over randomized geometry;
12. provisional circumferential pieces have exact axial width;
13. circumferential pieces tile each ring face once;
14. all circumferential pieces are closed positive-volume hexahedra;
15. minimum/maximum Table-2 joint dimensions remain non-degenerate at `R=2 m` and `R=5 m`.

---

## 11. Stress verification

A comprehensive stress run generated:

```text
3000 default-geometry rings
1000 randomized-geometry rings
4000 total rings
```

Every case includes six radial joint meshes and both six-piece circumferential collars.

Results:

```text
max base arc-width error             1.39e-17 m
max cap arc-width error              1.39e-17 m
max added-thickness error            4.44e-16 m
min extrados radial clearance       -8.88e-16 m  (floating-point zero)
min angular clearance between ribs  16.48 deg
radial non-manifold meshes           0
radial non-positive-volume meshes    0
max circumferential tiling error     1.14e-13 deg
max circumferential axial-width err  5.55e-17 m
circumferential non-manifold meshes  0
circumferential non-positive volume  0
```

The smallest positive signed volumes were approximately:

```text
radial joint piece          0.00161 m^3
circumferential piece       0.00163 m^3
```

so no near-degenerate generated solids were encountered.

The randomized stress configuration uses the paper's broad `R=2..5 m` range. Because the paper does not publish a universal `t_seg` distribution, the stress script samples a separate conservative thickness band solely for software verification; it is not represented as an author-provided distribution.

---

## 12. Example seed 5812

For the Stage-4 example:

```text
w_joi = 0.0358320316 m
t_joi = 0.0591789622 m
R      = 3.35 m
R+t    = 3.4091789622 m
```

The corresponding radial-joint angular width is approximately:

```text
at R:       0.612843 deg
at R+t:     0.602205 deg
```

Both evaluate to the same prescribed arc width when multiplied by their respective radii.

The example OBJ contains:

- six base lining segments;
- six paper-literal radial-joint outer ribs;
- six provisional back-face circumferential collar pieces.

The front collar is omitted from the example OBJ only to reduce visual clutter; it is present in the JSON and API.

---

## 13. What Stage 4 establishes

The radial prescribed-joint construction can now be treated as stable at the pure-geometry level.

The strongest defensible reconstruction from the paper is:

```text
radial prescribed joint
    = hexahedral outer rib
    = R .. R+t_joi
    = constant arc width w_joi
```

The following remain explicitly unresolved:

1. whether the authors additionally generated an intrados-visible groove that is not documented by the printed `R_joi` equation;
2. the exact vertex construction of their circumferential joint;
3. how the prescribed joint object is attached or transformed when neighbouring segments receive different rigid deformations.

These uncertainties should not be silently resolved by guesswork.

---

## 14. Recommended Stage 5

The next stage should be the first **representation/back-end boundary**, not bolt Boolean geometry yet.

Recommended Stage 5 scope:

1. define an engine-neutral scene-object/semantic schema;
2. generate Blender-compatible Python from the already-tested meshes;
3. create one object per lining segment / radial joint / displacement joint;
4. attach stable `ringID`, `segmentID`, `labelID`, `objectType` metadata;
5. validate mesh orientation and object naming in an actual Blender runtime if one is available;
6. keep bolt pockets for the following stage, because Boolean operations add a new class of geometry failure.

The current execution environment does not contain a Blender executable or the `bpy` module, so Blender-runtime validation will require either a Blender-enabled environment or execution of the generated adapter script in a local Blender installation.
