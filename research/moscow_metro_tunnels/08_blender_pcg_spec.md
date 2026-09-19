# Blender PCG implementation specification

Purpose: implementation contract for an AI coding agent building high-fidelity Moscow Metro running tunnels for synthetic LiDAR.

This document intentionally separates physical geometry from normative clearance geometry.

---

## 1. Core scene graph

Recommended hierarchy:

```
TUNNEL_ROOT
├── ALIGNMENT
├── LINING
│   ├── RINGS / SECTIONS
│   ├── JOINTS
│   ├── BOLTS / POCKETS / GROUT_PLUGS
│   └── TRANSITIONS
├── TRACK
│   ├── RUNNING_RAIL_L
│   ├── RUNNING_RAIL_R
│   ├── SLEEPERS_OR_BLOCKS
│   ├── FASTENINGS
│   ├── TRACK_CONCRETE
│   ├── DRAINAGE
│   └── COUNTERRAIL_EVENTS
├── THIRD_RAIL
│   ├── CONTACT_RAIL
│   ├── BRACKETS
│   ├── INSULATORS
│   ├── PROTECTIVE_COVER
│   └── AIR_GAP_EVENTS
├── SERVICES
│   ├── CABLE_RACKS
│   ├── CABLES
│   ├── LIGHTING
│   ├── PIPES
│   ├── SIGNAL_OBJECTS
│   └── SIGNS
├── SPECIAL_STRUCTURES
│   ├── CROSS_PASSAGES
│   ├── BULKHEADS
│   ├── BELLMOUTHS
│   ├── SWITCH_CHAMBERS
│   └── TBM_CHAMBERS
└── VALIDATION
    ├── C_CLEARANCE
    └── O_CLEARANCE
```

Each layer must be independently togglable.

---

## 2. Alignment representation

Use a continuous 3D engineering alignment, not an arbitrary Blender Bezier alone.

```python
AlignmentSegment =
    Tangent |
    CircularArc |
    TransitionCurve |
    VerticalGrade |
    VerticalCurve
```

At sampled chainage `s`, compute:
- position P(s);
- unit tangent T(s);
- horizontal normal;
- track cant / superelevation h(s);
- local frame using parallel transport or equivalent low-twist frame.

Avoid raw Frenet frames at low curvature because orientation becomes numerically unstable.

Track frame:
- X = T;
- Y = left;
- Z = up;
- rotate Y/Z about X by cant.

The lining frame may be related to, but must not always equal, the track frame.

---

## 3. Construction-centered vs track-centered geometry

Store two axes:

```
tunnel_axis(s)
track_axis(s)
```

They may differ:
- vertical placement;
- curve/cant clearance shift;
- two-track circular tunnel layout;
- transitions / chambers.

For a classic single-track circular clearance:
- Cмк clearance-circle center is 1.700 m above UGR for R50;
- 1.670 m for R65.

Treat this as a validation datum, not an automatic proof of physical lining-axis location in every historical tunnel.

---

## 4. Lining generator API

Suggested Python interface:

```python
generate_lining(
    alignment,
    lining_family,
    s0,
    s1,
    ring_sequence=None,
    construction_tolerance_profile=None,
    lod=0
)
```

### Circular segmental/tubing lining

Never generate as one long bent cylinder.

Algorithm:
1. determine ring centers along chainage by ring pitch;
2. calculate each ring plane;
3. apply ring taper / wedge arrangement where required;
4. create segment instances around ring;
5. create explicit radial and circumferential joints;
6. instance bolts, ribs, sockets and plugs by lining family;
7. merge only for export if the target LiDAR engine benefits.

### Monolithic lining

Generate:
- swept true circular profile;
- construction pour seams at configured intervals;
- local geometry patches as optional condition layer.

### Rectangular lining

Generate structural section by family:
- precast frame section;
- wall + roof + invert blocks;
- diaphragm walls + roof slab;
- monolithic box.

Curves must widen according to structural design, not by blindly bending the inside wall.

---

## 5. Ring-family schema

```json
{
  "id": "TBM_6000_5400_RC_7SEG_R1400",
  "shape": "circle",
  "outer_diameter_m": 6.0,
  "inner_diameter_m": 5.4,
  "ring_width_m": 1.4,
  "segment_count": 7,
  "segment_layout": [],
  "joint_gap_m": null,
  "gasket": true,
  "intrados_features": {
    "bolt_pockets": true,
    "grout_socket": true
  },
  "steering": {
    "method": "universal_or_project_specific",
    "taper_m": null
  }
}
```

Unknown values stay null. Do not hallucinate.

---

## 6. Cast-iron tubing mesh

LOD0 tubing should be built parametrically from:
- intrados back plate;
- two ring flanges;
- two radial flanges;
- 1 circumferential rib;
- 2–3 radial ribs on normal elements;
- flange caulking rebates;
- bolt bores;
- bolt heads/nuts/washers;
- grout-injection plug.

