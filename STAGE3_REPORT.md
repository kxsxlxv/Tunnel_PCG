# Stage 3 Report — Mapping Ring-Wise Deformation to Physical Segment Geometry

## 1. Scope

Stage 3 addresses the unresolved problem left at the end of Stage 2: how to convert the recurrence state

- `O^(i)`
- `theta_i`
- `d_i`
- `phi_i`

into actual rigid transformations of the eight-vertex segment meshes created in Stage 1.

No Blender-specific code is introduced. The purpose is to establish a geometry model whose invariants can be tested independently of `bpy`, Boolean modifiers, tessellation, or scanning.

---

## 2. Reinterpretation of `O_i`

The Stage-2 report provisionally described `O_i` as a cumulative offset / centroid-like state because the Tunnel Scanner text calls it a centroid. That wording is not geometrically consistent with the recurrence: in the undeformed case every `O_i` remains at the origin.

Inspection of the source ring-wise deformation model cited by Tunnel Scanner resolves this. The deformation diagram uses points such as `O_B1` and `O_L1` as the centers from which the corresponding rigid circular segment arcs are constructed. Therefore Stage 3 interprets `O_i` as the **local center of curvature (local ring center)** for segment `i`.

This interpretation has the required undeformed limit:

```text
d_i = 0 and phi_i = 0  ->  O_i = (0, 0) for every segment
```

which is exactly what a concentric undeformed ring requires.

---

## 3. Index reconstruction

Tunnel Scanner defines `d_i` and `phi_i` as the dislocation and rotation of segment `i` relative to segment `i-1`, and its closure discussion solves for terminal values including `d_N` and `phi_N`.

The printed Eqs. (6)–(10), however, use `d_(i-1)` and `phi_(i-1)` in the step from state `i-1` to state `i`. Taken literally, the final `d_N` and `phi_N` cannot influence the closure equation.

Stage 3 therefore retains the Stage-2 **segment-indexed reconstruction**:

```text
step i consumes d_i, phi_i
```

The literal printed-index implementation remains available as a diagnostic mode.

---

## 4. Rotation-sign reconstruction

A second inconsistency becomes visible only when the recurrence is mapped to actual rigid geometry.

The published positional update actively rotates the translated local center by the segment rotation angle. If the shared interface point is to remain a common pivot during a pure segment rotation, the corresponding radial/interface orientation must rotate in the same direction.

That yields the geometry-consistent update:

```text
theta_i = theta_(i-1) - alpha_i + phi_i
```

where `alpha_i` is the mean angular span of segment `i`.

The printed equation uses `-phi_i` (after correcting only the index). That version fails the common-pivot invariant for a pure rigid rotation.

For transparency the code exposes three conventions:

1. `CORRECTED_SEGMENT_INDEXED`
   - `d_i, phi_i`
   - geometry-consistent `+phi_i`
   - used for generated geometry.

2. `INDEX_CORRECTED_PRINTED_SIGN`
   - `d_i, phi_i`
   - printed `-phi_i`
   - diagnostic only.

3. `AS_PRINTED_PREVIOUS_INDEX`
   - previous-index consumption
   - printed sign
   - diagnostic only.

---

## 5. Coordinate-system mapping

Stage 1 represents the tunnel cross-section in the `XZ` plane with the parameterization

```text
x = r sin(alpha)
z = r cos(alpha)
```

so `alpha = 0` is the crown (`+Z`) and increasing `alpha` moves toward `+X`.

The deformation recurrence uses a conventional planar vector

```text
(cos(theta), sin(theta))
```

and initializes `theta_0 = pi` at the K-to-B1 interface.

A constant planar basis rotation maps recurrence coordinates to the Stage-1 mesh coordinates. For the sampled Stage-1 geometry it is obtained from the undeformed B1 entry boundary:

```text
delta = -90 deg - alpha_B1_entry
```

All recurrence-space local centers and rotation centers are transformed through this same basis rotation.

---

## 6. Segment rigid transform

For target segment `i`, the recurrence yields:

- the local center `O_i`;
- a shared joint/pivot construction point;
- the accumulated orientation.

The resulting physical segment transform is represented as:

```text
p_deformed = R(gamma_i) p_undeformed + t_i
```

where:

- `gamma_i` is the accumulated segment rotation;
- `t_i` is determined by the mapped local center / pivot geometry.

The fixed initial K block uses identity transform.

For the geometry-consistent convention:

```text
gamma_B1 = phi_1
gamma_A1 = phi_1 + phi_2
...
gamma_B2 = sum(phi_1 ... phi_5)
```

and the repeated terminal K block returns to zero rotation because closure enforces:

```text
sum(phi_1 ... phi_6) = 0
```

The position closure solver from Stage 2 simultaneously returns the repeated K local center to the origin.

---

## 7. Displacement-induced joint gaps

Stage 3 introduces explicit joint bridge meshes between the deformed end face of one segment and the deformed start face of its neighbor.

These are **not yet the nominal construction joints** parameterized in the paper by `w_joi` and `t_joi`. They represent the geometric opening/offset caused by the relative rigid transforms only.

