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
- enabled flag.

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
relevance to ray intersections.

The default known_lateral_allowance_m is only 0.016 m, corresponding to the
documented 15 +/- 1 mm central-stop free clearance. It is intentionally named
"known" allowance and is not a claim that all dynamic gauging terms are known.

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
