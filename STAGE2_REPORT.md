# Stage 2 verification report — ring-wise joint deformation kinematics

## Scope

Stage 2 reconstructs and verifies the rigid-body ring-deformation model in Section 2.2 of:

Wanru Yang et al., *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, Automation in Construction 187 (2026) 106924, DOI 10.1016/j.autcon.2026.106924.

This stage remains Blender-independent. It implements the deformation state and closure solver but deliberately does **not** yet transform the Stage-1 segment meshes or create displacement-induced joint meshes, because the paper leaves the mapping from its recurrence state `O(i), theta_i` to final Blender object transforms under-specified.

## Source facts reproduced

Table 2:

- ring-wise radial dislocation: `d_i in [-10, +10] mm`;
- ring-wise segment rotation: `phi_i in [-0.3, +0.3] deg`.

Section 2.2 / Eqs. (5)-(11):

- K is the fixed reference at `i=0`;
- `O(0)=(0,0)`, `theta_0=pi`;
- deformation proceeds to `i=Nseg`;
- the final state `i=Nseg` is the displaced K-block used to close the ring;
- Eq. (11) requires `O(Nseg)=O(0)` and `theta_Nseg + theta_0 = 0`;
- the paper states that `d_(Nseg-1), d_Nseg, phi_Nseg` are the three closure unknowns and the remaining `2*Nseg-3` parameters are sampled.

## Indexing inconsistency found and reconstructed

The prose defines `d_i` and `phi_i` as the displacement/rotation of segment `i` relative to `i-1`, and the closure paragraph explicitly solves `d_(N-1), d_N, phi_N`.

However, printed Eqs. (6)-(10) apply `d_(i-1)` and `phi_(i-1)` at recurrence step `i`. If evaluated literally for `i=1..N`, the recurrence consumes indices `0..N-1`; consequently `d_N` and `phi_N` never enter Eq. (11). The stated set of closure unknowns is therefore impossible under the literal printed indexing.

Stage 2 adopts the minimal consistent reconstruction:

- recurrence step `i` consumes `d_i, phi_i`;
- the printed `i-1` deformation subscripts are treated as a systematic off-by-one typesetting/indexing error;
- an `AS_PRINTED_PREVIOUS_INDEX` diagnostic propagation path is retained in code so this assumption is explicit and testable.

This reconstruction is strongly supported by the prose and by the DoF count: for six segments, sample `d_1..d_4` and `phi_1..phi_5` (9 free DoFs), then solve `d_5, d_6, phi_6` (3 closure DoFs), for the stated total of 12 DoFs.

### Cross-check against cited reference [49]

Tunnel Scanner cites W. Lin et al. (2023), *Refined perception and management of ring-wise deformation information for shield tunnels based on point cloud deep learning and BIM*, as the basis for the simplified rigid-body deformation pattern. That paper independently states that a six-segment ring is determined by **12 rotation/dislocation parameters**, constrained by segment consistency, with rotation defined between adjacent segments and dislocation along the radial direction. This supports a one-rotation + one-dislocation parameterisation for each of the six segment positions and is consistent with the corrected `d_1..d_6`, `phi_1..phi_6` interpretation. It does not, however, provide enough algebra in the accessible text to resolve the later state-to-mesh transform by itself.

Reference: DOI 10.1201/9781003323020-490.

## Reconstructed traversal

Stage 1 uses cyclic topology:

`K, B1, A1, A2, A3, B2`

Because the paper fixes K at `i=0` and says the final `i=N` state is the displaced K-block, Stage 2 traverses:

`B1 -> A1 -> A2 -> A3 -> B2 -> K`

The six centre angles sum to 360 degrees regardless of the Stage-1 front/back taper interpretation.

## Exact closure solver

The implementation does not use a nonlinear optimiser.

Once `phi_1..phi_(N-1)` are sampled, angular closure reduces to:

`sum(phi_i) = 0`

because the segment centre angles already sum to 360 degrees. Therefore:

`phi_N = -sum(phi_1..phi_(N-1))`.

After rotations are fixed, `theta_i` is independent of all `d_i`, and Eqs. (6)-(10) are affine in every dislocation. Hence the remaining translation condition `O(N)=(0,0)` is a 2x2 linear system in `d_(N-1), d_N`.

The code constructs the exact two affine coefficient columns by unit probes and solves them with `numpy.linalg.solve`. Samples are rejected if the solved closure parameters leave the Table-2 bounds.

## Sampling assumption

The paper says the Table-2 bounds use Gaussian sampling but does not publish the Gaussian standard deviations. Stage 2 therefore uses a zero-mean truncated Gaussian with:

`sigma = bound / 3`

so the published hard bounds correspond to approximately +/-3 sigma before truncation. This is an engineering assumption, not a claimed recovery of unpublished author code.

## Verification

Automated tests include:

- zero-deformation exact closure;
- reconstructed segment traversal;
- deterministic seeded sampling;
- Eq. (11) closure and Table-2 bounds over 1000 seeds;
- exact final-rotation closure identity;
- numerical proof that translation is affine in dislocation for fixed rotations;
- diagnostic exposure of the printed-indexing inconsistency.

Additional stress tests performed during Stage 2:

- 10,000 default-geometry seeded deformations:
  - maximum sampling attempts: 28;
  - mean attempts: 3.5947;
  - median attempts: 3;
  - 99th percentile: 14 attempts;
  - maximum translation closure error: `1.405e-15 m`;
  - maximum angular closure error: `1.137e-13 deg`;
  - all emitted `|d_i| <= 10 mm`;
  - all emitted `|phi_i| <= 0.3 deg`.

- 2,000 additional random ring configurations with outer radius in 2-5 m and lining thickness in 0.2-0.6 m:
  - maximum sampling attempts: 40;
  - maximum translation closure error: `1.999e-15 m`;
  - maximum angular closure error: `1.137e-13 deg`.

## Important interpretation of O(i)

The paper calls `O(i)` a segment-centroid coordinate, yet sets `O(0)=(0,0)`. Under Eqs. (6)-(10), if all dislocations and rotations are zero, every `O(i)` also remains `(0,0)`. Therefore it cannot simultaneously be the absolute polar coordinate of each physical segment centroid around the ring.

Stage 2 treats `O(i)` as the recurrence's cumulative in-plane rigid-body offset state (or equivalently a local ring-centre/segment-reference offset), not as an absolute physical centroid coordinate. This is sufficient for solving Eq. (11), but the exact mapping of that state onto Blender segment meshes is not explicitly published.

## Decision before Stage 3

The mathematical closure solver is ready. Before applying these states to actual Stage-1 vertices and generating displacement-induced joint meshes, the state-to-mesh transform needs a separate derivation/validation against Fig. 3(c)-(d) and, ideally, author clarification or visual reproduction checks.
