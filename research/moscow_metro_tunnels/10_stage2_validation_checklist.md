# Stage-2 geometry validation checklist

Use this as acceptance criteria for the first Blender implementation.

## Cross-section validation

- [ ] UGR is an explicit datum and not derived from the lining center.
- [ ] Cмк is implemented as a separate validation envelope.
- [ ] Oм is implemented separately from Cмк.
- [ ] R50 and R65 use their different vertical clearance references.
- [ ] curve cant transforms the local track/clearance frame correctly.
- [ ] curve widening rules are applied for rectangular/open-cut profiles.
- [ ] two-track circular tunnel uses project-calculated vertical placement when diameter >9.4 m.
- [ ] 3.4 m minimum intertrack rule is not misused as a universal design spacing.

## Lining validation

- [ ] segmental/tubing tunnels are generated as discrete rings, not one deformed cylinder.
- [ ] ring pitch is measured along construction/alignment logic consistently.
- [ ] cast-iron N/C/K segment classes can differ.
- [ ] cast-iron ribs and flanges are true mesh at LiDAR LOD0.
- [ ] tubing bolt heads/nuts and grout plug can be independently enabled.
- [ ] modern RC ring joints are explicit.
- [ ] unknown segment layout never defaults silently to equal wedges.
- [ ] ring steering can occur by taper/rotation rather than mesh bending.

## Track validation

- [ ] gauge is measured between inner rail-head working faces.
- [ ] gauge changes by curve-radius rule, including R<=100 m -> 1.544 m.
- [ ] R50/R65 rail is extruded from a real rail profile, not a rectangle.
- [ ] cant rotates both running rails and support geometry coherently.
- [ ] R<300 m underground main-track curve can instantiate counterrail.
- [ ] legacy timber sleepers and modern RC elastic-boot supports are separate families.
- [ ] track concrete contains explicit drainage geometry.

## Contact rail validation

- [ ] default side is left in direction of travel.
- [ ] underground R<200 m rule can force outside-of-curve placement.
- [ ] switch/platform/event overrides are possible.
- [ ] nominal working surface is +0.160 m over UGR.
- [ ] nominal axis is 0.690 m outward from nearest running-rail inner working face.
- [ ] bracket pitch is independent from lining-ring pitch.
- [ ] end ramps and insulating gaps are event geometry, not texture.

## LiDAR validation

- [ ] semantic object IDs are exported.
- [ ] joint edges remain geometrically resolvable.
- [ ] rib/bolt/fastener geometry exists above configured sensor feature threshold.
- [ ] surface defects are generated as a separate condition layer.
- [ ] randomization is deterministic from seed.
- [ ] normative dimensions are not randomized outside documented tolerances.
- [ ] a BVH/analytic clearance test reports chainage and penetration depth.

## Failure policy

A generation job must fail loudly when an archetype requires an unknown value and no explicit fallback is selected.

Prohibited behavior:
- guessing a tunnel diameter from TBM class;
- guessing segment count from diameter;
- scaling a 5.1 m single-track tunnel into a 10 m two-track tunnel;
- using a ГОСТ clearance envelope as the physical wall mesh;
- placing rail-profile origins at +/- gauge/2 without accounting for the inner working face.
