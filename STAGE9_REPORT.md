# Stage 9 — Production geometry / long-tunnel assembly

Stage 9 turns the Stage 1–8 Tunnel Scanner reconstruction into an engine-oriented procedural asset generator.

The target contract is not LiDAR synthesis. The target is stable, continuous geometry suitable for long real-time tunnel scenes and later UNIGINE integration.

## 1. Coordinate model

The canonical production scene remains in global coordinates.

No floating-origin or mandatory coordinate rebasing is applied by the geometry core. This is intentional: the target engine can operate with double precision and the user explicitly permits vertices many kilometres from the origin.

The Stage-9 metadata records:

    globalCoordinates = true
    coordinatePrecisionIntent = "double/global; no mandatory rebasing"

Optional chunk-local coordinates exist only as an export convenience, primarily for Blender or other tools that benefit from smaller local coordinate ranges.

## 2. Physical versus technical partitioning

Physical geometry and export partitioning are separate concepts.

Physical units:

- lining ring;
- lining segment;
- bolt pocket/head;
- one continuous pavement asset;
- one continuous walkway asset;
- two continuous rail assets;
- configured continuous tube/service assets.

Technical unit:

- optional TunnelChunk.

Changing chunk size must not change the physical geometry or the stable parent identity of any physical asset.

## 3. Continuous ancillary infrastructure

Stage 8 represented ancillary structures as one closed mesh per ring. This was useful as a direct reconstruction of the paper but created coincident internal end caps.

Stage 9 does not instantiate Stage-8 ring-local ancillary objects in the production scene.

Instead, the Stage-8 cross-sections become continuous sweeps over the Stage-9 alignment.

Reference production infrastructure:

    1 pavement
    1 walkway
    2 rails
    6 tube-like services

These ten assets exist once per tunnel, regardless of ring count.

## 4. Alignment stations

The production alignment contains:

    tunnel start
    ring 0 centre
    boundary 0/1
    ring 1 centre
    boundary 1/2
    ...
    final ring centre
    tunnel end

For N rings:

    station count = 2*N + 1

At every inter-ring boundary the continuous infrastructure has exactly one cross-section.

No pair of closed ring-local ancillary caps exists there.

## 5. Lining alignment

The original Stage-7 model applied one rigid X/Z translation to each ring. For production geometry that can create small centreline discontinuities at a ring boundary.

Stage 9 production default therefore maps ring-local geometry onto the same piecewise-linear alignment used by the continuous infrastructure.

The lining segments, bolt pocket cutters and bolt heads use the same local-Y-dependent X/Z map.

This preserves their relative Boolean geometry while ensuring the front/back centre of neighbouring rings refers to one physical tunnel cross-section.

Diagnostic rigid-ring behaviour remains available with:

    ProductionConfig(stitch_ring_geometry=False)

## 6. Z-fighting and coincident surfaces

Stage 9 uses several complementary cleanup rules.

### Ancillary internal caps

Eliminated by construction. Continuous infrastructure is not represented as N closed ring solids.

### Pavement versus lining contact

The hidden circular pavement perimeter that lies against the tunnel intrados is omitted from the production sweep. Only the tunnel-facing pavement top surface is generated longitudinally.

### Rail versus pavement contact

The rail-foot bottom longitudinal face is omitted. The visible rail profile remains, while the hidden coplanar contact surface against pavement is not generated.

### Stage-4 prescribed outer joint solids

The literal Stage-4 radial ribs and circumferential outer collars are extrados-only reconstruction solids. They are omitted from production scenes by default.

They can still be retained for debugging:

    ProductionConfig(keep_prescribed_outer_joint_solids=True)

### Lining ring end caps

Closed lining meshes are retained until bolt Boolean tools have been baked because Blender Boolean operations require solid geometry.

After Boolean processing, internal longitudinal lining cap faces are removed.

Tunnel start and tunnel end caps remain.

### Lining segment-to-segment boundaries

