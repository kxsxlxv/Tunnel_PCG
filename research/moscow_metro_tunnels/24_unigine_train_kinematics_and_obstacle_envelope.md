# Unigine train kinematics and obstacle-relevance envelope — 81-775

Research snapshot: 2026-09-24.

## 1. Purpose

This note defines the first runtime contract for moving a Moskva-2020 81-775
vehicle through the generated tunnel and for deciding which LiDAR obstacles are
geometrically relevant to the vehicle.

The core rule is:

> **Do not move the complete vehicle as one rigid transform sampled at one
> track-centre point.**

The wheelsets and bogies follow the rails much more directly than the carbody.
On a horizontal curve the carbody longitudinal axis is approximately a chord
between its two bogie guiding/pivot sections. That chord geometry creates an
inward displacement around the vehicle centre and an outward displacement at
the vehicle ends.

The render mesh, nominal rigid-body kinematics, kinematic/swept envelope, and
obstacle-query acceleration structure are separate layers.

---

## 2. Terminology and controlling sources

### Moscow / Russian terminology

Primary current gauging source:

- ГОСТ 23961-2024 «Метрополитены. Габариты приближения строений,
  оборудования и подвижного состава», effective 2025-06-01.
- Rosstandart registration:
  https://protect.gost.ru/gost/details/d9e37be2-c5e8-4727-9df3-b84536ed7609
- Searchable copy used for formula review:
  https://meganorm.ru/mega_doc/norm_update_01032025/gost_gosudarstvennyj-standart/0/gost_23961-2024_mezhgosudarstvennyy_standart_metropoliteny.html

ГОСТ uses **геометрический вынос подвижного состава** for displacement caused
by the vehicle longitudinal axis lying on the chord through the guiding
sections. For four-axle vehicles the guiding sections pass through the vertical
bogie kingpin axes.

Appendix В also distinguishes non-geometric lateral terms, including:
- q — possible lateral bogie-frame displacement relative to the wheelset from
  clearances/wear;
- w — possible lateral carbody displacement relative to the bogie frame from
  clearances, wear and elastic oscillation.

Therefore geometric throw is only one component of the final clearance problem.

### English gauging terminology

For implementation naming, use the established English terms:
- **centre throw / center throw** — maximum inward curve throw around the
  vehicle centre;
- **end throw** — maximum outward curve throw at the vehicle end;
- **kinematic envelope** — vehicle-related envelope including relevant
  tolerances/motions according to the adopted gauging standard;
- **swept envelope** — route-dependent envelope after curve/throw effects are
  applied.

A useful independent terminology cross-check is LTA E/GD/09/106/A3 (Dec 2025),
which explicitly defines centre/end throw and calls the kinematic envelope
enlarged for curve throw the swept envelope:
https://www.lta.gov.sg/content/dam/ltagov/industry_innovations/industry_matters/development_construction_resources/pdf/TransportInfrastructure/civil_standards/pdf/EGD09106A3-Overall.pdf

This international source is used for terminology and implementation
cross-checking only. Moscow clearance validation remains controlled by the
applicable Russian standards.

---

## 3. 81-775 source-backed inputs

Project source: user-supplied 81-775.md.

Known:
- length over coupler heads: 20.080 m;
- maximum width: 2.740 m;
- empty height above top of rail: 3.680 m;
- vehicle base: 12.600 m;
- two powered two-axle bogies;
- vertical pivot/kingpin arrangement between bogie and body;
- central lateral-stop clearance: 15 +/- 1 mm to each side stop;
- design speed: 90 km/h.

The source does **not** give a complete target-vehicle kinematic gauge. Important
missing values include:
- target bogie wheelbase;
- detailed rigid carbody length versus coupler-head length;
- exact pivot-to-body-end dimensions;
- complete exterior/underframe/current-collector 3D contour;
- maximum suspension lateral/vertical excursions and roll;
- wheel/rail lateral play;
- complete wear and maintenance tolerances.

