# Tunnel equipment and services visible to LiDAR

Research snapshot: 2026-09-19.

Primary current design source:
СП 120.13330.2022 «СНиП 32-02-2003 Метрополитены», consolidated through 2026:
https://meganorm.ru/mega_doc/norm_update_01052026/metodika/0/sp_120_13330_2022_svod_pravil_metropoliteny_snip_32-02-2003.html

This file covers infrastructure that materially changes tunnel point clouds:
- cable brackets/trays/cables;
- luminaires and emergency/evacuation signs;
- fire/wash water main and taps;
- signal/signage hardware;
- walkway/evacuation objects;
- local cabinets, grounding conductors and attachment hardware.

The exact project layout varies strongly by line and era. Geometry is therefore split into normative constraints and project/archetype presets.

---

## 1. Cable infrastructure

### 1.1 Routing principle

Current SP permits exposed cable routing in non-passenger areas. Running tunnels therefore commonly contain visibly exposed cable runs on wall/lining-mounted brackets or shelves.

Do not merge cables into a texture. For synthetic LiDAR at normal metro-tunnel ranges, cable bundles, shelves and bracket arms must be mesh geometry.

### 1.2 Cable hierarchy / side organization

Engineering rules separate strong-current and weak-current systems.

Typical strong-current vertical ordering in tunnel cable structures:
1. 6/10/20 kV;
2. 825 V traction-related cables;
3. 400/230 V;
4. control cables;
5. trunk / other power-control systems.

Weak-current side carries communications, signaling, interlocking/blocking and control systems.

In two-track tunnels, mixed placement on both sides may be permitted by the project when separation requirements are met.

This hierarchy should be represented as semantic cable classes, not as one generic bundle.

### 1.3 Current minimum geometric spacings from SP Table 5.24

Store as constraints, not as default physical object dimensions:

| Parameter | Minimum / range |
|---|---:|
| vertical distance between bracket horns | 125 mm |
| vertical distance between cable shelves | 150 mm |
| bracket spacing, vertical arrangement | 1000–1200 mm |
| bracket spacing, horizontal arrangement | 800–1100 mm |
| cable collector / cable-room clear height where applicable | 1800 mm |
| substation cable-floor clear height where applicable | 2300 mm |

Cable-to-cable clearances depend on voltage/system class. Examples:
- power <=3 kV: 60 mm vertical / 15 mm horizontal;
- 6/10/20 kV: 100 mm vertical;
- <=3 kV to 6/10/20 kV: 100 mm vertical;
- <=1 kV to control: 60 mm vertical / 15 mm horizontal.

These values are useful for procedural packing of cable bundles on shelves.

### 1.4 Bracket anchoring and grounding

Concrete / RC tunnel cable structures are attached:
- to embedded parts where provided;
- or by removable dowel/screw fastening nodes.

Cable brackets and associated metalwork require grounding/bonding. Therefore high-detail geometry may include:
- grounding conductor;
- bonding jumper;
- clamp;
- anchor plate / embedded insert;
- bracket base plate;
- anchor bolt / dowel head.

### 1.5 Crossing from one side to the other

Cable-side change should be modeled as an event, not as arbitrary interpolation.

Current geometry/clearance rules constrain overhead crossings, especially in tighter circular curves. In a circular tunnel R <= 350 m, ordinary cable transfer through the crown within the Cмк–Oм space is restricted.

At designed crossing points, cable runs may use:
- special supporting structures;
- short-pitch brackets, commonly around 1 m in historical/current engineering practice;
- clamps to prevent movement.

Do not route permanent cables underneath the track unless an explicit project source permits it.

### 1.6 Traction-return / 825 V special runs

Historical/current-compatible metro practice places some traction jumper/return cables on additional brackets below the main cable system.

Keep as a configurable subsystem:
`TRACTION_CABLE_LOWER_BRACKET_RUN`.

---

## 2. Lighting

### 2.1 Current illumination requirements

Current tunnel lighting requirements include:
- ordinary running/dead-end/connecting tunnels: **20 lx at UGR**;
- station-approach / braking zones: higher illumination;
- working + emergency lighting on station approaches and braking zones;
- luminaires must not reduce visibility or correct perception of signal aspects.

Historical/current design tables give:
- 150 m before platform: **60 lx**;
- 25 m after platform: **60 lx**.

Portal adaptation sequence from a documented metro design table:
- 0–5 m: 1000 lx;
- 5–25 m: 750 lx;
- 25–50 m: 500 lx;
- 50–75 m: 300 lx;
- 75–100 m: 150 lx;
- 100–125 m: 60 lx;
- 125–150 m: 20 lx.

The lux target does **not** determine luminaire spacing uniquely. Photometry, mounting height and luminaire family are project parameters.

### 2.2 Historical geometric reference

An older metro lighting engineering reference gives an example rational arrangement:
- spacing around **9 m**;
- mounting height about **2.76 m above UGR**;
- reflector optical axis around 30 degrees to horizontal and 5 degrees to the track axis.

Treat this only as a historical archetype preset, not as a current universal Moscow value.

### 2.3 Do not generalize the 5 m spacing rule

A documented 5 m staggered spacing requirement applies to luminaires over inspection/stabling pit zones in dead-end tracks, not to every ordinary running tunnel.

### 2.4 Geometry model