Each bridge is a hexahedral shell joining four corresponding boundary vertices:

```text
previous segment end face  <->  current segment start face
```

Topology is normalized so every joint bridge is a closed two-manifold:

- 8 vertices;
- 6 quad faces;
- 12 unique edges;
- every edge used exactly twice.

Face winding is normalized through signed-volume checks.

---

## 8. Geometric invariants

The Stage-3 test suite verifies the following invariants.

### 8.1 Zero-deformation identity

With every `d_i = 0` and `phi_i = 0`:

- every physical segment transform is identity;
- every deformed vertex equals its Stage-1 vertex;
- all displacement-induced joint gaps have zero separation.

### 8.2 Rigid-distance preservation

For every segment and every pair of its vertices:

```text
||p_a - p_b|| before == ||p_a - p_b|| after
```

within floating-point tolerance.

### 8.3 Relative rotation recovery

For every adjacent pair the recovered relative rigid rotation equals the sampled `phi_i`, including the terminal closure step back to K.

### 8.4 Pure rotation pivot

For `d_i = 0`, applying a nonzero `phi_i` leaves the shared mean-radius joint pivot invariant.

This invariant is satisfied by the `+phi` reconstruction and fails under the printed-sign diagnostic convention.

### 8.5 Pure dislocation separation

For `phi_i = 0` and a single imposed radial `d_i`, corresponding joint boundary points separate by the prescribed radial displacement magnitude (within floating-point tolerance).

### 8.6 Closure

The repeated terminal K transform returns to:

```text
translation = (0, 0)
rotation = 0
```

within numerical precision.

---

## 9. Automated test results

Final test run:

```text
31 passed
```

The suite includes both deterministic unit cases and randomized runs.

---

## 10. Stress verification

### Full geometry stress test — default geometry

3,000 generated rings:

```text
max translational closure error     1.1957467920563633e-15 m
max angular closure error           1.1368683772161603e-13 deg
max repeated-K translation error    1.1957467920563635e-15 m
max repeated-K rotation error       1.1368683772161603e-13 deg
max relative-rotation recovery err  1.5652756868433926e-13 deg
max rigid edge-length error         1.3322676295501878e-15 m
non-manifold joint meshes           0
negative-winding joint meshes       0
mean rejection-sampling attempts    3.5823
99th percentile attempts            ~14
maximum attempts                    28
```

The largest generated joint-corner displacement in this run was approximately `10.22 mm`, consistent with the sampled deformation envelope and rotation contribution.

### Randomized geometry stress test

1,000 rings with randomized Stage-1 geometry:

```text
max translational closure error     1.9860273225978185e-15 m
max repeated-K translation error    1.9860273225978185e-15 m
max repeated-K rotation error       1.1368683772161603e-13 deg
maximum rejection attempts          36
```

### Closure-only extended stress test

10,000 generated rings:

```text
max translational closure error     1.3322676295501878e-15 m
max angular closure error           1.1368683772161603e-13 deg
max repeated-K translation error    1.3322676295501878e-15 m
max repeated-K rotation error       1.1368683772161603e-13 deg
mean rejection-sampling attempts    3.599
99th percentile attempts            14
maximum attempts                    24
```

---

## 11. Example seed 5812

For seed `5812`, the mapped physical segment rotations are approximately:

```text
K    0.000000 deg
B1   0.127659 deg
A1   0.036541 deg
A2   0.158041 deg
A3   0.100606 deg
B2   0.095222 deg
K*   0.000000 deg  (closure copy)
```

The terminal repeated K transform closes to approximately `5e-16 m` translation and zero rotation.

The example OBJ includes the six deformed lining blocks plus displacement-induced joint bridge meshes.

---

## 12. What Stage 3 supersedes from Stage 2

Two Stage-2 interpretations are superseded:

1. `O_i` should not be described as a physical concrete-segment centroid. It is treated as a local center of curvature / local ring center.
2. The geometry-generating recurrence uses the reconstructed `+phi_i` orientation update; the old printed-sign variant is retained only for diagnostics.

The exact 2x2 closure strategy developed in Stage 2 remains valid because the angular closure condition still gives

```text
phi_N = -sum(phi_1 ... phi_(N-1))
```

and, after rotations are fixed, the displacement equations remain affine in the final two unknown dislocations.

---

## 13. Remaining uncertainty before Blender

The largest unresolved geometry issue is no longer the deformation mapping. It is the **nominal construction joint**.

Tunnel Scanner gives:

- joint width `w_joi`;
- joint thickness/depth `t_joi`;
- an angular conversion using `theta_joi = w_joi / R_joi`;
- two possible radii involving the lining radius and joint depth.

However, the exact eight-corner construction and its relationship to the adjacent lining intrados/extrados are not sufficiently explicit in the text alone to justify silently choosing one topology.

Therefore Stage 4 should begin with a narrow reconstruction/verification of the nominal joint wedge before introducing Blender objects and Boolean operations.

---

## 14. Stage status

**Stage 3 mathematical/mesh deformation core: complete.**

**Recommended next action:** resolve the nominal `w_joi / t_joi` joint construction, then move to Blender integration.