These stay explicit unknowns. They must not silently become zero.

Data file:
research/moscow_metro_tunnels/data/rail_vehicle_81_775.json

---

## 4. Nominal rigid-chord vehicle kinematics

Let the track evaluator return at chainage s:

P(s)  = 3D track-centre position
T(s)  = unit tangent
U(s)  = local track-plane up vector, including cant when available

For the first implementation, use the 12.600 m vehicle base as the distance
between the two body guiding/pivot sections. This is an engineering
interpretation consistent with current four-axle metro gauging terminology and
must remain tagged as such until an 81-775 dimensioned drawing explicitly
locates both pivot centres.

### 4.1 Do not use s_rear = s_front - 12.600

That relation preserves *arc length*, not the rigid distance between the body
pivot points.

Instead solve:

| P(s_front) - P(s_rear) | = B

where:

B = 12.600 m

The root is local and is solved by bracket + bisection in the engine-neutral
reference implementation.

### 4.2 Bogie poses

Each bogie pose uses its own local rail frame:

bogie_position = P(s_bogie)
bogie_forward  = T(s_bogie)
bogie_up       = U(s_bogie)

Thus the bogies yaw independently as they follow the track.

A later higher-fidelity bogie model can use both axle positions and the actual
bogie wheelbase. That value is currently unavailable for the target vehicle.

### 4.3 Carbody pose

Let:

P_f = front/leading bogie pivot
P_r = rear/trailing bogie pivot

Then:

body_forward = normalize(P_f - P_r)
body_origin  = 0.5 * (P_f + P_r)

The nominal body up vector is derived from the two bogie/track up vectors and
orthogonalized against body_forward.

This makes the body a **rigid chord**, not a bendable spline follower.

---

## 5. Circular-curve throw as a validation oracle

For a constant-radius horizontal curve and two guiding sections separated by
base B, the exact inward centre displacement of the chord midpoint is:

centre_throw_exact =
    R - sqrt(R^2 - B^2 / 4)

For a symmetric rigid longitudinal proxy of total length T, the exact outward
endpoint displacement is:

end_throw_exact =
    sqrt(R^2 + (T^2 - B^2) / 4) - R

Small-angle screening approximations are:

centre_throw ~= B^2 / (8 R)

end_throw ~= (T^2 - B^2) / (8 R)

For the 81-775 reference implementation:
- B = 12.600 m;
- T = 20.080 m **only as a conservative coupler-head-length screening proxy**.

Do not use this endpoint proxy as a certified carbody/coupler swept envelope.

Approximate screening values:

| R, m | centre throw, mm | end throw proxy, mm |
|---:|---:|---:|
| 300 | ~66 | ~102 |
| 400 | ~50 | ~76 |
| 600 | ~33 | ~51 |
| 1200 | ~17 | ~25 |
| 2000 | ~10 | ~15 |

The runtime algorithm does not use these approximations. Tests use them to
verify that the two-bogie/chord solver behaves correctly on a circular path.

ГОСТ's complete rolling-stock restriction methodology additionally depends on
bogie base and q/w-style lateral terms. Those cannot yet be evaluated fully for
81-775 because the target bogie wheelbase and several motion allowances are
missing.

---

## 6. Obstacle-relevance volume

The obstacle volume is not a constant tunnel cross-section.

Use the following layers:

1. **Physical nominal vehicle geometry**
   - carbody;
   - bogies/running gear;
   - underframe equipment;
   - current collectors where relevant.

2. **Geometric path effect**
   - actual rigid-chord body pose from the two bogie pivots;
   - centre/end throw follows automatically from that pose.

3. **Vehicle kinematic/dynamic allowances**
   - documented body-bogie lateral freedom;
   - wheelset/bogie play;
   - suspension lateral and vertical motion;
   - roll/bounce;
   - wear/tolerances.

4. **Track allowances**
   - gauge/alignment/level/cross-level tolerances where applicable.

