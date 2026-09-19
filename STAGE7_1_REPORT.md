# Stage 7.1 report — physical-wavelength centreline correction

## 1. Why Stage 7.1 exists

The first real five-ring Blender scene exposed a scale problem in the Stage-7 engineering defaults.

Stage 7 correctly implemented the form of Yang et al. (2026) Eq. (21), including the published example amplitude A=0.1 m. However, because the paper does not publish numerical omega_x or omega_z values, Stage 7 chose frequencies from the number of exported rings:

    omega_x = 2*pi/(N_ring-1)
    omega_z = pi/(N_ring-1)

That made the physical curvature depend on export length.

For N_ring=5 and L_seg=1.35 m, adjacent ring centres could differ by roughly 0.10–0.13 m in X/Z. The Blender result was mathematically consistent with that temporary default, but it was not a good physical parameterization.

## 2. What remains paper-derived

Stage 7.1 does not change the published Eq. (21) structure or the displacement amplitude.

The working model remains:

    x = A*sin(phase_x) + epsilon_x
    y = chainage
    z = A*cos(phase_z) + epsilon_z

with:

    A = 0.1 m

as the example amplitude given in the paper.

The paper still does not provide numerical spatial frequencies. Therefore the smoothness scale remains an explicitly documented engineering choice.

## 3. Physical parameterization

Stage 7.1 evaluates the sinusoid by physical chainage:

    s_i = i*L_seg

    x_i = A*sin(2*pi*s_i/lambda_x) + epsilon_x
    z_i = A*cos(2*pi*s_i/lambda_z) + epsilon_z

Default reconstruction:

    lambda_x = 50 m
    lambda_z = 100 m

These are not claimed as author values.

They preserve the Stage-7 intent that vertical variation is lower-frequency than lateral variation, while making the same route invariant to the number of rings exported.

## 4. Default adjacent-ring displacement

For one coordinate with amplitude A, wavelength lambda and ring spacing L, the largest deterministic difference between adjacent samples is:

    Delta_max = 2*A*|sin(pi*L/lambda)|

For:

    A = 0.1 m
    L = 1.35 m
    lambda_x = 50 m
    lambda_z = 100 m

the bounds are:

    Delta_x,max = 0.0169442644 m
    Delta_z,max = 0.0084797575 m

A conservative combined transverse bound is:

    sqrt(Delta_x,max^2 + Delta_z,max^2)
    = 0.0189476749 m

So the sinusoidal component is now centimetre-scale from ring to ring rather than decimetre-scale.

## 5. Noise remains separate

The working reconstruction still interprets the paper's ambiguous printed noise notation as:

    sigma(epsilon_x) = sigma(epsilon_z) = 0.005 m

Noise is independent of the deterministic sinusoid, so an individual adjacent-ring displacement can exceed 18.95 mm.

For canonical seed 5812 in a five-ring scene, the largest observed transverse centre step including noise is about 21.0 mm.

The deterministic bound is therefore intentionally named as such in metadata.

## 6. Export-length invariance

This is the central Stage-7.1 invariant.

With zero noise, a five-ring scene and a thirty-ring scene generated with the same physical wavelength have exactly identical positions for their first five rings.

Stress verification measured:

    exportLengthInvarianceErrorM = 0.0

This removes the previous dependency of physical curvature on N_ring.

## 7. Compatibility

The original paper-style parameters remain available:

    omega_x_rad_per_ring
    omega_z_rad_per_ring

If either explicit override is provided, it takes precedence over the wavelength default.

This preserves exact reproduction of legacy Stage-7 centreline equations such as:

    x_i = A*sin(0.25*i)
    z_i = A*cos(0.4*i)

without forcing all downstream users onto the new default.

## 8. Metadata

Multi-ring ScenePackages now record:

    sourceStage = "7.1"
    frequencyParameterization
    lateralWavelengthM
    verticalWavelengthM
    omegaXRadPerM
    omegaZRadPerM
    omegaXRadPerRing
    omegaZRadPerRing
    deterministicAdjacentStepBoundXM
    deterministicAdjacentStepBoundZM
    deterministicAdjacentTransverseStepBoundM

The metadata explicitly states that 50 m / 100 m are engineering defaults because the paper does not publish frequency values.

## 9. CLI

examples/generate_stage7_tunnel.py now accepts:

    --lateral-wavelength-m
    --vertical-wavelength-m

Defaults:

    --lateral-wavelength-m 50
    --vertical-wavelength-m 100

## 10. Verification

Regression suite:

    95 tests collected
    95 passed

New Stage-7.1 tests verify:

- wavelength values are physical and independent of N_ring;
- first five deterministic positions are identical in 5-ring and 30-ring exports;
- adjacent deterministic displacement remains below the analytic bound;
- scene metadata carries the wavelength policy;
- explicit rad/ring overrides reproduce the legacy equation exactly.

Stress verification:

    2,000 pose scenes
    39,877 ring poses
    50 complete 5-ring scenes
    13,200 SceneObjects
    9,000 planned Boolean operations
    10 JSON round-trips

Measured:

    empirical axis-noise mean            0.0000236111 m
    empirical axis-noise std             0.0049952991 m
    configured sigma                     0.0050000000 m
    max Y-spacing error                  0.0 m
    max rigid-transform distance error   1.776e-15 m
    export-length invariance error       0.0 m

    deterministic X step bound           0.0169442644 m
    deterministic Z step bound           0.0084797575 m
    deterministic transverse bound       0.0189476749 m
    maximum observed deterministic step  0.0189475954 m

    PASS

## 11. Independent mesh validation

The canonical 13-ring scene was regenerated with the new positions.

A separate trimesh 4.11.1 pass checked all 696 pre-Boolean mesh objects after the new rigid world transforms:

    watertight             PASS
    winding consistent     PASS
    positive volume        PASS

No mesh topology changed in Stage 7.1.

## 12. Blender implications

Stage 7.1 does not change:

- local ring geometry;
- bolt pockets;
- bolt heads;
- Boolean target identity;
- object hierarchy;
- semantic IDs.

It only changes world X/Z translations.

The existing Stage-7 Blender verifier therefore remains valid. A new visual five-ring render should show the same tunnel/bolt structure but a much gentler centreline.

## 13. Status

Stage 7.1 is complete.

No additional theoretical investigation is required before the ancillary-infrastructure stage. The 50 m / 100 m wavelengths are deliberately configurable engineering defaults rather than claims about unpublished author parameters.
