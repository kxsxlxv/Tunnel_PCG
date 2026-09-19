# Running-tunnel typology for Moscow Metro

This file defines the first-pass archetype matrix. It will be refined with project-specific examples and drawings.

## T01 — Legacy circular cast-iron tubing, D_out ≈ 6.0 m
Era: introduced on the second construction stage of Moscow Metro.

Documented technical literature states:
- outer diameter: 6.0 m;
- early ring width: 0.75 m;
- cast-iron segmental lining.

Visual signature:
- strongly ribbed inward-facing tubings;
- dense bolted radial and circumferential joints;
- dark metallic / coated surface;
- track-concrete infill in the invert.

Source:
https://www.metro.ru/library/metropoliteny/233/

Use as a separate archetype; do not scale the later 5.5 m lining uniformly because ring pitch and segment proportions differ.

## T02 — Standard circular cast-iron tubing, D_out 5.5 m / D_in 5.1 m
Documented standard dimensions:
- ring width: 1.0 m;
- outer diameter: 5.5 m;
- inner diameter: 5.1 m;
- traditional tubing rib height: 0.20 m;
- later lightweight variant rib height: 0.15 m;
- bolts for D_out 5.5 m: nominal bolt diameter 27 mm, length about 120 mm.

Ring composition uses:
- normal tubings;
- two tubings adjacent to the key;
- key/closing tubing.

A later arrangement may use a flat combined reinforced-concrete/cast-iron invert element.

Sources:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/
https://www.metro.ru/library/metropoliteny/233/

This is one of the most important LiDAR archetypes because the internal ribs, bolt rows, segment seams and flat/infilled invert are all geometrically conspicuous.

## T03 — Circular precast reinforced-concrete block lining, legacy unified types
Introduced in Moscow on a large scale from the 1950s.

Technical literature describes:
- ribbed and solid block variants;
- unified lining systems;
- flat invert element;
- key block;
- variants compressed against the surrounding ground;
- one described ring arrangement: six normal blocks + one invert block + expansion/fixing inserts;
- another described compressed system: eight normal + two invert blocks + four wedges + insert + gasket.

Source:
https://www.metro.ru/library/metropoliteny/233/

Geometry must expose construction-system variants rather than a generic smooth concrete tube:
- segment count;
- radial seams;
- ring seams;
- key block position;
- recessed bolt/tie pockets where present;
- ribbed-vs-solid internal faces.

Exact series dimensions remain a Stage-2 task.

## T04 — Circular monolithic / monolithic-pressed concrete
Historical technical literature gives:
- typical internal diameter for metro running tunnels: 5.5 m;
- lining thickness for monolithic-pressed construction: about 0.37–0.40 m.

Sources:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/
https://www.metro.ru/library/metropoliteny/233/
https://www.metro.ru/library/stroitelstvo_metropolitenov/479/

Visual signature:
- comparatively smooth continuous cylindrical surface;
- formwork-cycle seams rather than discrete precast segments;
- local cold-joint / repair / seepage traces are plausible;
- track-concrete invert remains a separate geometry layer.

## T05 — Cut-and-cover rectangular two-track running tunnel
Typical for shallow construction.

Technical literature states shallow tunnels are commonly rectangular and that open-cut running tunnels are generally two-track.

Sources:
https://www.metro.ru/library/metropoliteny/229/
https://www.metro.ru/library/stroitelstvo_metropolitenov/531/

Structural variants:
- precast reinforced-concrete large elements;
- monolithic walls with “wall in ground” construction plus roof beams/slabs;
- closed-section precast frame / цельносекционная обделка.

A documented full-section unit has external section dimensions reported as 453 × 5140 × 1500 mm in the source text; this value needs drawing-level verification before coding because the first number is likely a section thickness/depth descriptor, not the overall tunnel width.

Sources:
https://www.metro.ru/library/metropoliteny/233/
https://www.metro.ru/library/stroitelstvo_metropolitenov/468

This archetype requires an explicit two-track center spacing parameter, side-wall clearance, central drainage and equipment zones.

## T06 — Modern ~6 m-class TBM single-track segmental RC tunnel
Contemporary Moscow construction widely uses nominal “6 m” TBMs for single-track tunnels.

Official Mosinzhproekt publication for BCL:
- TBM class: 6 m;
- ring width: 1.4 m;
- ring consists of 6 blocks;
- ring mass: ~21 t.

Source:
https://mosinzhproekt.ru/wp-content/uploads/2023/03/is_01-full_.pdf

Official city construction example identifies 6 m TBMs on the Rublyovo-Arkhangelskaya line:
https://mosinzhproekt.ru/news/nachalos-stroitelstvo-demontazhno-shhitovoj-kamery-u-stanczii-metro-bulvar-generala-karbysheva/

A 2012 Moscow pricing document records two useful project-specific lining families:
- Herrenknecht transition-tunnel lining: D_out/D_in = 6.0/5.4 m, ring width 1400 mm, 7 blocks;
- NFM running-tunnel lining: D_out/D_in = 5.6/5.1 m, ring width 1400 mm, 8 blocks.

Source:
https://www.mos.ru/upload/documents/oiv/inf_ceny_2012.pdf

Conclusion: **“6 m TBM” does not imply one universal finished diameter or segment count.** Store TBM/lining family separately.

## T07 — Modern ~10 m-class TBM two-track segmental RC tunnel
Moscow introduced large-diameter shields for two-track metro tunnels.

Official sources:
- first use of 10 m-class TBMs for two-track tunnels on the second section of the Nekrasovskaya line:
  https://transport.mos.ru/mostrans/all_news/128989
- BCL also used giant 10 m-class shields:
  https://transport.mos.ru/mostrans/all_news/108873
- Rublyovo-Arkhangelskaya continues to use “Lilia”, diameter >10 m:
  https://stroi.mos.ru/news/sobianin-shchit-ghighant-postroit-uchastok-rubliovo-arkhanghiel-skoi-linii-mietro

Mosinzhproekt BCL engineering infographic:
- ring width: 1.8 m;
- 6 blocks;
- ring mass: ~70 t.

Source:
https://mosinzhproekt.ru/wp-content/uploads/2023/03/is_01-full_.pdf

Generator must parameterize:
- two track centerlines inside one circular lining;
- track-center spacing;
- possible central equipment/cable structure;
- side walkways and evacuation arrangements;
- lining-ring roll/stagger pattern.

## Transition archetypes (must not be ignored)

### Bellmouth / раструб
Widening at junctions, station approaches and branch connections. Often monolithic reinforced concrete or special lining.

### Assembly / dismantling chambers
Circular or enlarged sections around TBM launch/reception.

### Cross-passage intersections
Local penetrations between paired single-track tunnels; they alter point-cloud silhouette near openings.

### Switch / crossover chambers
Large-span or widened structures with track branching. Although not “ordinary running tunnel,” trains traverse them, so a complete route generator needs them.

## Minimum archetype IDs for code

- CAST_IRON_6000_R075
- CAST_IRON_5500_R1000
- CAST_IRON_5500_LIGHT
- RC_BLOCK_LEGACY_RIBBED
- RC_BLOCK_LEGACY_SOLID
- MONOLITHIC_PRESSED_5500
- CUT_COVER_RECT_2T_PRECAST
- CUT_COVER_RECT_2T_DIAPHRAGM_WALL
- TBM_6M_RC_6SEG_R1400
- TBM_5600_5100_RC_8SEG_R1400
- TBM_6000_5400_RC_7SEG_R1400
- TBM_10M_RC_6SEG_R1800_2T
- TRANSITION_BELLMOUTH
- SWITCH_CHAMBER