Radial segment boundary surfaces are also hidden coincident interfaces. A tessellation-independent classifier uses each segment's analytical angular start/end boundaries and removes these surfaces during render finalization.

The classifier does not depend on neighbouring segments having identical polygon subdivision.

## 7. Production render finalization

Engine-neutral finalization:

    finalize_production_render_scene(scene)

requires temporary bolt cutters to be absent.

It performs:

1. internal lining longitudinal cap removal;
2. lining segment radial-interface removal.

The equivalent Blender adapter path performs Boolean operations first and then the same render-surface cleanup.

On the canonical five-ring topology audit:

Stage 8 before cleanup:

    exact duplicate groups: 94

including:

    lining/lining                         30
    circumferential-joint/joint          24
    pavement/pavement                     4
    walkway/walkway                       4
    rail/rail                             8
    tube/tube                            24

Stage 9 source:

    exact duplicate groups: 30
    all remaining groups: lining/lining
    production infrastructure groups: 0
    Stage-4 outer joint solids: absent

Stage 9 finalized:

    exact duplicate groups: 0
    exact duplicate occurrences: 0

The five-ring run removed:

    1246 lining longitudinal-cap faces
    60 segment radial-interface faces

## 8. Rail profile

Stage 8 used rectangular rail prisms because the paper itself treats ancillary geometry coarsely.

Stage 9 replaces those rectangles with a generic low-poly rail-like profile.

It is intentionally not yet a Moscow/Russian rail standard. That belongs to Stage 10.

The profile has:

- broad foot;
- narrow web;
- broad head;
- small shoulder transitions.

Default complexity:

    16 cross-section vertices

Parameterization:

    overall_height_m
    head_width_m
    head_height_m
    web_thickness_m
    foot_width_m
    foot_height_m

The Stage-8 outer rail envelope is preserved by default.

This provides a recognisable rail silhouette without subdivision or excessive polygon count.

## 9. Stable identity contract

Python's runtime hash is not used.

Stage 9 creates deterministic positive 63-bit IDs using BLAKE2b over semantic persistent keys.

Tunnel identity:

    stable_instance_id("<namespace>/tunnel")

Ring-local physical object key:

    <namespace>/ring/<global-ring-id>/<object-name>

Continuous infrastructure key examples:

    <namespace>/infrastructure/rail/0
    <namespace>/infrastructure/rail/1
    <namespace>/infrastructure/tube/<service-name>

Every production object carries:

    persistentKey
    persistentInstanceID
    tunnelInstanceID

Continuous infrastructure additionally carries:

    infrastructureID

These parent physical IDs do not depend on chunk size.

## 10. Chunk identity

A chunk piece is a technical export object, not a new physical rail or pipe.

Its piece instance ID may depend on chunk boundary because the piece itself changes.

Each chunked infrastructure object therefore also carries the stable parent identity:

    sourcePersistentKey
    sourceInstanceID
    sourceInfrastructureID

Changing 25 m chunks to 50 m chunks changes piece IDs but does not change the parent infrastructure ID.

## 11. Chunk boundary policy

Default:

    ring_aligned

The requested chunk length is treated as an approximate target. Boundaries are snapped to complete lining rings so a physical ring does not straddle two streamed chunks.

A diagnostic/export mode also exists:

    exact_length

It can cut continuous infrastructure at exact metric positions but should not be treated as the preferred streaming partition when full ring objects are also present.

## 12. Global versus localized chunks

Default chunk coordinates remain global.

Optional:

    localize_coordinates=True

or CLI:

    --localize-chunks-for-blender

subtracts a chunk origin from chunk vertices and writes the world origin into metadata.

The stable IDs do not change.

The full production scene itself never requires this localization.

## 13. Chunks-only serialization

For kilometre-scale Blender/export workflows the Stage-9 generator supports:

    --chunk-m <length>
    --chunks-only

This skips writing the monolithic full-scene JSON and serializes only chunk packages plus a manifest.

