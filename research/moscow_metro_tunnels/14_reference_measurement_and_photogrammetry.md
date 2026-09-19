# Dimension extraction from photographs and technical images

Purpose: controlled use of photographic references when exact project drawings are unavailable.

## Rule 1 — photographs do not override normative/project dimensions

Source hierarchy remains:
1. dimensioned drawing / standard;
2. official project value;
3. engineering literature;
4. calibrated photograph.

A photograph may fill morphology or estimate a missing dimension only with an explicit `inferred=true` flag and uncertainty.

## Scale anchors

Preferred scale anchors visible in tunnel imagery:

### High confidence if archetype is known
- lining ring pitch:
  - early cast iron: 0.75 m;
  - classic cast iron: 1.0 m;
  - named modern families: 1.4 or 1.8 m;
- running-rail gauge from applicable radius rule;
- R50/R65 rail height: 152 / 180 mm;
- known sleeper size in legacy family: 250 x 160 mm section;
- known contact-rail nominal geometry.

### Medium confidence
- standard sign panels only if exact sign standard is known;
- known cable bracket family;
- door opening with published dimensions.

### Low confidence
- person height;
- train-car dimensions when only partly visible;
- assumed brick/block dimensions;
- visual “TBM diameter”.

## Perspective workflow

For a near-orthogonal wall/lining feature:
1. identify at least four coplanar points;
2. estimate plane homography;
3. rectify image;
4. calibrate using one or more known dimensions;
5. measure target;
6. repeat using a second independent anchor;
7. retain residual error.

For circular-tunnel images:
- do not measure apparent circle diameter directly unless camera intrinsics and pose are known;
- use ring seams / rails / known centerline references instead.

## Uncertainty record

Every photo-derived value:
```json
{
  "value": 0.143,
  "unit": "m",
  "source_photo": "Pxx",
  "method": "planar_homography",
  "scale_anchors": ["ring_pitch_1.0m", "R65_height_0.18m"],
  "sigma": 0.006,
  "confidence": "D",
  "inferred": true
}
```

## Lens distortion

For action cameras/wide-angle tunnel photography:
- estimate radial distortion before measurement;
- straight rails/cable trays are useful calibration lines;
- reject edge-of-frame measurements if distortion is unknown.

## Repeated-feature estimation

Repeated tunnel features improve estimates:
- fit many ring seam positions simultaneously;
- infer mean pitch in image space;
- detect outliers at transitions/wedge rings;
- use robust regression rather than measuring one interval.

This is especially useful for:
- ring pitch;
- cable bracket pitch;
- luminaire pitch;
- sleeper pitch.

## LiDAR-oriented reference use

For synthetic LiDAR, prioritize silhouette/relief measurements:
- rib projection;
- bolt-head projection;
- joint recess;
- cable diameter;
- tray stand-off;
- pipe OD;
- drainage edge height;
- third-rail cover envelope.

Surface colour/texture measurements are lower priority unless the simulated sensor models intensity/reflectance.

## Prohibited inference shortcuts

Do not:
- infer tunnel ID from a photograph by assuming the train is centered;
- infer ring width from a worker;
- infer two-track center spacing from standard gauge;
- scale a tunnel from the nominal TBM name;
- infer cable class from colour alone;
- treat perspective-measured dimensions as exact source data.

Photo-derived geometry belongs in a separate `visual_inference` layer.
