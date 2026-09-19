# Parameter confidence and implementation gates

This document tells the coding agent which values may be used automatically and which must remain unresolved until a project/series source is found.

## Confidence classes

- **A — normative / primary:** current ГОСТ, СП, official operating rule or directly dimensioned normative figure. May be used for validation logic within its applicability.
- **B — official project / engineering:** Moscow Government, Mosinzhproekt, Moscow Transport, current official cost/norm publication. May be used for a named archetype/family, but not generalized outside its stated project/family.
- **C — engineering secondary / historical:** technical textbook, historical construction manual, patent. Suitable for historical archetypes and morphology; do not silently reinterpret as a current requirement.
- **D — visual inference:** photograph/video only. Use for appearance and plausibility; never establish an exact dimension without scale calibration.

## Hard implementation gates

### Values safe to hard-code as rule sets

| Parameter | Value / rule | Confidence |
|---|---|---|
| Cмк circle radius | 2.450 m | A |
| Cмк circle-center z for R50 | +1.700 m from UGR | A |
| Cмк circle-center z for R65 | +1.670 m from UGR | A |
| two-track minimum center spacing, straight/R>=500 m in applicable tunnels | 3.400 m | A |
| current track gauge | radius-dependent 1.520–1.544 m | A |
| R50/R65 nominal rail-profile principal dimensions | ГОСТ Р 51685-2022 | A |
| contact-rail default side logic | current SP rule set | A |
| contact-rail support pitch | current SP ranges | A |
| counterrail required on underground main curves R<300 m | current SP | A |
| service-platform minimum height above UGR in Cмкд case | 1.100 m | A |
| service-platform clear width | >=0.700 m | A |

### Values safe only inside named archetypes

| Archetype parameter | Value | Confidence |
|---|---:|---|
| classic cast-iron OD/ID | 5.5 / 5.1 m | C |
| classic cast-iron ring pitch | 1.0 m | C |
| classic tubing rib/flange height | 0.20 m | C |
| lightweight tubing rib height | 0.15 m | C |
| early 6 m cast-iron documented pitch | 0.75 m | C |
| NFM Moscow 2012 ring | 5.6/5.1 m, 1.4 m width, 8 blocks | B |
| Herrenknecht Moscow 2012 transition ring | 6.0/5.4 m, 1.4 m width, 7 blocks | B |
| BCL 6 m-class ring | 1.4 m width, 6 blocks, ~21 t | B |
| BCL 10 m-class ring | 1.8 m width, 6 blocks, ~70 t | B |
| historic full-section precast box | 4.4 x 5.0 m external, 1.5 m long, 13.3 t | C |

## Parameters that MUST remain unresolved / project-specific

The coding agent must raise a missing-parameter error, select an explicitly named fallback preset, or require an override for:

- exact angular segmentation of each cast-iron ring series;
- exact N/C/K tubing central angles;
- exact modern universal-ring taper and ring-rotation sequence;
- joint-gap width for a particular segmental lining;
- exact bolt-pocket/dowel layout unless documented for that family;
- inner/outer diameters of a generic “10 m-class” two-track tunnel;
- vertical position of tracks inside a >9.4 m circular two-track tunnel;
- track-center spacing below R=500 m without applying the ГОСТ curve calculation;
- exact cable-rack heights and offsets for an unspecified project;
- exact luminaire spacing for an unspecified line/era;
- cross-passage dimensions and spacing without a project source;
- switch chamber / bellmouth geometry without a project source.

## Geometry-versus-validation rule

A normative clearance dimension is not evidence that the physical wall lies on that dimension.

Examples:
- Cмк radius 2.450 m != physical tunnel radius.
- Oм polyline != equipment support position.
- 3.400 m intertrack minimum != universal actual track-center spacing.

The code schema should therefore use separate namespaces:

```
physical_geometry.*
clearance_constraints.*
operational_tolerances.*
visual_condition.*
source_provenance.*
```

## Provenance requirement

Every scalar/vector used to instantiate an archetype should expose:

```json
{
  "value": 5.1,
  "unit": "m",
  "status": "nominal",
  "confidence": "C",
  "source_id": "S007",
  "scope": "CAST_IRON_5500_R1000",
  "inferred": false
}
```

For performance, the runtime generator may use flattened numeric presets, but the source/provenance file must remain available for audit and regeneration.
