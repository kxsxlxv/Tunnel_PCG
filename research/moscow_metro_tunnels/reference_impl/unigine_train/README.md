# UNIGINE 81-775 reference component

This directory contains an SDK-facing reference implementation built against
the API documented in the user-supplied ai_docs.zip.

It is intentionally kept outside the Python package build because the CI runner
does not contain the UNIGINE SDK.

## Files

- Train81775Kinematics.h / .cpp — one resolved-route vehicle kinematics
  component.
- RailSweptEnvelopeManager.h / .cpp — multi-route future obstacle screening
  component. It keeps unresolved turnout hypotheses alive, builds one adaptive
  OBB chain per route, queries the UNIGINE world by one conservative
  WorldBoundBox broad phase, and then applies OBB-vs-AABB SAT before assigning
  ACTIVE_ROUTE / ALL_FEASIBLE_ROUTES / ROUTE_AMBIGUOUS relevance.

## Input path

Use the .spl file emitted by:

examples/generate_koltsevaya_track_b_pilot.py

The generator writes the exact same C1 route interpolation used by Tunnel_PCG
continuous rail geometry as a native UNIGINE SplineGraph text file. Its points
are vertically shifted to the Stage-10 **track-axis UGR** datum before export;
do not replace it with the raw alignment/core-origin spline.

To refresh only the train path without regenerating any tunnel chunks:

```bash
python examples/generate_koltsevaya_track_b_pilot.py \
  --unigine-spline-only \
  --output examples/koltsevaya_track_b_train_path.json
```

This writes:
- `examples/koltsevaya_track_b_train_path_track.spl`;
- `examples/koltsevaya_track_b_train_path_summary.json`.

It deliberately does **not** create the requested `.json` scene file,
`*_chunks/`, a chunk manifest, or prototype geometry. The `--output` value
is only the naming/location anchor in spline-only mode.

The component:
1. loads the SplineGraph;
2. builds an arc-length lookup per cubic segment;
3. advances the leading bogie at fixed physics timestep;
4. solves the trailing bogie chainage such that the 3D pivot chord is 12.6 m;
5. orients each bogie using its local spline tangent/up;
6. places the carbody on the rigid chord between bogies.

The component assumes the imported vehicle nodes use local +Y as forward and +Z
as up. Put a corrective parent transform around a mesh asset if its authoring
axes differ.

## Obstacle manager

Attach RailSweptEnvelopeManager to a scene node and point
train_kinematics_node at the node containing Train81775Kinematics.

Each route_hypotheses entry contains:
- route_id;
- native .spl file;
- global_chainage_origin_m;
- enabled flag;
- either path_uncertainty_exact_ground_truth=true for simulator truth, or
  explicit non-negative bounds for lateral offset, heading, curvature,
  vertical offset, grade and cant/roll uncertainty.

Negative uncertainty values mean **unknown**, not zero.

Leave active_route_id empty while a turnout route is unresolved. In that state
the manager treats every enabled and geometrically feasible route as live. A
candidate intersecting only a subset of routes is ROUTE_AMBIGUOUS; it is not
discarded. Once an external switch/route detector resolves the route,
active_route_id can be set to the selected route ID.

For engine objects the manager uses:
1. World::getIntersection(WorldBoundBox, objects) as broad phase;
2. each object's getWorldBoundBox();
3. SAT against every future vehicle OBB.

For LiDAR points call classifyPoint() directly; this avoids reducing point-cloud
relevance to ray intersections. The manager rebuilds a balanced BVH over the
future OBB world AABBs on every envelope update, so point classification prunes
most future poses before the exact OBB containment test.

Vehicle/track gauging inputs are separate from path-estimation uncertainty.
The component exposes the documented 0.016 m body/bogie free-clearance upper
value plus explicit GOST q and w slots, dynamic lateral/vertical/roll terms and
track tolerances. All unsourced terms default to -1 (unknown). The 0.016 m value
is not treated as a complete sourced w.

isSafetyComplete() returns true only when all vehicle/track allowance terms and
all enabled route path-uncertainty terms are explicitly supplied. Ground-truth
simulation should use each route's path_uncertainty_exact_ground_truth toggle.

## Runtime diagnostics

Both UNIGINE reference components now expose diagnostic logging toggles.

Train81775Kinematics:
- Diagnostic Logging = true prints the spline path, node world positions before
  the first snap, spline segment count/length, route start/end samples, resolved
  leading/trailing chainages, target body position, node positions after the
  snap and the first N physics ticks.
- Diagnostic Physics Ticks controls how many initial fixed-physics updates are
  logged.

RailSweptEnvelopeManager:
- Diagnostic Logging = true prints every route hypothesis including whether it
  is enabled, its spline path and exact-ground-truth flag, loaded route
  geometry, safety-completeness state and the first N envelope updates.
- Diagnostic Updates controls the initial update count.

These logs are specifically intended for diagnosing UNIGINE world-space /
spline-space mismatches when runtime object transforms cannot be inspected in
the editor while Play mode is active.

## Important limitations

- Train81775Kinematics represents one already-resolved route.
- RailSweptEnvelopeManager does not infer switch state by itself; it preserves
  ambiguity until another subsystem supplies active_route_id.
- The current screening volume is an above-TOR rectangular proxy, not a
  complete underframe/bogie/current-collector envelope.
- The 20.08 m dimension is still a coupler-head longitudinal proxy, not a
  certified rigid carbody contour.
- Target 81-775 bogie wheelbase and several dynamic gauge allowances remain
  unsourced.
- C++ files are API-grounded reference code but are not compiled in repository
  CI because the UNIGINE SDK is not installed there.

Turnout ambiguity and obstacle-envelope rules are specified in:
research/moscow_metro_tunnels/24_unigine_train_kinematics_and_obstacle_envelope.md
