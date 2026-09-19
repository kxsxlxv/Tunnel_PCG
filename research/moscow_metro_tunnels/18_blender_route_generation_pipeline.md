# Blender generation from georeferenced metro alignment data

Goal: turn a geospatial route into deterministic engineering transforms for tunnel rings, rails, contact rail and equipment.

Do **not** make Blender responsible for GIS parsing or vertical-datum conversion. Preprocess geospatial data outside Blender and feed Blender a local-metre engineering alignment.

---

## 1. Recommended architecture

```
OSM / survey XY
       |
       v
metric reprojection (UTM/project CRS)
       |
DEM / LandXML surface --------+
       |                      |
station/profile Z anchors ----+--> vertical profile solver
                                   |
                                   v
                    sampled 3D UGR centerline P(s)
                                   |
                              local origin
                                   |
                                   v
                    alignment.json / CSV
                                   |
                                   v
                  Blender Python engineering layer
                                   |
                  +----------------+----------------+
                  |                                 |
             transforms                       Geometry Nodes
         rings / rails / events              mass instancing
```

GIS acquisition and engineering reconstruction should be reproducible without opening Blender.

---

## 2. Input to Blender

Recommended sample spacing for alignment input:
- ordinary tangent/large curve: 1–5 m;
- transition curves: <=1 m;
- special chambers/turnouts: adaptive;
- do not use the input spacing as final mesh tessellation.

Each point:

```json
{
  "s_m": 1234.5,
  "x_m": 40.123,
  "y_m": -381.447,
  "z_ugr_m": -32.625,
  "surface_z_m": 4.811,
  "horizontal_radius_m": 800.0,
  "grade_permille": -18.0,
  "cant_mm": 80.0,
  "sigma_xy_m": 2.0,
  "sigma_z_m": 4.0,
  "source_class": "OSM+ENGINEERING_INTERPOLATED"
}
```

Coordinates are already **local metres**.

---

## 3. Blender coordinate convention

Keep the existing project convention:

- +X = increasing chainage/tangent;
- +Y = left;
- +Z = up.

A geospatial route cannot globally use +X as world chainage because it turns in plan. Instead:

- Blender world coordinates use local projected East/North/Up;
- each alignment sample has a local engineering frame:
  - local X = tangent;
  - local Y = left;
  - local Z = track up.

This frame is what tunnel sub-generators consume.

---

## 4. Use parallel-transport frames, not raw Frenet frames

For a sampled 3D route `P(s)`:

1. derive normalized tangent `T(s)`;
2. initialize an up vector;
3. transport the local left/up frame minimally between tangent samples;
4. orthonormalize;
5. rotate left/up about tangent by track cant.

This avoids:
- sudden 180-degree roll changes;
- Frenet instability on straight sections;
- unwanted twisting of circular tunnel rings.

The Stage-5 reference implementation adds this as:
`reference_impl/tunnel_pcg_ref/alignment3d.py`.

---

## 5. Apply cant after centerline orientation

Given base transported frame:
`{T, L, U}`.

Cant angle:
```
alpha = atan(h / gauge)
```

Rotate `L` and `U` around `T` by `alpha`.

Then:
- running rails;
- sleepers/LVT blocks;
- contact rail;
- O/C clearance envelopes

are placed in the canted track frame.

The structural tunnel lining does not necessarily rotate identically with track cant.

---

## 6. Ring placement

Never deform a segment/tubing ring continuously along a Blender Curve at LiDAR LOD0.

For ring pitch `w`:

```
s_n = s0 + (n + 0.5) * w
frame_n = alignment.frame(s_n)
instance ring in plane normal to frame_n.T
```

Then apply:
- taper/universal-ring steering;
- roll/index rotation;
- build tolerance;
- special-structure override.

For old cast-iron curves, preserve ring/wedge logic instead of using Curve Modifier bending.

---

## 7. Rails

Generate two rail centerlines from the UGR alignment frame.

Important:
gauge is between **inner working faces**, not profile symmetry axes.

Procedure:
1. determine curve-radius-dependent gauge;
2. get exact R50/R65 profile;
3. solve profile axis offsets from inner working faces;
4. offset both rail paths in local `L`;
5. sweep profile along each rail path using transported track frame.

