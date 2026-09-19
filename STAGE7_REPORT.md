# Stage 7 report — multi-ring tunnel assembly

## 1. Scope

Stage 7 moves from one verified ring to a complete longitudinal tunnel scene. It implements the scene-construction model around Eq. (21) of Yang et al. (2026), while preserving all Stage 1–6 geometry and semantic metadata.

This stage deliberately does **not** add rails, walkway, drainage, cables, pipes, scanner trajectories, or material/reflectance physics. Its responsibility is the ring-level world transform and deterministic assembly of a physically coherent sequence of ring packages.

## 2. Source model implemented

For ring index i, Eq. (21) defines:

    x_i = A*sin(omega_x*i) + epsilon_x
    y_i = i*L_seg
    z_i = A*cos(omega_z*i) + epsilon_z
    phi_i = phi + delta_i

The paper gives:

- example displacement amplitude A = 0.1 m;
- ring-count bounds N_ring = 10..30 in Table 1;
- stagger-angle bounds phi_s = -6*theta_K .. +6*theta_K in Table 2;
- delta_i ~ N(0, (0.1*phi)^2);
- epsilon_x, epsilon_z ~ N(0, 0.005 m^2) as printed.

The paper does **not** publish numerical omega_x or omega_z values and does not completely specify how the nominal stagger angle phi changes from ring to ring.

## 3. Coordinate transform

Every Stage-5/6 SceneObject remains expressed in a local ring frame until Stage 7. The world-space transform is:

    p_world = R_y(phi_i) * p_ring + T_i

where R_y rotates about the tunnel longitudinal axis +Y.

The transform is rigid. It does not alter mesh connectivity, segment dimensions, bolt geometry, semantic IDs, or Boolean target names.

## 4. Ring spacing

The local ring mesh spans y=[-L_seg/2,+L_seg/2], while Eq. (21) places ring centres at y_i=i*L_seg. Therefore ideal adjacent rings meet at their longitudinal boundary before lateral axis perturbations are considered.

For the default L_seg=1.35 m, the canonical 13-ring scene spans 17.55 m from the first front face to the last back face.

## 5. Axis-noise ambiguity

The paper prints epsilon_x,epsilon_z ~ N(0,0.005 m^2). Interpreted literally as variance, sigma is about 70.7 mm. Because the prose calls these perturbations small, Stage 7 uses an explicit working reconstruction:

    sigma_axis = 0.005 m

This is configurable and recorded in ScenePackage metadata.

Stage 7 does not recenter Eq. (21) offsets by default. Raw equation values are preserved. Optional lateral recentering is available as a pure global X/Z translation and is explicitly recorded if used.

## 6. Unspecified spatial frequencies

The paper publishes symbols omega_x and omega_z but no numeric values. Stage 7 exposes both parameters. If omitted, explicit engineering defaults are:

    omega_x = 2*pi/(N_ring-1)
    omega_z = pi/(N_ring-1)

This produces one complete lateral sine wave and one half-wave vertical cosine variation. These defaults are marked as reconstruction assumptions in metadata.

## 7. Staggered-ring ambiguity

A literal interpretation of phi_i=phi+delta_i with one constant phi for every ring does not create much deliberate ring-to-ring stagger apart from delta_i.

Stage 7 exposes three strategies:

### CONTINUOUS

    phi_i = 0

### PAPER_CONSTANT_NOMINAL

A literal/common-phi reading with one nominal phi for the complete scene.

### RINGWISE_GAUSSIAN

Production staggered reconstruction:

    phi_nominal_i ~ truncated Gaussian within +/-6*theta_K
    delta_i ~ N(0, (0.1*|phi_nominal_i|)^2)
    phi_i = phi_nominal_i + delta_i

This is consistent with Table 2 describing the stagger bounds as Gaussian sampled and actually produces inter-ring joint staggering. The CLI generator uses this mode by default, while the low-level TunnelAssemblyConfig defaults to continuous joints.

The nominal sampled angle is constrained to the published bound. The final angle can slightly exceed that bound because delta_i is an additional imperfection term.

## 8. Scene composition

build_multi_ring_scene_package() merges already-built ring packages without renaming their stable ring-local objects. Names already contain R####, so no collisions occur.

Every transformed object receives:

    ringTranslationX
    ringTranslationY
    ringTranslationZ
    ringRotationDeg
    ringNominalRotationDeg
    ringAngularImperfectionDeg
    ringChainageM

