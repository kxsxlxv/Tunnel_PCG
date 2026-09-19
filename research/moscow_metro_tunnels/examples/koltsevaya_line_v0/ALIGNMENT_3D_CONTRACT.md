# Resolved 3D alignment contract for the Koltsevaya pilot

The file 'alignment_3d.json' is intentionally **not committed yet** because the
route still lacks a verified surface/profile solution.

When it is generated, it must satisfy:

- local Cartesian metre coordinates;
- one explicit vertical datum in metadata;
- all 'z_ugr_m' values resolved;
- first and last sample at the same physical point;
- first and last Z identical within source tolerance;
- monotonic 's_m';
- uncertainty/provenance for reconstructed portions.

Then run 'blender_alignment3d_import.py'.

The script:
1. rejects any null 'z_ugr_m';
2. checks geometric seam closure;
3. forces exact repeated endpoint only after the tolerance check;
4. runs 'closed_parallel_transport_frames';
5. creates the 3D UGR diagnostic curve;
6. creates local XYZ frame empties every 100 m;
7. records the raw closed-loop holonomy correction.

The importer is deliberately a **diagnostic**. Final tunnel rings, rails and
services should consume these same frames rather than sweep one monolithic mesh
along the Blender Curve.