A luminaire instance should contain:
- housing;
- lens/diffuser;
- mounting bracket;
- conduit/cable entry;
- emergency/working circuit semantic tag.

At LiDAR LOD0 add:
- 5–20 mm bracket thickness;
- wall stand-off;
- mounting bolts;
- short local cable loop.

---

## 3. Evacuation and information signs

Current SP makes several categories visible in tunnels.

### 3.1 Evacuation direction signs
- illuminated;
- placed on the side of the evacuation path;
- mounting height roughly **0.5–1.5 m above walkway/floor**;
- longitudinal interval no more than **25 m**.

Generate these from the evacuation graph, not from a fixed global array, because direction arrows must point toward the actual safe route.

### 3.2 Distance / information signs
Tunnel information signs indicating station-direction/distance are placed with step no more than approximately **160 m** under current rules.

### 3.3 Other visible signs
Include configurable instances for:
- chainage / picket signs;
- speed / operating signs;
- signal designation plates;
- contact-rail hazard plates;
- cross-passage / emergency exit markers;
- tunnel-side equipment identification plates.

Exact artwork should be a material/decal layer; signboard and bracket remain geometry.

---

## 4. Walkway / evacuation geometry

For a single-track tunnel the service/evacuation passage is a continuous geometry system, not an occasional prop.

Current geometric requirements include, depending on tunnel solution:
- side passage clear width around **0.6 m minimum**;
- clear height **>=2.0 m**;
- at about 1.5 m above track-concrete level, clear passage width **>=0.7 m** in the relevant current requirement.

Classic <=5.2 m circular tunnel rule:
- personnel walkway on side opposite contact rail;
- nominal walkway level **+0.2 m above UGR**.

At:
- contact-rail side changes;
- hermetic-gate zones;
- turnout/crossover chambers;
- central-path transitions,

the evacuation surface changes locally. Model these as named topology events.

---

## 5. Water / fire / washing pipeline

### 5.1 Current water main
Current SP:
- tunnel water main nominal diameter at least **DN80**;
- one main in each single-track tunnel;
- mounted **above UGR**;
- normally on the weak-current side;
- if routed on the contact-rail side, it is placed in a casing/protective arrangement;
- a two-track tunnel may have water main on both sides;
- project solutions may route internal-fire-water-supply piping below a central passage in a two-track tunnel.

Exact present-day vertical offset is project-specific.

### 5.2 Historical positional reference
Older metro design rules commonly placed the tunnel water main approximately **0.6–0.8 m above UGR** on the weak-current side.

This is useful as an era preset only. Do not apply it as a current mandatory coordinate.

### 5.3 Irrigation / washing taps
Current:
- irrigation tap diameter >= **20 mm**;
- along running tunnels interval no more than **30 m**;
- short isolated segments still need sufficient taps per design.

Older washing-unit infrastructure also used larger filling points at much longer intervals. Keep those as a historical optional subsystem.

### 5.4 Geometry model
```
WaterMainRun
  pipe_DN
  side
  centerline_z
  wall_standoff
  hanger_pitch
  valve_events[]
  tap_events[]
  sleeve/casing_events[]
```

Model:
- pipe;
- elbows;
- T-pieces;
- isolation valves;
- hose taps;
- wall clamps/hangers;
- casing where present.

Pipe insulation/coating thickness should be project/era-specific.

---

## 6. Signal-related visible geometry

This research does not attempt to reproduce proprietary signaling logic. It only classifies visible geometry.

Potential tunnel objects:
- conventional signal heads where present;
- ATP/automatic-driving sensors near track;
- track circuits / impedance bonds depending on system;
- axle-counter / detection equipment where applicable;
- auto-stop rail / mechanisms on legacy systems;
- cabinets/junction boxes;
- cable connection boxes;
- antenna / radiating-cable supports;
- track beacons / transponders;
- speed and block-section signs.

The lower Oм clearance profile explicitly reserves zones for devices such as automatic-driving sensors and raised auto-stop equipment.

Every signaling object requires:
- semantic ID;
- support geometry;
- protected cable route;
- project/era applicability.

Do not infer signal placement from line speed alone.

---

## 7. Equipment attachment grid

Avoid placing every subsystem on the same longitudinal pitch.

Independent sequences:
- lining ring pitch;
- sleeper/block pitch;
- contact-rail support pitch;
- cable-bracket pitch;
- water-pipe hanger pitch;
- luminaire pitch;
- sign pitch;
- signal/event locations.

This de-synchronization is a key visual characteristic of real tunnel LiDAR.

Recommended deterministic generation:
```python
equipment_seed = hash(project_seed, subsystem, tunnel_id)
phase = deterministic_phase(equipment_seed)
positions = subsystem_rule.generate(s0, s1, phase)
```

---

## 8. LiDAR LOD policy

At close-range LOD0, true mesh:
- bracket arms and bases;
- cable cylinders / bundled cylinders;
- pipe and clamp cross-sections;
- luminaire body;
- sign plates;
- valve bodies;
- grounding strap/conductor;
- anchor bolt heads;
- cabinets and hinge lips;
- cable sag.

At LOD1:
- cable bundle can become grouped oval/circular sweep;
- bolts simplified;
- sign text as material.

At LOD2:
- retain only major cable trays, water main, luminaire bodies, cabinets and signs.

Never bake a cable rack into the lining normal map if the sensor is expected to resolve its silhouette.
