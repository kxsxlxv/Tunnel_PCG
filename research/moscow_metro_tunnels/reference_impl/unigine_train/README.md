# UNIGINE 81-775 reference component

This directory contains an SDK-facing reference implementation built against
the API documented in the user-supplied ai_docs.zip.

It is intentionally kept outside the Python package build because the CI runner
does not contain the UNIGINE SDK.

## Files

- Train81775Kinematics.h / .cpp — one resolved-route vehicle kinematics
  component.

## Input path

Use the .spl file emitted by:

examples/generate_koltsevaya_track_b_pilot.py

The generator writes the exact same C1 route interpolation used by Tunnel_PCG
continuous rail geometry as a native UNIGINE SplineGraph text file.

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

## Important limitations

- This component represents one already-resolved route.
- It does not guess a turnout branch.
- It does not yet construct the complete dynamic/swept obstacle envelope.
- The 20.08 m length is used only for debug endpoint markers, not as a certified
  rigid carbody contour.
- Target 81-775 bogie wheelbase and several dynamic gauge allowances remain
  unsourced.

Turnout ambiguity and obstacle-envelope rules are specified in:
research/moscow_metro_tunnels/24_unigine_train_kinematics_and_obstacle_envelope.md