Rail cross-sections from Stage 4 already have analytic reconstruction/fixtures.

---

## 8. Horizontal OSM geometry smoothing

Do not attach a Bezier curve to raw OSM vertices and enable Blender “Auto” handles. It can:
- cut corners;
- create radii below metro standards;
- change station position;
- distort track spacing.

Preferred modes:

### Mode A — Preserve public geometry
For a visual replica:
- resample the OSM polyline;
- use a smoothing filter with a strict lateral error corridor;
- report inferred curvature.

### Mode B — Engineering fit
For physically plausible alignment:
1. detect nearly straight ranges;
2. estimate circular arcs from stable curvature;
3. fit tangents/arcs;
4. insert radioidal/clothoid-like transition curves;
5. select transition length/cant from SP rules;
6. optimize the fit while keeping the line within an allowed XY corridor around OSM.

This produces a route that is often more plausible as a metro design than a raw GIS polyline, but it must be tagged `ENGINEERING_FIT_TO_OSM`.

### Mode C — Project alignment
If LandXML/project axis is available:
- use it directly;
- do no OSM smoothing.

---

## 9. Vertical profile representation

Do not use ordinary Blender Bezier control points as the source of truth.

Use piecewise engineering elements:

```
VerticalTangent {
  s0, s1,
  grade_permille
}

VerticalCircularCurve {
  s0, s1,
  radius_m,
  sign
}
```

Sample these analytically to generate Blender curves/meshes.

This allows:
- exact grade validation;
- exact vertical radius validation;
- consistent chainage;
- reproducible LiDAR trajectories.

---

## 10. Large-network precision

Moscow-wide projected coordinates are too large for ideal GPU/physics/LiDAR precision.

Use:

```
absolute engineering coordinate
  -> route/chunk local origin
  -> Blender float coordinate
```

Recommended chunk length:
- 1–5 km depending on engine and LiDAR range.

Keep a 64-bit metadata transform:
```
world_from_chunk
chunk_from_world
```

At runtime, origin-rebase when train/sensor crosses chunk boundaries.

---

## 11. Geometry Nodes vs Python

### Python should own
- GIS-local alignment import;
- chainage;
- frames;
- ring transforms;
- track gauge/cant;
- special route events;
- validation;
- semantic IDs/provenance.

### Geometry Nodes should own
- high-volume repeated instances;
- cable/fastener/light instancing;
- bounded construction variation;
- LOD switching.

Do not encode standards separately in Geometry Nodes and Python; keep one engineering source of truth.

---

## 12. LiDAR semantic metadata

Every generated object/instance should carry:

```
route_id
track_id
chainage_start
chainage_end
archetype
geo_quality
xy_source
z_source
sigma_xy
sigma_z
semantic_class
instance_id
```

This allows synthetic scans to distinguish “exact geometry” from “reconstructed plausible geometry”.

---

## 13. Minimal Blender import flow

Pseudo-code:

```python
route = load_alignment_json(...)

samples = [Vec3(p.x, p.y, p.z_ugr) for p in route.samples]
frames = parallel_transport_frames(samples)

for ring_s in ring_chainages(route):
    frame = interpolate_frame(frames, ring_s)
    create_or_instance_ring(frame)

for rail in ('left', 'right'):
    rail_path = build_rail_path(route, frames, rail)
    sweep_exact_rail_profile(rail_path)

generate_contact_rail(route, frames)
generate_track_supports(route, frames)
generate_services(route, event_ranges)
validate_clearances(route)
```

The Blender scene should be a *rendering/instancing result* of engineering alignment data, not the only copy of that data.

---

## 14. Recommended first real-route prototype

A good validation sequence is:

1. one short shallow/tangent section;
2. one OSM-derived interstation with a horizontal curve;
3. one section with two known station depth anchors;
4. one official river/channel crossing with a published depth constraint;
5. one large two-track modern tunnel.

For each compare:
- plan over OSM/orthophoto;
- surface longitudinal profile;
- generated UGR profile;
- grades;
- horizontal/vertical radii;
- overburden;
- ring orientation;
- rendered LiDAR.

Do not start by generating all Moscow lines at once; first validate one end-to-end alignment pipeline.
