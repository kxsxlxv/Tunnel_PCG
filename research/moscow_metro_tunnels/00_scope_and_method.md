# Scope and research method

## Goal

Build an implementation-oriented technical base for procedural generation of Moscow Metro **train-running tunnels** in Blender, with geometry accurate enough to support synthetic LiDAR.

The model must distinguish:
- civil/structural geometry that controls the tunnel envelope;
- permanent-way geometry (running rails, rail fastenings, sleepers/half-sleepers, track concrete/ballast);
- third/contact rail and its guards/supports;
- drainage;
- visible electrical/cable/lighting infrastructure;
- construction-era details that materially change a LiDAR point cloud.

Stations, escalator tunnels, ventilation shafts and service tunnels are outside the primary scope except where they create a transition visible from a running tunnel (bellmouths, cross-passages, chambers, junctions, station approaches).

## Source hierarchy

Use values in this order:
1. Current Russian standards and Moscow operating rules.
2. Official Moscow construction / engineering publications.
3. Historical USSR/Russian design standards valid for the construction era.
4. Engineering textbooks / Metrostroy technical literature.
5. Photographs and enthusiast archives, only for visual validation and non-dimensional detail.

Every dimensional field should carry:
- source;
- construction era / applicability;
- confidence level: A = normative/primary; B = official engineering publication; C = technical secondary; D = visual inference;
- whether the value is exact, nominal, range, or inferred.

## Critical modeling rule

Do **not** reduce “Moscow Metro tunnel” to a single 5.1 m circle. Moscow has multiple generations of running-tunnel geometry: early/legacy circular cast-iron linings, 5.5 m-class circular linings, precast concrete block linings, monolithic pressed-concrete linings, cut-and-cover rectangular tunnels, modern 6 m TBM single-track tunnels, and modern ~10 m TBM two-track tunnels. Project-specific transitions and widened zones must be treated as separate procedural archetypes.

Research snapshot date: 2026-09-19.