Recommended approach:
- create one segment in local polar coordinates;
- use actual different classes N/C/K;
- instance around ring;
- do not apply radial Array with identical segments for key ring.

Surface intersection sharpness matters for LiDAR more than material texture.

---

## 7. Track generator

```python
generate_track(
    track_alignment,
    rail_type,
    gauge_rule,
    support_family,
    sleeper_density_rule,
    track_concrete_family,
    drainage_family,
    lod
)
```

### Gauge
Use radius-dependent current/historical rule set.
At R <= 100 m current gauge reaches 1.544 m.

### Running rail
Extrude exact R50/R65 section along rail-centerline.
Correct placement:
- gauge is distance between **inner rail-head working faces**;
- derive rail profile reference origin so the working face, not the profile centroid, lands at gauge/2.

### Sleeper/block placement
Use an engineering pitch sequence, plus small bounded build tolerance if requested.

Legacy:
- wooden full sleepers 2.75 m straight / 2.65 m curves;
- 250 x 160 mm section.

Modern:
- independent RC/LVT-style blocks in boots.

### Concrete
Generate explicit drain crossfall and central channel.

---

## 8. Third-rail generator

Inputs:
- traffic direction;
- curve radius;
- platform / turnout events;
- third-rail side overrides.

Side logic:
1. default: left in direction of movement;
2. R < 200 m underground curve: outside of curve;
3. platform/turnout/event may override.

Physical placement:
- working contact surface z = +0.160 m above UGR;
- contact-rail axis is 0.690 m outside the nearest running rail's inner head working face.

Support placement:
- normal pitch randomly/strategically chosen within 4.5–5.4 m;
- special-zone rule sets override.

Explicit geometry:
- bracket;
- insulator;
- fastening bolt;
- anti-creep;
- rail;
- insulating cover;
- cover supports.

Air-gap event:
- accepting ramp 1:30 on main track;
- releasing ramp 1:25;
- no-contact length event using project rule.

---

## 9. Clearance engine

Do not use Blender's viewport collision as the only validator.

Create 2D clearance polygons in local track coordinates and sweep/sample them.

```python
class ClearanceEnvelope:
    name: str
    frame: str
    polygon_or_circle: ...
    curve_rule: ...
    rail_type_rule: ...
```

Check every mesh vertex / BVH against envelope at sampled s.

For circular Cмк an analytic test is preferable:
```python
inside = x*x + (z-zc)**2 < R*R
```

For equipment Oм use piecewise-linear polygons from the standard.

Log:
- object;
- chainage;
- penetration depth;
- governing envelope;
- allowed/not allowed.

---

## 10. LiDAR-specific geometry policy

Synthetic LiDAR requires real geometry for features above target angular/range resolution.

At close range explicitly model:
- 10–30 mm joint gaps/recesses when project-confirmed;
- tubing ribs;
- bolt heads;
- grout plugs;
- cable bundles;
- cable brackets;
- luminaire bodies;
- rail clips/plates;
- third-rail cover;
- drainage edges;
- repair build-up / mineral deposits when condition simulation is enabled.

Use normal maps only for:
- very fine concrete aggregate;
- paint texture;
- corrosion texture below sensor resolution.

Provide a `lidar_min_feature_m` threshold. Features larger than this must be mesh geometry.

---

## 11. Surface-condition layer

Keep deterioration independent from base construction.

```python
ConditionProfile:
    seepage_frequency
    efflorescence_depth
    patch_frequency
    cable_sag_sigma
    bolt_missing_probability
    local_spall_probability
    grime_height_profile
```

For ground-truth training, record semantic IDs:
- lining;
- joint;
- bolt;
- rail;
- sleeper;
- third rail;
- cable;
- drain;
- walkway;
- signal;
- defect.

---

## 12. Deterministic randomization

Every generated route should be reproducible:

```python
seed = hash(project_seed, tunnel_id, chainage_bucket, subsystem)
```

Randomize only within physically justified distributions.

Do not randomize:
- normative gauge;
- fundamental ring diameter;
- rail profile;
- contact-rail nominal offset;
- clearance envelopes.

---

## 13. Recommended implementation order

Phase A:
1. alignment frame;
2. classic 5.5/5.1 cast-iron lining;
3. R65 track on legacy timber/concrete;
4. contact rail;
5. Cмк/Oм validation.

Phase B:
6. modern 6.0/5.4 segmental ring;
7. LVT track;
8. modern services.

Phase C:
9. two-track 10 m-class circle;
10. rectangular open-cut;
11. transitions / bellmouths / switch chambers.

Phase D:
12. defect/condition randomization;
13. LiDAR semantic metadata;
14. export/performance LOD.

The AI coding agent should reject an archetype with missing required geometric parameters rather than silently inventing values.