5. **Future-path estimation uncertainty**
   - LiDAR rail-centre estimation error;
   - heading error;
   - curvature/transition fit uncertainty;
   - uncertainty growth with look-ahead.

The current 81-775 source directly documents only one useful lateral free-play
number: the central stop clearance is 15 +/- 1 mm on each side. The reference
budget therefore records **16 mm as a known documented upper free-clearance
term**, but marks the total safety envelope incomplete.

ГОСТ Appendix В terms are now represented explicitly:
- **q** = bogie-frame lateral displacement relative to the wheelset in the
  guiding section;
- **w** = carbody lateral displacement relative to the bogie frame in the
  guiding section.

The supplied 81-775 material does not provide complete target values for q or
w. They therefore remain unknown. The 16 mm documented stop gap is evidence for
body/bogie free motion, not a silent replacement for the complete normative w.

### 6.1 Recommended runtime representation

For obstacle testing, sample future vehicle poses along time or travelled
distance and build a union of conservative convex volumes:
- OBB/convex hull for carbody at each pose;
- separate bogie/underframe volumes;
- connect consecutive samples with swept prisms/hulls;
- inflate by the current allowance/uncertainty budget.

The spacing between samples must be error-driven:
- tighter in high curvature;
- tighter near transition curves and turnouts;
- tighter when path-estimation uncertainty changes rapidly.

Do not use only a single AABB aligned to world axes except as broad phase.

---

## 7. Track-estimation uncertainty

The generated tunnel has a known synthetic centreline, but the intended
obstacle-detection system may estimate future track locally from LiDAR.

Therefore maintain two paths:
- **ground-truth path** for simulation/evaluation;
- **estimated path hypotheses** for the detector.

Do not hide the difference.

A practical uncertainty model should propagate sampled path hypotheses rather
than only inflating one nominal line by a constant scalar. Each hypothesis
carries explicit deterministic error bounds for:
- lateral offset;
- heading;
- curvature/transition fit;
- vertical offset;
- grade;
- cant/roll of the estimated track frame.

The engine-neutral reference now separates these terms from vehicle/track
allowances. For a look-ahead distance d it uses the conservative first-order
bound model:

lateral_bound(d) =
    lateral_offset + d*tan(heading_error) + 0.5*d^2*curvature_error

yaw_bound(d) =
    heading_error + d*curvature_error

vertical_bound(d) =
    vertical_offset + d*tan(grade_error)

Yaw and roll uncertainty expand the OBB extents geometrically; they are not
approximated as a constant lateral scalar.

A missing uncertainty term is **unknown**, not zero. Synthetic evaluation using
the known generated centreline must opt in explicitly through
PathEstimationUncertainty.exact_ground_truth(). This keeps ground-truth
evaluation distinct from detector evaluation.

The obstacle-relevance volume remains the union of corresponding vehicle swept
volumes over retained route/path hypotheses. This naturally represents
nonlinear growth of position error at look-ahead distance.

---

## 8. Turnouts and crossovers

A turnout is a **discrete route-hypothesis problem**, not merely a wider
Gaussian around one centreline.

If no route map, interlocking/switch state or sufficiently strong local rail
observation is available, keep every geometrically feasible branch alive:
- straight;
- diverging;
- crossover branch(es), as applicable.

Obstacle policy while route is unresolved:

obstacle_volume =
    union(swept_envelope(route_i) for every feasible route_i)

Classification:
- OUTSIDE — intersects no feasible route envelope;
- ALL_FEASIBLE_ROUTES — intersects every feasible route;
- ROUTE_AMBIGUOUS — intersects at least one but not all feasible routes;
- ACTIVE_ROUTE — route has been resolved and the obstacle intersects it.

This deliberately increases false positives near an unresolved switch. That is
preferable to deleting a real obstacle on the branch the train may take.

Only prune a route hypothesis when the selected branch is resolved strongly
enough **before the vehicle reaches the action/stopping horizon**. Possible
evidence includes:
- explicit switch/interlocking state;
- preloaded route;
- robust LiDAR rail topology ahead;
- train-control route authority.