The package also stores a complete ringPoses record.

## 9. High-level procedural builder

build_procedural_nominal_tunnel() composes:

    per-ring angle sampling
        -> ring mesh
        -> prescribed joints
        -> optional Stage-6 bolts
        -> local ScenePackage
        -> Stage-7 Eq. (21) world pose
        -> one multi-ring ScenePackage

A single master seed deterministically derives independent sub-seeds for ring angles, joints, bolt dimensions, bolt perturbations, and tunnel assembly.

## 10. Circumferential interface count

For an actual sequence of N rings there are only N-1 inter-ring interfaces. The Stage-7 high-level builder therefore omits the terminal back circumferential joint by default.

For 13 rings:

    12 circumferential interfaces
    72 circumferential collar pieces

## 11. Multi-ring Boolean bug found and fixed

Stage 6 keyed Boolean operations only by boltIndex, which was safe for one ring because bolt indices are local to the ring.

In a multi-ring scene every ring contains bolt indices 0..17, so the original planner saw duplicates.

Stage 7 fixes Boolean identity to:

    (ringID, boltIndex)

and includes ringID in BoltBooleanOperation.

A canonical 13-ring Type-1 bolt scene therefore has:

    234 bolt heads
    234 pocket cutters
    468 planned Boolean operations

without ID collisions.

## 12. Canonical 13-ring scene

Seed 5812:

    rings                         13
    ring width                     1.35 m
    scene length                  17.55 m
    lining segments                78
    radial joint objects           78
    circumferential joint pieces   72
    bolt heads                     234
    pocket cutters                 234
    objects before Blender         696
    expected Boolean operations    468
    expected surviving objects     462

Default reconstructed frequencies:

    omega_x = 0.5235987756 rad/ring
    omega_z = 0.2617993878 rad/ring

## 13. Automated verification

Regression suite:

    92 tests collected
    92 passed

Stage-7 tests cover exact Eq. (21), source N_ring bounds, raw Eq. (21) default, seeded determinism, all rotation strategies, stagger bounds, exact Y spacing, rigid transform preservation, unique IDs, metadata propagation, JSON round-trip, N-1 circumferential interfaces, multi-ring Boolean planning, and high-level build determinism.

Stress verification:

    2,000 pose scenes
    39,877 ring poses
    50 full 5-ring scenes
    250 full-scene rings
    13,200 SceneObjects
    9,000 planned Boolean operations
    10 full JSON round-trips

Measured:

    empirical epsilon mean       0.00002361 m
    empirical epsilon std        0.00499530 m
    configured sigma             0.00500000 m
    max Y-spacing error          0.0 m
    max rigid-distance error     1.78e-15 m
    max nominal stagger          134.9018 deg
    published nominal bound      135.0 deg

    PASS

Independent mesh validation: trimesh 4.11.1 reports all 696 mesh objects in the canonical 13-ring pre-Boolean scene as watertight, winding-consistent, and positive-volume.

## 14. Blender verification

Stage 6 already passed a real Blender visual/Boolean smoke test. Stage 7 adds a dedicated multi-ring verifier because the Boolean planner changed from a local to a (ringID,boltIndex) key.

Recommended quick test:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_runtime_report.json \
        --save-blend examples/stage7_tunnel_scene.blend

For five Type-1 rings:

    ring count                    5
    pre-Boolean objects         264
    bolt heads                   90
    pocket cutters               90
    Boolean operations          180
    removed cutters              90
    surviving objects           174

## 15. Deliberate limitations

Stage 7 follows Eq. (21) literally in one important respect: ring axes remain parallel to global +Y. Rings are translated laterally/vertically but are not tilted to the local centreline tangent.

This can create small geometric steps at circumferential interfaces when the S-curve changes between adjacent rings. It is not silently corrected because Eq. (21) publishes translations and axial ring rotation, not pitch/yaw orientation of ring planes.

A future alignment-aware extension can introduce a transported local frame, but it should remain separate from reproduction of the paper's scene model.

## 16. Stage status

The engine-neutral multi-ring assembly is ready and all changes are in GitHub.

The only external validation gate before Stage 8 is the real Blender Stage-7 multi-ring smoke test. Once that passes, the next logical stage is ancillary infrastructure driven along the tunnel alignment: pavement/walkway, rails, and tube-like services.
