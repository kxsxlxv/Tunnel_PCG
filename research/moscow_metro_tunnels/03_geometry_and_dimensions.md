# Geometry and dimensions — verified starter set

All dimensions are in SI units in code. Preserve the original source unit in metadata.

## Circular cast-iron lining

### Standard 5.5 / 5.1 m ring
- outer diameter: 5.500 m
- inner diameter: 5.100 m
- radial structural depth: 0.200 m
- ring pitch: 1.000 m
- inward rib/flange height (traditional): 0.200 m
- inward rib/flange height (lightweight generation): 0.150 m
- typical fastening for 5.5 m lining: bolt Ø27 mm, length ~120 mm

Source:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/

### Earlier 6.0 m cast-iron ring
- outer diameter: 6.000 m
- ring pitch: 0.750 m on the early Moscow implementation
- later 6.0 m variants also existed.

Source:
https://www.metro.ru/library/metropoliteny/233/

## Circular monolithic pressed concrete
- nominal internal diameter: 5.500 m
- lining thickness: approximately 0.370–0.400 m

Sources:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/
https://www.metro.ru/library/metropoliteny/233/

## Modern precast segment rings

### BCL “6 m-class” single-track
- ring pitch: 1.400 m
- segment count: 6
- ring mass: ~21 t
- shield class: 6 m

Source:
Mosinzhproekt engineering publication:
https://mosinzhproekt.ru/wp-content/uploads/2023/03/is_01-full_.pdf

### BCL “10 m-class” two-track
- ring pitch: 1.800 m
- segment count: 6
- ring mass: ~70 t
- shield class: 10 m

Same source.

### Project-specific 2012 Moscow lining references
From Moscow construction-price documentation:
1. Herrenknecht transition tunnel:
   - D_out = 6.000 m
   - D_in = 5.400 m
   - thickness = 0.300 m
   - ring width = 1.400 m
   - 7 blocks/ring
2. NFM running tunnel:
   - D_out = 5.600 m
   - D_in = 5.100 m
   - thickness = 0.250 m
   - ring width = 1.400 m
   - 8 blocks/ring

Source:
https://www.mos.ru/upload/documents/oiv/inf_ceny_2012.pdf

## Track gauge

Moscow operating values:
- straight and R >= 1200 m: 1.520 m
- 600 < R < 1200 m: 1.524 m
- 400 < R <= 600 m: 1.530 m
- 125 < R <= 400 m: 1.535 m
- 100 < R <= 125 m: 1.540 m

Source:
https://base.garant.ru/73992414/53f89421bbdaf741eb2d1ecc4ddb4c33/

Generator implication:
track gauge is a curve-dependent parameter, not a global constant.

## Legacy permanent way / track slab

Engineering text for metro tunnels:
- rails traditionally on wooden sleepers embedded in track concrete;
- central drainage channel under the sleepers, width approximately 0.7–0.9 m;
- historical standard tunnel track is ballastless;
- R65 rail is documented as the standard heavy running rail in later periods.

Sources:
https://www.metro.ru/library/stroitelstvo_metropolitenov/524/
https://www.metro.ru/library/metropoliteny/243/

At portals / selected special zones, ballast track can occur; do not assume concrete everywhere.

## Contact rail

Historical Moscow description:
- generally mounted to the left side in direction of train travel;
- support brackets roughly every 5 m.

Construction text:
- bracket spacing about 4.25–5.5 m;
- around thermal joints about 2.5 m;
- protective cover over the contact rail.

Sources:
https://www.metro.ru/library/50/441/
https://www.metro.ru/library/stroitelstvo_metropolitenov/491/

Exact transverse/vertical contact-rail placement must come from ГОСТ 23961 profiles in the next stage.

## Walkway and drainage

Current SP:
- in single-track tunnels with internal diameter <= 5.2 m, personnel walkway on side opposite contact rail;
- nominal walkway height: 0.2 m above rail-head level;
- modern evacuation arrangements may use a central path or side path depending on design;
- minimum drainage channels in general facilities: 100 × 50(h) mm or equivalent radius >= 50 mm;
- drainage slope generally >= 0.003;
- legacy central tunnel drainage is much larger where integrated below the track.

Source:
https://base.garant.ru/406472751/

## Coordinate convention recommended for Blender generator

Use right-handed local tunnel coordinates:
- +X = chainage / travel direction;
- +Y = left from direction of increasing chainage;
- +Z = up;
- rail-head reference plane z = 0;
- track centerline y = 0 for single-track archetypes.

Do not use lining center as the universal origin because the track may be vertically and laterally offset by curve/cant/clearance requirements.