Use hysteresis/confidence when changing the active branch so noisy rail
detection cannot cause rapid route flipping.

The existing OSM reference stitcher in this repository already follows the
same conservative principle: a branched graph is rejected rather than silently
choosing one physical path.

---

## 9. UNIGINE architecture

Reviewed from the supplied ai_docs.zip:
- SplineGraph API/sample;
- WorldSplineGraph documentation/sample;
- move_by_trajectory sample;
- update_physics sample;
- bounding-volume object detection sample;
- asynchronous ray-intersection samples;
- Mesh Cluster documentation.

### 9.1 Track graph

Use **SplineGraph** (or an equivalent project-owned rail graph wrapped around
it) as the runtime topology/evaluation layer.

Required operations:
- segment graph / branch adjacency;
- point evaluation;
- tangent evaluation;
- up-vector evaluation;
- route-hypothesis traversal.

Do not use WorldSplineGraph as the authoritative train state merely because it
can place/generate geometry along a spline. Geometry generation and vehicle
kinematics are separate concerns.

Because spline t is parametric rather than metres, maintain an arc-length LUT
per edge:
- s -> edge, local distance -> t;
- update/refine the LUT until position error is below the train-path tolerance.

### 9.2 Fixed-step simulation

Advance authoritative vehicle chainage and route state from the physics/fixed
simulation update. Visual transforms may be interpolated for rendering.

Recommended hierarchy:

TrainRoot
  Carbody_81_775
  BogieFront
  BogieRear
  Sensors
    LiDAR
    Cameras

The carbody transform comes from the pivot chord. Each bogie receives its own
track-frame transform.

### 9.3 Mesh Cluster

Do **not** put the moving train body/bogies into Mesh Cluster.

Mesh Cluster remains appropriate for the static repeated tunnel assets already
generated by Tunnel_PCG. The supplied UNIGINE documentation states that a Mesh
Cluster contains identical **static** meshes with matching materials.

### 9.4 Obstacle query

Two stages are recommended.

**Broad phase**
- query a conservative world-space bound around the whole future swept volume;
- or query a point-cloud/BVH equivalent for LiDAR points.

**Narrow phase**
- test candidates against route-hypothesis swept hulls/OBBs;
- report minimum distance / first predicted intersection / route-hypothesis
  membership.

Do not use a single ray as the final obstacle test. Ray intersections are useful
for sensor simulation and selected narrow queries but do not represent vehicle
volume.

---

## 10. Implementation status

Implemented in the engine-neutral Python core:
- RailVehicleGeometry for 81-775 source-backed scalar dimensions;
- TrackFrame / RigidFrame;
- trailing-bogie chord-distance solver;
- independent bogie poses;
- rigid carbody chord pose;
- exact and small-angle circular-throw screening;
- explicit incomplete ГОСТ q/w + vehicle/track allowance budget;
- separate future-path estimation uncertainty model with explicit
  exact-ground-truth mode;
- look-ahead-dependent OBB growth from offset/heading/curvature/grade/cant
  uncertainty;
- turnout route-hypothesis obstacle classification;
- above-TOR rectangular 81-775 screening OBB derived only from the currently
  sourced overall width/height/coupler-head length;
- adaptive future-pose sampling by rigid-body midpoint deviation;
- per-route sampled/inflated OBB union and broad-phase world AABB;
- immutable BVH over per-pose OBB world AABBs for LiDAR point queries;
- BVH classification is semantically identical to the naive OBB-union test but
  prunes most future OBBs before the expensive oriented containment test;
- union/classification across unresolved route hypotheses.

Modules:
- src/tunnel_scanner_core/rail_vehicle.py
- src/tunnel_scanner_core/rail_obstacle.py

Tests:
- tests/test_rail_vehicle.py
- tests/test_rail_obstacle.py

The OBB layer is intentionally named a **screening proxy**, not a final
kinematic gauge. Its lower plane is Top Of Rail because the supplied source
does not give a complete underframe/bogie/current-collector contour. Detailed
running gear remains a separate future volume.