The generator still uses global coordinates as the canonical geometry model.

The manifest records:

- tunnelInstanceID;
- persistent infrastructure keys and IDs;
- chunk chainage ranges;
- global ring IDs;
- optional chunk world origins;
- boundary policy.

## 14. Hierarchy

Production hierarchy is semantic and deterministic.

Ring-local geometry:

    Tunnel/
        <namespace>/
            Rings/
                Ring_00000000/
                Ring_00000001/
                ...

Continuous infrastructure:

    Tunnel/
        <namespace>/
            Infrastructure/
                Pavement/
                Walkway/
                Rails/
                Tubes/

Optional chunk package prefix:

    Chunks/
        Chunk_00000/
        Chunk_00001/
        ...

Chunking does not replace global ring IDs or physical infrastructure IDs.

## 15. Long-tunnel verification

Latest CI baseline before Stage 9J:

### 100 m full geometry

    requested length: 100 m
    rings: 75
    generated length: 101.25 m
    scene objects: 460
    CI generation time: ~0.54 s

After render finalization:

    longitudinal lining-cap faces removed: 19508
    segment-interface faces removed: 944
    exact duplicate face groups: 0

### 1 km full geometry

    requested length: 1000 m
    rings: 741
    generated length: 1000.35 m
    scene objects: 4456
    alignment stations: 1483
    rail vertices per rail: 23728
    rail faces per rail: 22232
    CI generation time: ~18.3 s

### 5 km alignment stress

    rings: 3704
    generated length: 5000.4 m
    alignment stations: 7409
    last world Y: 4999.725 m

This 5 km test intentionally validates the global-double alignment model without allocating every lining mesh.

Stage 9J additionally builds the full set of 1 km ring-aligned chunk packages and verifies unique ring coverage and exact infrastructure cross-section continuity.

## 16. Topology verification

Independent trimesh 5.1.0 validation checks all ten production infrastructure assets.

Expected intentionally open contact meshes:

    pavement
    rail 0
    rail 1

They are open because hidden contact faces are deliberately omitted.

Expected closed meshes:

    walkway
    six tube-like services

Latest result:

    production assets checked: 10
    expected open contact meshes: 3
    expected closed meshes: 7
    failures: 0
    PASS

## 17. Blender path

The Stage-9 Blender verifier imports the production ScenePackage and:

1. runs Stage-6 bolt Booleans;
2. removes pocket cutter tools;
3. strips internal lining ring caps;
4. strips coincident lining segment boundary faces;
5. verifies the 16-vertex rail profile and persistent IDs.

Use:

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --rings 20

    blender --background --python scripts/blender_verify_stage9.py -- \
        examples/stage9_production_scene.json \
        --report examples/blender_stage9_runtime_report.json \
        --save-blend examples/stage9_production_scene.blend

For a long Blender scene:

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --length-m 1000 \
        --chunk-m 50 \
        --chunks-only \
        --localize-chunks-for-blender

## 18. Production limitations intentionally deferred to Stage 10

Stage 9 does not introduce Moscow Metro engineering standards.

In particular it does not yet define:

- Russian/Moscow tunnel diameter/profile;
- actual Russian rail section;
- Moscow track gauge configuration;
- sleepers and rail fasteners;
- central drainage/track trough;
- Moscow cable/support layout;
- absence/replacement of the current Tunnel-Scanner walkway;
- line/era-specific lining and service arrangements.

Those are domain-profile changes and belong to Stage 10.

## 19. Stage-9 completion criteria

Stage 9 is complete when:

- full CI is green;
- 1 km chunk packages build and preserve unique global ring coverage;
- infrastructure cross-sections match exactly across chunk boundaries;
- final render topology has zero exact duplicate faces;
- persistent parent IDs are invariant to chunk size;
- Blender verifies Boolean + lining cleanup + rail profile on a representative short scene.

The first five criteria are automated. The last criterion requires the user's real Blender installation.
