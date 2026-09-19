# Standards and normative baseline

## Current baseline

### СП 120.13330.2022 «СНиП 32-02-2003 Метрополитены»
Status: current; effective 2023-01-28. Current text must be read together with later changes, including Change No. 2 approved in 2025.

Primary sources:
- Minstroy: https://www.minstroyrf.gov.ru/docs/306920/
- Rosstandart register: https://protect.gost.ru/sp/details/e5e4aea4-e696-4f57-ba29-2a94cc79ba94
- Consolidated text: https://base.garant.ru/406472751/
- Change No. 2 (2025): https://base.garant.ru/411596597/

Geometry-relevant requirements identified:
- tunnel structures must satisfy ГОСТ 23961 clearances;
- in single-track running tunnels of internal diameter <= 5.2 m, a personnel walkway is placed on the side opposite the contact rail, nominally 0.2 m above rail-head level (УГР);
- drainage is part of the permanent tunnel arrangement; self-flowing channels/pipes, inspection points, etc. are required;
- running/tail/connecting tunnel working illumination is normalized at 20 lx at rail-head level, with higher values on station approaches;
- cabling in tunnels is generally exposed on structures/trays and is therefore LiDAR-visible;
- current evacuation provisions also affect the walkable strip / central path geometry.

### ГОСТ 23961-2024 «Метрополитены. Габариты приближения строений, оборудования и подвижного состава»
Status: current from 2025-06-01.

Primary:
- Rosstandart: https://protect.gost.ru/gost/details/d9e37be2-c5e8-4727-9df3-b84536ed7609

Secondary readable text:
- https://allgosts.ru/93/060/gost_23961-2024

This is the **controlling cross-section standard** for procedural clearance envelopes. It defines:
- building clearance for single-track tunnels;
- equipment clearance;
- rolling-stock clearance;
- curve-dependent offsets;
- different single-track tunnel cases and contact-rail side conditions.

For implementation, the figures from this standard should be transcribed into polygonal clearance profiles rather than approximated with a circle.

### Moscow operating rules
«Правила технической эксплуатации метрополитена в г. Москве», Moscow Government Resolution No. 468-ПП, 2020.

Readable source:
- https://base.garant.ru/73992414/53f89421bbdaf741eb2d1ecc4ddb4c33/

Track-gauge values relevant to procedural track generation:
- straight and R >= 1200 m: 1520 mm;
- R > 600 to < 1200 m: 1524 mm;
- R > 400 to 600 m: 1530 mm;
- R > 125 to 400 m: 1535 mm;
- R > 100 to 125 m: 1540 mm.
Allowed absolute limits in operation: 1512–1548 mm.

## Historical standards

These matter because tunnel geometry reflects the standard in force when the section was built.

### ГОСТ 23961-80
Former clearance standard, heavily relevant to most legacy lines.
- readable: https://allgosts.ru/93/100/gost_23961-80
- archive: https://dokku.standartgost.ru/g/%D0%93%D0%9E%D0%A1%D0%A2_23961-80

### СНиП II-40-80 «Метрополитены»
Historical design standard.
- https://dokku.standartgost.ru/g/%D0%A1%D0%9D%D0%B8%D0%9F_II-40-80

### СНиП 32-02-2003 «Метрополитены»
Superseded by later SP editions but important for 2000s–2010s work.
- MChS copy: https://47.mchs.gov.ru/deyatelnost/stranicy-s-glavnoy/zakonodatelstvo/normativno-pravovye-dokumenty-po-pozharnoy-bezopasnosti/snip-32-02-2003-metropoliteny
- PDF mirror: https://files.stroyinf.ru/Data2/1/4294817/4294817383.pdf

### СП 120.13330.2012
Superseded, but applicable to many recently constructed sections in their design period.
- https://base.garant.ru/70352498/

## Implementation consequence

The generator needs **two independent cross-sections**:
1. structural lining profile;
2. normative clearance/equipment envelope.

They must not be conflated. The structural lining is construction-type-dependent; the clearance profile is track/vehicle/curve-dependent.