Coordinate rule: every vehicle TrackFrame position is the **track axis at UGR**.
Do not feed the raw Stage-9/10 alignment/core origin directly into vehicle
kinematics. The Koltsevaya .spl exporter now applies the Moscow profile's
profile-to-core UGR offset explicitly.

UNIGINE path bridge:
- src/tunnel_scanner_core/unigine_spline.py converts the same C1 alignment used
  by Tunnel_PCG rails into native UNIGINE .spl cubic-Bezier data;
- the spline points are shifted from the generic alignment/core origin to the
  actual Stage-10 track-axis UGR datum before export. For the current Moscow
  profile this is the profile-to-core Z offset (currently -1.670 m), so the
  train path lies on the running-rail head plane rather than the lining/core
  datum;
- the Koltsevaya pilot writes <output_stem>_track.spl and records it in the
  manifest;
- the Hermite-to-Bezier conversion is tested point-for-point.

UNIGINE SDK-facing reference:
- research/moscow_metro_tunnels/reference_impl/unigine_train/
  Train81775Kinematics.h/.cpp;
- loads the .spl with SplineGraph;
- builds an arc-length LUT because spline parameter t is not distance;
- advances the leading bogie from COMPONENT_UPDATE_PHYSICS;
- solves the trailing-bogie chord constraint every physics step;
- applies independent bogie tangent/up frames and one rigid carbody chord;
- supports one already-resolved route hypothesis only.

UNIGINE multi-route obstacle reference is now implemented in:
- research/moscow_metro_tunnels/reference_impl/unigine_train/
  RailSweptEnvelopeManager.h/.cpp.

It mirrors rail_obstacle.py:
- route hypotheses are separate SplineGraph paths configured through
  PROP_ARRAY_STRUCT;
- current train chainage comes from Train81775Kinematics;
- each feasible hypothesis produces an adaptively refined future OBB chain from
  the same 12.6 m two-bogie chord kinematics;
- World::getIntersection(WorldBoundBox, ...) is used only as broad phase;
- candidate objects use getWorldBoundBox() followed by OBB-vs-AABB SAT;
- LiDAR points can be classified directly with classifyPoint(), without ray
  intersection;
- an empty/invalid active route does not suppress unresolved alternatives;
- unresolved routes are unioned and retain ROUTE_AMBIGUOUS classification;
- GOST q/w, vehicle dynamics and track tolerances are separate properties with
  unknown-by-default sentinel values;
- every route has its own future-path offset/heading/curvature/vertical/grade/
  cant uncertainty bounds, or an explicit exact-ground-truth mode;
- yaw/roll and growing centreline uncertainty expand each future OBB using the
  same formulas as the Python oracle;
- isSafetyComplete() is false until both allowance and path-uncertainty ledgers
  are complete.

This manager sits above the single-route vehicle component so a turnout is not
resolved implicitly by whichever spline happens to be loaded first.

The UNIGINE implementation is grounded in the supplied SDK documentation for
SplineGraph, Component System array structs, fixed-physics updates, world
bounding-volume intersections, node world bounds and Visualizer. It remains
reference code until compiled against the user's installed UNIGINE SDK.

---

## 11. Safety / evidence boundary

This model is suitable for synthetic simulation and algorithm development. It
is **not yet a complete safety-certified rolling-stock kinematic gauge**.

Do not label the obstacle volume complete until the missing target-vehicle
allowances and detailed target geometry have been sourced or measured.

In particular:
- do not interpret the documented 15 +/- 1 mm lateral-stop clearance as the
  entire lateral dynamic allowance or as a sourced ГОСТ w value;
- do not substitute zero for unknown q/w, roll, suspension, track or
  path-estimation terms;
- use exact-ground-truth zero uncertainty only when evaluating against the
  simulator's known generated track, not when emulating the LiDAR detector's
  locally estimated future track.
