# Stage 1 verification report

## Goal

Build and verify a Blender-independent mathematical core for one undeformed six-segment Tunnel Scanner ring before introducing joints, displacement, booleans, or sensor simulation.

## Source facts implemented

- Six-segment ring consists of one K-block, two B-blocks and three A-blocks.
- Each base segment is described as a hexahedron with eight vertices and twelve edges.
- Front surface uses corners 0-1-4-5 and back surface corners 2-3-6-7.
- Centre angle is the mean of front/back angles (Eq. 2).
- Each face must close to 2π (Eq. 3).
- B transition continuity is imposed by Eq. 4.
- Default ring ranges and empirical `L_seg/t_seg` relation come from Table 1.

## Engineering choices made in Stage 1

1. Cyclic order is `K, B1, A1, A2, A3, B2`, placing one B-block on each side of the K-block.
2. K is centred at the crown on each face.
3. The baseline sampler keeps all A-blocks mutually equal and both B-blocks mutually equal. The paper permits a more general per-block randomisation; that is deferred until the exact intended constraint treatment is resolved.
4. Mesh faces are planar quads between the eight published corner points. Cylindrical tessellation is intentionally deferred because the paper explicitly calls the base element a hexahedron.

## Verification performed

- 1000 deterministic seeds sampled in equation-consistent mode.
- Every sample satisfies 360-degree front, back and centre closure.
- Every sample satisfies Eq. (4) for B1 and B2.
- All sampled angles remain inside Table-1 bounds.
- Literal mode confirms the algebraic consequence `K_f == K_b`.
- Mesh topology is six independent hexahedra, each with 8 vertices and 6 quad faces.
- Inner/outer corner radii and front/back Y planes are numerically checked.
- Export is deterministic and uses no Blender dependency.

## Open questions before deformation implementation

The deformation section has a second indexing ambiguity: Eqs. (6)-(10) update step `i` using `d_(i-1), phi_(i-1)`, while the prose later says the three closure unknowns are `d_(Nseg-1), d_Nseg, phi_Nseg`. A literal recurrence to `i=Nseg` never consumes both `d_Nseg` and `phi_Nseg`. This must be resolved or represented by an explicit interpretation before Stage 2.
