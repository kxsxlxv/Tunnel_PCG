# Stage 11/22 — Кольцевая линия: две физические трассы, стрелочные камеры и соединительные ветви

Research date: 2026-09-22.

## 0. Scope and evidence policy

Цель этого документа — инженерный контракт для PCG участка Кольцевой линии, в котором две главные трассы существуют как **два независимых физических track alignment**, а стрелки, съезды и соединительные ветви являются событиями топологического графа.

Правила доказательности:

- OSM используется как источник **physical topology / approximate XY**, но не как исполнительная геодезия.
- Второй путь **никогда** не получается постоянным lateral offset первого.
- Публичные глубины станций не превращаются в UGR/Z без известного surface datum.
- Фотографии подтверждают класс сооружения и материальную систему, но не дают абсолютный размер без масштаба.
- Железнодорожная generic-стрелка не выдаётся за московскую metro turnout.
- Если точная московская модель или размер не найден, поле остаётся `null`, range/constraint либо явно маркированным `FALLBACK`.

Machine contracts:
- `examples/koltsevaya_line_v0/track_topology.json`;
- `data/moscow_turnout_archetypes.json`;
- `data/moscow_junction_civil_archetypes.json`;
- `examples/koltsevaya_line_v0/junction_events.json`;
- `data/koltsevaya_junction_source_pinpoints.json` — exact page/figure/clause locators for the numerical junction contract;
- `reference_impl/tunnel_pcg_ref/osm_track_graph.py`.

---

## 1. Две физические главные трассы

### KOLTSEVAYA_TRACK_A

- operational track: **I главный путь**;
- ring position: **inner**;
- движение: **clockwise**;
- source: S084 + S096;
- station order:
  Белорусская → Новослободская → Проспект Мира → Комсомольская → Курская → Таганская → Павелецкая → Добрынинская → Октябрьская → Парк культуры → Киевская → Краснопресненская → Белорусская.

S084 — текущая публикация Московского транспорта о выдаче поездов из ТЧ «Красная Пресня»: первый путь — движение по часовой стрелке, второй — против часовой.  
S096 — учебный материал по пути метрополитена, где внутренний путь Кольцевой, движение по часовой стрелке, прямо назван первым путём.

### KOLTSEVAYA_TRACK_B

- operational track: **II главный путь**;
- ring position: **outer**;
- движение: **counterclockwise**;
- source: S084 + S096;
- station order:
  Белорусская → Краснопресненская → Киевская → Парк культуры → Октябрьская → Добрынинская → Павелецкая → Таганская → Курская → Комсомольская → Проспект Мира → Новослободская → Белорусская.

### Physical centerline status

Текущая OSM hierarchy теперь разрешена непосредственно по OpenStreetMap:

- `r1462012` — `type=route_master`, `route_master=subway`, Line 5 (S099);
- `r300607` — текущая `route=subway` **Circle line (Inner)** (S100);
- `r1462011` — текущая `route=subway` **Circle line (Outer)** (S101).

Поэтому:
- `KOLTSEVAYA_TRACK_A.osm_route_relation_ids = [300607]`;
- `KOLTSEVAYA_TRACK_B.osm_route_relation_ids = [1462011]`.

Это исправляет прежнее pilot-предположение, что relation 300607 является только устаревшим ID. В текущем OSM это действующий child route внутреннего кольца.

При этом в исследовательском runtime всё ещё не удалось получить `relation/full` bytes, поэтому **не внесены вымышленные OSM way IDs, switch node IDs или physical centerline vertices**. Поля `osm_way_ids` и `physical_centerline_file` остаются `null`.

Правильный upgrade path:

1. получить `relation/300607/full` и `relation/1462011/full` либо эквивалентные объекты из Moscow PBF;
2. сохранить физические `railway=subway` ways и исходные OSM node IDs отдельно для каждого child route;
3. построить физический граф без выбора ветви;
4. проверить непрерывность каждой главной цепи;
5. сопоставить Inner с source-backed I/clockwise и Outer с II/counterclockwise;
6. сохранить две centerline независимо.

Наличие двух отдельных текущих route relations является ещё одним независимым основанием не сводить Line 5 к одной оси.

### Local project evidence that the two main tracks have independent chainage

S054, the 2024 Moscow project/expertise for the future Dostoevskaya insertion zone, gives separate existing-Line-5 project PK intervals:

- **right main track:** PK147+48.991 → PK157+01.926, derived track-local span **952.935 m**;
- **left main track:** PK147+46.010 → PK157+02.021, derived track-local span **956.011 m**.

The derived span difference is **3.076 m** over this project zone.

This is useful evidence for the PCG contract because the two physical tracks are already handled as separate project alignments with separate chainage ranges. It is **not** an inter-track spacing measurement. The project labels `right` / `left` are also **not yet mapped** to `KOLTSEVAYA_TRACK_A/B`; that mapping remains null until a project orientation/track-number source resolves it.

The same source gives **25.4 m intertrack spacing** for the **future Dostoevskaya deep pylon station**. That is a station-zone civil value and must not be reused as ordinary running-tunnel spacing.

The referenced project set explicitly contains a 1:500 line plan and a 1:200 vertical longitudinal profile, but those sheets themselves are not included in the published expertise PDF. They remain a high-value acquisition target.

### Межосевое расстояние, взаимный Z и обделка

Для Line 5 целиком пока не найден публичный исполнительный источник, который давал бы функции:

- `axis_spacing_A_B(chainage)`;
- `delta_z_A_B(chainage)`;
- `lining_family_A/B(chainage)`.

Эти поля остаются `null`. Не допускается считать межосевое постоянным.

---

## 2. Physical track graph contract

Старый `stitch_simple_component()` остаётся консервативным: degree > 2 отвергается.

Новый `osm_track_graph.py::extract_physical_track_graph()` делает другое: **не выбирает маршрут**, а сохраняет граф.

### Сущности

`TRACK_EDGE`
- один физический путь/часть OSM way;
- собственная centerline;
- from/to OSM node;
- полный `osm_node_refs`;
- original way tags;
- никакого автоматически назначенного main/depot semantic.

`SWITCH_NODE`
- graph node degree > 2;
- координата из OSM XY;
- `z_ugr_m=null`, пока нет инженерного профиля;
- extractor не угадывает straight/diverging/handedness.

`CROSSOVER`
- semantic object поверх одного или нескольких switch nodes/edges;
- создаётся только после source-backed аннотации;
- связывает две главные трассы.

`BRANCH_EDGE`
- semantic subtype/annotation для TRACK_EDGE;
- соединительная ветвь к депо, тупику или другой линии;
- extractor сам не присваивает этот статус.

`END_NODE`
- degree 1 на границе исследуемой сети либо намеренный PCG cut marker.

### SWITCH_NODE semantic fields

Для geometry-agent после аннотации требуются:

- `node_id`;
- `world/engineering_xy`;
- `z_ugr_m`;
- `incoming_edge`;
- `straight_outgoing_edge`;
- `diverging_outgoing_edge`;
- `turnout_archetype_id`;
- `handedness`;
- `orientation`;
- `civil_chamber_archetype_id`.

Пока OSM/project geometry не получена, значения, зависящие от actual switch coordinate, остаются `null`.

---

### Route-member graph is not enough for junction discovery

The current route relations resolve the two passenger directions, but a depot or service branch can be a physical `railway=subway` way that is not a member of either passenger route. Therefore the reference acquisition pipeline has two layers:

1. `300607 Inner` and `1462011 Outer` seed the two main-track candidate sets;
2. `tools_extract_connected_subway_graph.py` expands through shared OSM nodes into connected off-route physical subway ways.

The expansion hop count is only an acquisition boundary. It does not assign `BRANCH_EDGE`, `CROSSOVER`, straight/diverging, or depot semantics. Those are applied only from the researched source contract.

## 3. Подтверждённые track-development systems Line 5

Это **топологические** подтверждения. Точные OSM/engineering XY требуют дальнейшего извлечения physical graph.

| System | Подтверждённое назначение | Source |
|---|---|---|
| Красная Пресня / Белорусская / Краснопресненская | подключение собственного электродепо; выдача поездов на I и II путь; оборотные/отстойные пути | S084, S085, S086, S087, S093 |
| Проспект Мира | 3 стрелки, оборотный/отстойный путь, продолжение в ССВ с Калужско-Рижской | S085, S088 |
| Курская | 5 стрелок, оборотный/отстойный путь, ССВ с Люблинско-Дмитровской | S085, S089 |
| Таганская / Марксистская system | служебные связи Кольцевой с Таганско-Краснопресненской и Калининской системами | S085, S092 |
| Павелецкая — Добрынинская system | оборотное развитие и ССВ к Замоскворецкой / Калужско-Рижской / Серпуховско-Тимирязевской | S085, S090 |
| Парк культуры | 5 стрелок, оборотный/отстойный путь, однопутная ССВ к Сокольнической, PTO | S085, S091 |

Не все перечисленные системы означают простой одиночный turnout. Многие — это несколько стрелок, тупик/оборотный путь и последующая соединительная ветвь.

### Полный current station-level inventory

Для operating-state `KOL5_OPERATING_2026_09_PRE_DOSTOEVSKAYA` станции разделены на **station track development** и отдельные nearby network junctions:

| Station | Current station track development | Contract |
|---|---|---|
| Белорусская | yes | 3-switch turnback/depot system, S086/S093 |
| Новослободская | no | S108 |
| Проспект Мира | yes | 3 turnouts + 1 reversing/storage track → KRL SSV, S088 |
| Комсомольская | no | S109 |
| Курская | yes | 5 turnouts + 1 reversing/storage track → LDL SSV, S089/S104 |
| Таганская | **no at the station** | S110; nearby service-connection system is a separate network object S092 |
| Павелецкая | yes | 3 turnouts + 1 reversing/storage track → multi-line SSV system, S090 |
| Добрынинская | no | S111 |
| Октябрьская | no | S112 |
| Парк культуры | yes | 5 turnouts + reversing/storage + single-track SSV to Sokolnicheskaya, S091/S105 |
| Киевская | no | S113 |
| Краснопресненская | yes | 3 turnouts + reversing/storage/depot connection, S087/S084/S098 |

This prevents a common topology error: a service connection in the **Taganskaya area** must not be attached to the Taganskaya station object merely because the station page is nearby in plan.

### Temporal topology: future Dostoevskaya

S114 is stored as a **separate future state**, not current operating Line 5:

- planned station opening: 2030;
- planned station development: **4 turnouts + 2 storage tracks**;
- additionally **3 turnouts + 1 reversing/storage track leading to the KRL SSV**, currently attributed to Prospekt Mira, are planned to become part of Dostoevskaya development;
- construction uses bypass tunnels/switching chambers to keep Line 5 operating.

Therefore the procedural graph must have a topology epoch/preset. The 2026 normal-operating graph must not silently include the future Dostoevskaya station graph or construction bypasses.

### Additional switch-number anchors on Line 5

S133 gives two useful operational topology anchors without claiming engineering XY:

- **Prospekt Mira KRL SSV:** turnouts **No.5, No.6, No.7** are explicitly listed as the service-connection switch set; exact mapping of each number to individual graph edges remains unresolved.
- **Taganskaya area:** **switch No.5 on Line-5 Track I** is explicitly identified before Taganskaya; until 2023 the associated signals/switch were controlled from the TKL Taganskaya interlocking.

These are stored as semantic switch-node anchors only. They do not supply branch radii, chainage, Z or chamber dimensions.

### Дополнительные actual-site visual anchors

После выбора Белорусской как первого depot-side topology archetype удалось найти два полезных реальных фото-набора для валидации морфологии:

**Курская — ССВ на Люблинско-Дмитровскую / Чкаловскую систему (S104).**
Фотоочерк с подписями фиксирует:
- стрелку №4 на **II пути**, причём II путь прямо назван внешним кольцом; вид направлен к Комсомольской;
- бывший оборотный тупик за Курской, в который в 1990-е была врезана новая камера для ССВ;
- от существующего развития ССВ **уходит вниз влево** — это source-backed qualitative vertical relation, но не численное ΔZ;
- новую камеру со **стрелкой №7**;
- камеру выезда через стрелку №4 как полностью монолитную;
- последующее развитие как **комбинированную обделку**: большая часть чугунная, самый широкий пролёт монолитный.

Никакие абсолютные размеры из этих фотографий не снимаются.

**Парк культуры — ССВ на Сокольническую (S105).**
Фотоархив прямо подписывает **стрелку №4** и указывает, что в показанной ориентации ССВ на Сокольническую линию уходит **направо**. Номер главного пути, chainage и инженерные координаты из одной подписи не выводятся.

Эти объекты остаются secondary validation archetypes. Первым depot-oriented junction contract остаётся Белорусская/Красная Пресня, поскольку для него есть одновременно actual-site tunnel-node photo/caption и прямое подтверждение связи с обслуживающим Line 5 депо.

---

## 4. Первый junction archetype: Белорусская → оборотный тупик / ТЧ «Красная Пресня»

ID:
`JUNCTION_KOL5_BELORUSSKAYA_DEPOT_WEST`.

Он выбран потому, что для него одновременно есть:
- track-development description;
- схема Line 5;
- историческая фотография **самого тоннельного узла** с подписью.

### Source-backed actual facts

S093, фотоальбом Метростроя 2017, pp.78–79:

- узел расположен около Белорусской Кольцевой;
- **прямо** уходит **II главный путь** в сторону Краснопресненской;
- **налево** уходит оборотный тупик и ветвь в депо «Красная Пресня»;
- камера съездов выполнена из **чугунных тюбингов**;
- торцевая стена — **монолитный железобетон**;
- первоначальная оклеечная гидроизоляция затем заменялась металлоизоляцией.

Следовательно, для направления Track B этот первый divergence source-backed как **left-hand branch**.

S086 дополнительно подтверждает у Белорусской со стороны Краснопресненской трёхстрелочное развитие оборотного пути, продолжающегося в соединение с депо.

S120 adds an actual-site photo sequence of the same depot connection:
- photo 2: **left = beginning of the depot branch; straight = toward Krasnopresnenskaya**;
- photo 7: explicitly captioned **two-track section of the depot branch**;
- photo 8: a downstream switch divides the branch directions **left toward Belorusskaya / right toward Krasnopresnenskaya**;
- photo 9: a closed-method tunnel segment of the depot branch;
- photo 12: an **experimental permanent-way section**;
- photo 13: a **tunnel gate/shutter ("затвор")** is visible, but its exact engineering type is not identified by the caption;
- photos 16 and 20: the crossover chamber, including a panorama.

S134 now provides the stronger historical engineering statement: the depot is connected to Line 5 by **two single-track branches**, adjoining the crossover-track systems at Belorusskaya and Krasnopresnenskaya. S125 gives later secondary corroboration, and S124 independently uses the same "two separate branches" language. This is compatible with S120 because S120 only proves that a **local depot-side section is two-track** before/around the downstream split.

Therefore the complete Krasnaya Presnya connection is represented as:
- `BRANCH_KRP_BELORUSSKAYA_LEG` — one physical track;
- `BRANCH_KRP_KRASNOPRESNENSKAYA_LEG` — one physical track;
- a downstream local two-track/switch system whose exact node decomposition is still unknown.

The geometry agent may therefore satisfy the first implementation sequence with the **single-track Belorusskaya leg**, but must place the model cut before the unresolved downstream two-track/switch system.

### Historical engineering confirmation of the depot topology

A stronger source than the later encyclopedia summaries is now available.

S134 is the 1983 engineering collection `Мы строим метро` (P.A. Vasyukov, ed.; Moscow Worker), article by A.M. Gorkov `Проектирование трасс метрополитена`. Exact web line 116 states that:

- the Koltsevaya depot was planned west of the ring near Krasnopresnenskaya Zastava;
- it was connected to Line 5 by **two single-track branches**;
- the two branches adjoin the **crossover-track systems at Belorusskaya and Krasnopresnenskaya**;
- the branch/crossover arrangement allows trains to enter/leave the ring without reversing maneuvers;
- the same passage independently describes the inner ring as clockwise and the outer ring as the reverse direction.

This is now the **primary track-count/topology evidence** for the two Line-5 depot legs. S125 remains useful current secondary corroboration, while S120 supplies the later photographed local two-track depot-side section.

The graph interpretation is therefore source-backed at the line-attachment level:

`Belorusskaya crossover system -> one single-track depot branch leg`

and separately

`Krasnopresnenskaya crossover system -> one single-track depot branch leg`.

It is still **not** source-backed to merge these into one continuous two-track `BRANCH_EDGE`; the downstream depot-side multi-edge/switch arrangement remains a separate unresolved graph section.

### Actual-site chamber morphology visible in S120

The S120 photo sequence adds useful **non-dimensional** constraints to S093:

- photos 16 and 20 show a widened underground turnout chamber with a ribbed/cast-iron crown;
- the bifurcation/end zone has two tunnel openings separated by a substantial central wall/pier zone;
- the chamber is visibly not a constant-radius continuation of the ordinary running tunnel;
- S093 independently identifies the end wall as monolithic reinforced concrete.

This is enough to validate the **shape class** of the first civil mesh, but not its size. No chamber span, pier thickness, opening diameter or transition length is taken from the photographs.

### Historical electrical commissioning anchor

S136 adds an official Metrostroy chronology point for the selected branch: on **26 March 1954** voltage was applied to the contact rail of the service branch from Line-5 `Белорусская` to depot `Красная Пресня`, and test running began before commissioning.

Engineering use is deliberately narrow:
- it proves the Belorusskaya depot leg and its contact-rail system were operationally complete enough for energized test running by that date;
- it constrains the original civil/electrical era independently of the later `LEGACY_R65_TIMBER_KD65_2001_REFERENCE` service preset;
- it does **not** identify the original turnout factory project, original rail type at the exact switch, bracket/insulator family, air-gap coordinates or later renewal state.

### Что не установлено для actual chamber

Публичный источник пока не дал:

- switch engineering XY;
- switch chainage;
- UGR/Z;
- длину камеры;
- максимальную ширину/высоту;
- осевые offsets;
- точную раскладку чугунных тюбингов;
- длину transition;
- точку появления самостоятельной круглой branch lining;
- диаметр/обделку ветви после камеры.

Фотография S093 **не используется как масштабный чертёж**.

---

### Actual archival vertical fragment on the Krasnopresnenskaya-side depot branch

A substantially stronger source has now been found for the **other downstream arm of the same Krasnaya Presnya depot-connection system**.

S121 is a 2025 Moscow state historical-cultural expertise/project document. It states that, based on **archival plan-and-elevation data of Moscow Metro structures**, the crown part of the depot branch from the Krasnopresnenskaya side has the following local branch-PK/depth observations:

| Branch-local PK interval | Length | Crown depth below the document's conditional 0.000 datum | Derived crown rise with increasing PK | Derived mean crown rise |
|---|---:|---:|---:|---:|
| ПК6+28 → ПК7+57 | 129 m | ~19.3 → ~14.0 m | ~5.3 m | ~41.09‰ |
| ПК6+45 → ПК7+05 | 60 m | ~18.5 → ~16.3 m | ~2.2 m | ~36.67‰ |
| ~ПК6+65 → ~ПК6+95 | ~30 m | ~17.8 → ~16.7 m | ~1.1 m | ~36.67‰ |

The same document gives site ground-surface absolute elevations **143.17–145.67 m**.

The document also gives two independent vertical-reference pairs inside the ~ПК6+65/~ПК6+95 building footprint:
- at axes **А-Г/5**: crown is ~7.9 m below mark 133.05 and ~3.9 m below mark 129.05 → both independently give a crown mark of **~125.15 m** in the document's concept vertical frame;
- at axes **А/2-3**: ~6.8 m below 133.05 and ~2.8 m below 129.05 → both give **~126.25 m** in that same concept frame.

The double derivation is internally consistent and is stored machine-readably, but the 133.05/129.05 frame is **not yet tied to an explicit geodetic datum**.

These numbers are useful, but the datum semantics are deliberately kept narrow:

- the quoted depth is to the **crown part of the structure**, not to UGR;
- `0.000` is the project concept's conditional datum; its absolute elevation is not resolved here;
- the PK values are **local chainage of the depot branch**, not Line-5 main-track chainage;
- therefore the derived 36–41‰ values are **crown-elevation trends only**, not asserted rail gradients;
- the branch cross-section/radius over these intervals is not given by this paragraph;
- the ~125.15/~126.25 marks are therefore retained as **concept-frame crown elevations**, not absolute Moscow Z.

Machine contract:
`KRASNOPRESNENSKAYA_DEPOT_BRANCH_PROFILE_FRAGMENT_ACTUAL`.

This is the first actual-source vertical/chainage constraint found for the Krasnaya Presnya depot-connection network and should supersede any generic vertical interpolation once the corresponding physical graph edge is identified.

S120 supplies matching construction context but not dimensions: the branch passed a powerful quicksand zone, includes a closed-method section, and the photographed section is explicitly described as having been constructed with ground freezing. Metrostroy's own historical album S093 independently corroborates the same construction class on pp.100-101: this Circle-line depot branch is cited as a difficult deep-to-shallow transition where **ground freezing** was used. S120 also says Dorman's 1971 monograph contained a construction description of this section. The Russian State Library record S123 confirms that the complete 271-page Dorman volume is in open access; the exact relevant pages have not yet been extracted, so no Dorman-specific dimensions are asserted yet.

### Dorman construction constraint: one Line-5 depot branch is 256 m

S135, Ya.A. Dorman's article `Из опыта применения замораживания грунтов на строительстве метрополитена` in the same 1983 engineering collection, adds a real geometric constraint to the depot network:

- a tunnel section at the exit toward Krasnopresnenskoye depot was built using artificial freezing of unstable/quicksand ground;
- **two Koltsevaya crossover chambers** are explicitly included among the frozen-ground construction objects;
- **one of the branches connecting Koltsevaya to the depot is 256 m long**;
- that branch passed under dense residential/industrial development;
- fan-arranged freezing holes formed frozen-ground "tents" above the tunnel;
- about **18,000 linear metres** of freezing holes were drilled for this branch.

The important limitation is explicit: the article says **"one of the branches"** and does not name Belorusskaya versus Krasnopresnenskaya. Therefore `256 m` is stored as an **unassigned one-of-two branch-length constraint**. It must not be assigned to `BRANCH_KRP_BELORUSSKAYA_LEG` or `BRANCH_KRP_KRASNOPRESNENSKAYA_LEG` until an independent plan/chainage source identifies which one Dorman describes.

This strengthens the real construction context but still does not give the switch-to-round-tunnel split point or the branch civil section.

### Adjacent Krasnaya Presnya → TKL branch: actual single-track-tunnel analogue

A contemporary construction source now closes one important **morphology** question for the same depot network, although not for the selected Line-5 branch itself.

S126 (*Метрострой*, 1972 №6) states that, to connect the Krasnaya Presnya depot with the then-new Krasnopresnensky radius, **a single-track tunnel branch** was constructed between «Площадь 1905 года» and «Беговая». The article also states that some sections of the route/depot branches were built by open cut.

S127 is a later photographic record of that actual connection and shows:
- the crossover/divergence chamber where the service branch joins the «Беговая» — «Улица 1905 года» running line;
- the branch viewed from the chamber;
- a hermetic-gate event on the branch.

Engineering implication:
- an actual Krasnaya-Presnya service connection is independently documented to become an **independent one-track tunnel** after its turnout/chamber;
- however, S126 does **not** give the tunnel diameter, lining family, chamber dimensions or switch-to-independent-shell distance;
- therefore this is an actual topology/civil-class analogue, not a dimensional substitute for the 1954 Belorusskaya leg.

Machine archetype:
`KRASNAYA_PRESNYA_BEGOVAYA_SINGLE_TRACK_BRANCH_1972_ACTUAL_CONSTRAINT`.

## 5. Turnout geometry contract

### 5.1 Source-backed constraint

Для обычных стрелочных переводов на главных/оборотных путях:
- frog mark **1:9** — S058, printed p.146; S022 §5.7.1.16;
- рельсовый тип перевода должен соответствовать рельсам участка — S022 §5.7.1.16;
- в описываемой Frolov turnout/crossover zone: **без переходных кривых и без возвышения наружного рельса** — S058, printed p.146.

Для crossovers текущая норма задаёт frog mark **2:9** — S022 §5.7.1.16.

### 5.2 Exact installed Belorusskaya turnout

**UNKNOWN.**

Ни один найденный публичный источник не связывает конкретный заводской project number с этим стрелочным переводом.

### 5.3 First mesh fallback — metro-specific R65 1:9 project 2976.00.000

Sources:
- S094 — Murom Switch Plant catalogue, product/drawing for project 2976.00.000;
- S095 — product technical page.

Это **не generic railway turnout**, а опубликованный metro turnout, но его установка на Белорусской **не доказана**.

Параметры fallback mesh:

| Parameter | Value | Status |
|---|---:|---|
| rail | R65 | source-backed product |
| gauge | 1520 mm | source-backed product |
| frog | 1:9 | source-backed product |
| total length | 31,035 mm | source-backed product |
| initial point radius | 300,000 mm | source-backed product |
| turnout curve radius | 200,060 mm | source-backed product |
| point-tip → turnout center | 12,458 mm | source-backed drawing |
| turnout center → mathematical frog center | 13,722 mm | source-backed drawing |
| point-tip → mathematical frog center | 26,180 mm | source-backed drawing |
| mathematical frog center → rear joint | 2,090 mm | source-backed drawing |
| front joint → point tip | 2,765 mm | reconstructed: 31,035−26,180−2,090 |
| initial point angle βn | 0°27′19.57″ | source-backed drawing |
| frog angle | atan(1/9)=6.34019° | reconstructed from frog mark |
| product speed straight/diverging | 100 / 40 km/h | product capability only |

Component topology:
- straight stock/frame rail + curved point;
- curved stock/frame rail + straight point;
- assembled frog;
- two rail assemblies with independent guard rails;
- connecting strip;
- switch bearers.

Published bearer inventory for project 2976:
17×3.00 m; 10×3.25; 8×3.50; 4×3.75; 6×4.00; 5×4.25; 6×4.50; 4×4.75; 4×5.00; 4×5.25.

Полная longitudinal bearer spacing sequence пока не транскрибирована надёжно — `null`.

**PCG rule:** если project 2976 используется в первой визуальной реализации Белорусской, каждому объекту присваивать:
`fallback=true`,
`installed_model_unconfirmed=true`.

### 5.4 Alternate R50 metro-specific fallback

Civil opening era does **not** determine turnout rail type. To avoid forcing the R65/2001 service preset onto every legacy scene, a second metro-specific family is now machine-readable:

`MOSCOW_METRO_R50_1_9_PROJECT_2891_REFERENCE_FALLBACK` — S107.

Published project 2891.00.000:
- R50, gauge 1520 mm, frog 1:9;
- overall length **31,057 mm**;
- front joint → point tip **4,323 mm**;
- point tip → turnout center **11,132 mm**;
- turnout center → mathematical frog center **13,722 mm**;
- point tip → mathematical frog center **24,854 mm**;
- mathematical frog center → rear joint **1,880 mm**;
- point radius **R297259 mm**;
- turnout curve **R200000 mm**;
- initial point angle **0°40′51.50″**;
- frog angle **6°20′25″**.

This is an alternate **R50 service-era fallback only**. It is not evidence that the 1950s Belorusskaya junction used project 2891, nor that it was installed on Line 5 at all.

The current first-mesh choice remains the R65 project-2976 path because the active Stage-10 service preset is R65/KD65/2001-reference. A geometry agent must switch to the R50 family only via an explicit service-era/site preset.

### 5.5 Legacy 1986-1987 turnout foundation/fastening contract

S117 and S118 close an important geometry gap that a product turnout drawing alone does not resolve: **the local track foundation changes in the turnout zone**.

For the documented Soviet metro construction family:

- turnout/crossover zones use **wooden switch bearers**, not ordinary sleepers embedded in the Stage-10 running-track concrete;
- S117 gives bearer lengths **2.75-6.75 m**;
- a ballast construction extends **15 m before and 15 m after** turnouts;
- ballast thickness beneath sleeper/bearer is **0.30 m**;
- S118 specifies a **rectangular-section concrete trough** beneath the crushed-stone ballast;
- R50 ordinary turnouts are **1:9**, crossovers **2:9**;
- reinforced antiseptic-treated wooden bearers are used;
- rail joints use six-bolt joint bars;
- rails/baseplates are fastened to the bearers with track screws;
- turnout baseplates are **uncanted**; transition back to canted running track uses a special variable-cant baseplate set;
- in the construction sequence the turnout is raised on mounting concrete cubes and then ballast is filled/tamped beneath the bearers.

S117 also gives a useful mesh orientation rule:
- bearers under the points/connecting track up to turnout center are perpendicular to the **straight-track axis**;
- in the frog zone they are perpendicular to the **bisector of the frog angle**.

Machine ID:
`MOSCOW_METRO_R50_1_9_VNIR_1986_LEGACY_CONSTRAINT`.

This is an era-aligned **construction constraint**, not a complete switch-rail plan. It must not be combined silently with project 2891 or 2976: those are separate geometric fallback products with their own fastening families.

---

### 5.4 Component lengths and point-drive family cross-check

Two additional manufacturer/legibility sources strengthen project 2976 without changing its fallback status.

S131, an official Dnipro Switch Plant metro product table for the `2976Dn` analogue family, independently gives:
- stock/frame rail component length **12.500 m**;
- rotating point/ostryak component length **8.300 m**;
- assembled frog component length **4.590 m**;
- total turnout length **31.035 m**;
- radii **300.00 / 200.06 m**;
- paired right/left project variants.

S130 is only a high-resolution supplier mirror, but its geometry image makes several drawing callouts legible:
- point longitudinal projection **8298 mm** next to the 8300 mm component length;
- point-root/heel opening callout **68.4 mm**;
- the known 2765 / 12458 / 13722 / 2090 / 31035 dimension chain;
- grouped bearer-spacing spans **5×520=2600**, **9×525=4725**, **14×505=7070**, **11×525=5775 mm**.

The first two values are therefore stored as project-2976 mesh constraints, but S094 remains the primary numeric authority and S130 remains a C-confidence legibility source. The 68.4 mm callout is **not** interpreted as a track-centerline offset.

From the point-tip datum:
- point root longitudinal station = **2765 + 8298 = 11063 mm** from the front joint.

S132 gives an official product-family compatibility record:
- SP-6 point machine;
- fitting project **16760-00-00 / 16760Dn.00.000**;
- R65 1:9, 1520 mm, metro turnout family 2976Dn;
- fitting mass **132 kg**.

This still does **not** prove that the selected Belorusskaya switch uses SP-6 or that exact fitting set. It only closes a compatible drive family for an optional fallback mesh.

Still unknown for a true turnout LOD0:
- full point opening curve between tip and root;
- point pivot/root hardware;
- exact frog nose and wing-rail surface CAD;
- front/rear chainage split of the known 4.590 m frog around the mathematical center;
- exact guard-rail start/end chainages and flangeway profile;
- complete 67-interval bearer-spacing sequence;
- exact installed plate/fastening package;
- site-specific point-machine rods and detector geometry.

### 5.5 Metro-specific R65/1:9 rail-control geometry from the 2005 instruction

S128 contains more direct rail geometry than the first contract used.

**Table 10, printed p.35** gives the maintained gauge for the R65 / 1520 / curved-secant-point / 1:9 family at named sections:

| Control section | Gauge |
|---|---:|
| frame-rail joints | 1520 mm |
| point tip | 1524 mm |
| point root, diverging route | 1520 mm |
| point root, straight route | 1521 mm |
| middle of turnout curve | 1524 mm |
| frog / end of turnout curve | 1520 mm |

Therefore a mesh must not keep a naive constant 1520 mm working-face spacing through every part of the switch.

**Table 16, printed pp.44–45** is even more useful. It defines the turnout-curve ordinate as the distance from the **working face of the outer rail of the straight direction** to the **working face of the outer/bearing rail of the turnout curve**. The abscissa is measured from the **point root**. For the R65 1:9 normal turnout with 8300 mm point, the 1520-mm-gauge denominator values are:

| x from point root | ordinate |
|---:|---:|
| 0 | 181 mm |
| 2.000 m | 259 mm |
| 4.000 m | 350 mm |
| 6.000 m | 460 mm |
| 8.000 m | 590 mm |
| 10.000 m | 740 mm |
| 12.000 m | 910 mm |
| 14.000 m | 1100 mm |

This table is a direct **working-face validation polyline** for the diverging rail. Combined with the project-2976 point-root longitudinal station at 11063 mm from the front joint, it gives a much stronger rail-plan validator than radius alone. The geometry agent should preserve the source definition: these are rail **working-face ordinates**, not centerline y coordinates.

The same instruction also gives:
- point throw at the first connecting-rod axis: **152 +8/-2 mm** (§2.12.11);
- ordinary rail-joint gap: **8±2 mm**;
- point-root gap: **5±2 mm**;
- frog front and tail joints: **0 mm** nominal gap (§2.12.6);
- at least **12 pairs** of wedge anti-creepers for a tunnel turnout (§2.12.15).

Terminal Table-16 rows after x=14 m have intentionally not been promoted to the machine contract until their 1524/1520 numerator/denominator endpoint semantics are rechecked. The source remains authoritative; the omission is conservative transcription, not a geometry fallback.

### 5.4 Additional source-backed component closure for project 2976

The first R65 fallback can now be meshed more specifically without inventing several component lengths:

- S131, an official Dnipro Switch Plant metro-product table for the 2976Dn/2976 family, gives:
  - stock/frame rail component length **12.500 m**;
  - rotating point component length **8.300 m**;
  - assembled frog component length **4.590 m**;
  - total turnout length **31.035 m**;
  - radii **300.00 / 200.06 m**.
- The high-resolution drawing mirror S130 independently shows a point longitudinal projection callout **8298 mm**. Together with the source-backed point tip at x=2765 mm, this gives a fallback point-root longitudinal station **x≈11063 mm** from the front joint. This is a drawing reconstruction, not an installed-site coordinate.
- S130 also shows a local **68.4 mm** callout at the point heel/root. It is stored only as a local point/stock-rail opening callout; it is **not** promoted to track-centerline offset.
- S132, the official Dnipro component catalogue, links the 2976Dn metro turnout family to **SP-6** through fitting project **16760-00-00 / 16760Dn.00.000**, mass 132 kg. ATIZ S095 instead lists **16737-00-00** as optional equipment for project 2976. Because these public product sources conflict, the selected Belorusskaya point-machine/fitting project remains `null`.
- S132 also dimensions the **SKL65 Dn436** turnout plate family: **370×165 mm**, support thickness **15 mm**, rib height **32 mm**, no rail-seat inclination.
- The alternate SK65 package remains separate. S095 lists **117× SK65 GOST 16277-93**; current GOST S060 Fig.5 provides a cross-era dimensional confirmation of an SK65 mesh family: **370×165 mm**, four **Ø26** holes on **310×100 mm** centers, no rail inclination. This is a fallback geometry confirmation, not proof of the historical Belorusskaya plate.

PCG rule: a fallback turnout selects **one** fastening/package variant. It must not combine the 117-piece SK65 package with the 208-piece SKL65 package.

## 6. Civil shell around turnout

### 6.1 Actual Belorusskaya

KNOWN:
- cast-iron tubing chamber;
- monolithic RC end wall;
- straight Track B + left diverging branch.

UNKNOWN:
- dimensional envelope and detailed tubing layout.

### 6.2 Generic dimensioned metro transition reference

S058, Frolov 2001, printed pp.146–150, Figs.4.33–4.35, даёт **не Белорусскую**, а dimensioned reference последовательного расширения камер.

| Chamber | Length | Civil section | Track-axis separation / offset parameter |
|---|---:|---:|---:|
| 1 | 5.00 m | approach/reference | not fully dimensioned |
| 2 | 10.00 m | circular ID 5.56 m | max 0.70 m |
| 3 | 15.00 m | circular ID 7.20 m | 2.22 m |
| 4 | 11.25 m | circular ID 7.70 m | 3.36 m |
| 5 | 9.75 m | max circular ID 9.00 m; text notes elliptical alternative | 4.46 m |
| 6 | 15.00 m | **two-vault common-wall chamber**: two open single-track lining arches bearing on a concrete/RC wall | exact axis spacing not dimensioned |

Fig.4.34 also provides two useful local axis callout sets without requiring photo-scale inference:

- chamber 5, section 1-1: **2.460 m + 2.000 m = 4.460 m**, which decomposes the published M4 inter-track parameter into offsets from the central section reference; the scan does not unambiguously identify which physical main/branch track should receive the left/right value in a reusable PCG frame;
- chamber 6, section 2-2: raw horizontal callouts **2.050 m** on each side from the track axes toward the central wall/reference zone. The exact dimension datum on the wall is not sufficiently clear in the available scan, so the contract **does not** convert these two labels into a claimed 4.10 m axis spacing.

For chamber 6, Fig.4.34 section 2-2 gives a generic lining-arc reference:
- intrados radius **2.57 m**;
- extrados radius **2.82 m**;
- lining axis **+1.70 m above UGR**;
- one vault carries the main track and the other the connecting track;
- exact central-wall thickness and exact inter-track axis spacing are not dimensioned.

This corrects an earlier reading of Fig.4.34: chamber 6 is **not yet two independent circular running tunnels**. Printed p.150 explicitly describes it as two single-track open linings resting on a common concrete/reinforced-concrete wall. The same text states that the main and connecting tracks become independent single-track tunnels **only when inter-track spacing exceeds 6 m**.

Derived:
- chamber 2 start → chamber 6 start:
  **46.00 m = 10 + 15 + 11.25 + 9.75**;
- chamber 2 start → chamber 6 end:
  **61.00 m**;
- independent single-track tunnel start is therefore only constrained as **later than / not before this 61 m generic progression**, with the additional source condition **inter-track spacing >6 m**. Exact post-chamber-6 chainage is not dimensioned.

Point-tip coordinate inside chamber 2 is not dimensioned; therefore **point-tip → independent branch tunnel distance remains null**.

The source also explains:
- an excessively large circular chamber becomes uneconomic;
- an elongated/elliptical section can be assembled with additional adjacent/key tubings and wedge spacers;
- end gaps between chambers of different spans are filled with monolithic concrete and waterproofed as required.

### Use rule

This sequence may drive a **generic fallback transition algorithm**, but the generated shell must be labelled:
`GENERIC_REFERENCE_NOT_BELORUSSKAYA_AS_BUILT`.

Actual Belorusskaya chamber must not inherit the 5.56 / 7.20 / 7.70 / 9.00 m diameters, chamber lengths, chamber-6 radii or >6 m split criterion as as-built dimensions.

### 6.3 Historical cast-iron chamber references closer to the actual material class

Для Белорусской actual evidence говорит **cast-iron tubings**, поэтому дополнительно зафиксирован более близкий по материалу исторический reference.

S102, ЕНиР Е36-2, вып.2 (1987), §Е36-2-75:
- чугунная тюбинговая камера съездов **D=8.75 m**;
- внутри неё расположен действующий перегонный тоннель **D=6.0 m**;
- кольцо камеры имеет ширину **0.75 m**;
- **11 тюбингов**: ЭК×1, ЭС×2, ЭН×6, НКУ×2, плюс две прокладки;
- НКУ закрепляются анкерными болтами в бетонном фундаменте; прочие тюбинги — болтами со сферическими шайбами.

Это **generic late-Soviet construction reference**, а не проект Белорусской. Для Belorusskaya запрещено автоматически переносить D=8.75 m, D=6.0 m, pitch=0.75 m или эту 11-piece раскладку.

S119 strengthens this morphology class with a 1975 Soviet engineering textbook, printed pp.68–69:

- for deep lines with the two main tracks in **separate single-track tunnels**, a connecting tunnel is accommodated by **progressively widening each running tunnel through crossover chambers**;
- chamber linings may be monolithic concrete, cast-iron tubings or precast reinforced concrete;
- for Moscow Metro, the text explicitly describes widespread chamber construction with **cast-iron tubing crowns bearing on monolithic concrete foundations and concrete inverts**;
- crowns in that Moscow family are reported with spans up to **14 m**;
- the large crowns use standard station/escalator-tunnel tubings with **wedge-shaped cast-iron spacers**;
- the same text defines a **bellmouth / раструб** as gradual widening where a two-track tunnel connects to two single-track tunnels, and notes the same morphology at connecting-tunnel junctions;
- deep-level turnback tracks use special chambers structurally analogous to crossover chambers plus larger-span chambers at the crossover/turnback connections.

The same source gives **12 m** between generic deep turnback-tunnel axes and describes a 1.2×1.2 m inspection ditch plus 1.2 m-high service platforms over 155 m. These are context values for a generic turnback facility, **not dimensions of the Belorusskaya divergence chamber or depot branch**.

S103 remains only secondary corroboration. The 14 m span and the generic turnback dimensions are never promoted to Belorusskaya as-built values.

---

## 7. Contact rail through the turnout event

Непрерывный Stage-10 contact rail через turnout запрещён.

S022 current rules give:

- normally contact rail is on the **left in direction of travel**;
- in turnouts / single and double crossovers it may be placed on the **right** (§5.7.2.2);
- turnout/crossover areas require **air gaps** (§5.7.2.7);
- main-track end ramps: receiving **1:30**, trailing **1:25**;
- connecting-track ramps: **1:25** (§5.7.2.8);
- gap bridgeable by collectors of one car: **≤10 m**;
- deliberately non-bridged gap: **≥14 m**;
- equipment clearance from metallic end-ramp end: **≥0.8 m**;
- rail segment with end ramps: normally **≥18.7 m**, constrained **≥12.5 m** (§5.7.2.9);
- support spacing for applicable turnout/crossover elastic-block construction: **2.20–2.75 m** (§5.7.2.4);
- traction sectioning between main/connecting/depot tracks follows separate sectioning rules (§5.10.4.2, §5.10.4.10).

The legacy construction source S118 is more specific about **how** the turnout event is built:

- gap locations at turnouts/crossovers follow the project **укладочный план** rather than a universal point-tip/frog offset;
- at each documented legacy gap end a **1:25 ramp** is attached **instead of a normal support bracket at that end**;
- contact rail and ramp are joined by **two joint bars on four bolts** during installation;
- when turnouts occur in frequent succession, some gaps may be filled with contact-rail pieces using **side ramps on the track-axis side**;
- the protective box has a separate installation operation over the 1:25 ramp.

This is important for PCG: a legacy switch-zone contact rail is not simply a shortened ordinary periodic rail. It has explicit `GAP`, `END_RAMP`, possible `SIDE_RAMP`, and `PROTECTIVE_BOX_RAMP` events.

A useful historical cross-check is now available from **SNiP II-Д.3-62**, printed p.21 (S122). Clause 5.19 already required contact-rail breaks at turnouts and crossovers, with **1:25** end ramps and equipment at least **0.8 m** from the metal end of the ramp. Clause 5.20 allowed a special exception only on **depot park tracks at speeds ≤25 km/h**: side ramps could be used and the rail break could be omitted. This exception must not be transferred to the selected underground main/depot-connection turnout.

Exact Belorusskaya contact-rail gap positions, feeder cables, disconnectors, point-tip/frog-relative offsets and support coordinates are **UNKNOWN**, because the required local laying plan has not been found.

Therefore contact rail is an **event geometry**:
`ordinary rail → ramp → air gap/sectioning → turnout-side routing → branch rail feed → ordinary branch rail`.

---

### Dimensioned R65 1:9 contact-rail ramp layout

A major gap in the first draft is now closed by **S128 Appendix 6, Fig.10**, printed p.158.

The figure is explicitly titled:
`Расположение концевых отводов на стрелочном переводе типа Р65 марки 1/9`.

Its notes (given for Figs.7–12 on printed p.157) state:
- dimensions are taken from the **metallic ends of the contact-rail ramps**;
- dimensions marked `*` are reference dimensions.

The figure is referenced to **ЦСП — the turnout center** and contains two direction/side variants. The machine contract preserves the raw callouts rather than guessing their local side before the actual contact-rail side is bound:

- upper variant: **11750 min / 2750 max / 29000 min mm**;
- lower variant: **12500* / 2750 max / 29000 min / 11750 min mm**.

This is much stronger than the earlier generic `gap somewhere in turnout zone` rule. For the R65/1:9 service-era fallback, contact-rail ramp endpoints can now be generated from the source figure once the local travel direction and rail side are selected.

The same appendix contains **Fig.12, R65 2/9 crossover**, with a separate multi-leg end-ramp layout. Its raw visible callouts are retained machine-readably rather than replaced by a symmetric approximation.

The selected Belorusskaya actual gap still has no site laying plan, so Fig.10 is a **service-era/type reference**, not proof of the exact historical ramp positions at that junction.

### Service-era contact-rail constraint closest to the 2001 preset

S128, the 2005 `Инструкция по текущему содержанию пути и контактного рельса метрополитенов`, is the closest located operational instruction to the selected `LEGACY_R65_TIMBER_KD65_2001_REFERENCE` preset. It is kept separate from both the 1986 construction norm S118 and the current SP S022.

For turnout/crossover zones it gives:

- turnout/crossover air gaps are **overlapping** and normally **≤7.7 m** (§3.10);
- on a non-main turnout a gap may exceptionally be extended to **10 m** with permission;
- equipment located inside the gap is at least **0.8 m** from the metallic ramp end;
- main-track receiving / trailing ramps are **1:30 / 1:25** (§3.12);
- on existing lines the older **1:25 receiving ramp may remain until reconstruction**;
- station and connecting tracks use **1:25 at both ends**;
- the protective box continues over the **full end-ramp length**;
- ramp end tips are documented as **beech or polyethylene**;
- a contact-rail segment including ramps is normally at least **18.7 m**, with **12.5 m** as an exceptional minimum for main/station/connecting tracks (§3.14).

Therefore the geometry agent must expose at least two selectable contact-rail rule sets: `LEGACY_2005` and `CURRENT_SP120`. Current sectioning values must not silently overwrite the legacy ≤7.7 m overlapping-gap geometry when reproducing the selected historical service preset.

## 8. Track concrete, drainage, walkway and services

Actual-site dimensioned plan for Белорусская switch chamber was not located.

Therefore the following **must not** be extended blindly from periodic Stage-10 tunnel generation:

- track-concrete surface mesh;
- central drain centerline;
- local cross-drains / sumps;
- walkway;
- refuges;
- cable racks;
- cable crossings;
- water pipe;
- luminaires;
- cabinets;
- switch machine;
- signals / autostop / sensors.

### 8.1 Near-service-era turnout foundation: 2005 instruction

S128 materially changes the first PCG turnout mesh relative to the ordinary Stage-10 running-tunnel preset:

- on turnouts/crossovers the rails are laid **without rail inclination / poduklonka** (§2.4.2);
- wooden turnout/crossover bearers are governed by GOST 8816 (§2.9.1);
- a single turnout uses bearers from **3.00 to 5.25 m** long (§2.9.6);
- turnouts and crossovers are laid on **ballast**;
- ordinary **track concrete is omitted under the turnout/crossover** (§2.10.1);
- the no-track-concrete zone continues **5–25 m on each side** of the turnout/crossover;
- minimum compacted ballast thickness in a tunnel turnout/crossover is **0.24 m under each rail** (§2.10.2);
- a **limit rail** is installed in the intertrack when converging/diverging track axes reach **3.400 m** separation; some pre-1963 lines may retain 3.300 m (§2.11.2);
- the limit rail is fixed to sleepers/bearers and its top must not project above UGR;
- counterrail/frog safety geometry is constrained by **≥1472 mm** between counterrail and frog-core working faces and **≤1435 mm** between counterrail and wing-rail working faces (§2.12.2).

This is operationally closer to the 2001 service preset than the 1986 VNiR family. For the first legacy R65 turnout event it has higher service-era relevance than continuing the Stage-10 timber-sleeper-in-track-concrete section through the switch.

S129 (GOST 8816-2003) independently closes the bearer **cross-section and aggregate set** for the R65/R50/R43 1:9 A4 family:

- Type II sawn bearer nominal thickness **160 mm**;
- widened top face **220 mm**; normal top face **175 mm**;
- lower face **250 mm (+20/-5)**;
- sawn-side height **≥120 mm**;
- A4 = **68 bearers**;
- length-count set: 17×3.00, 10×3.25, 8×3.50, 4×3.75, 6×4.00, 5×4.25, 6×4.50, 4×4.75, 4×5.00, 4×5.25 m.

This length-count set exactly matches the project-2976 drawing inventory, providing an independent standard cross-check. The exact **longitudinal order / skew / widened-vs-normal width assignment** of every bearer remains tied to the project laying drawing; the machine contract does not invent it.

Source-backed constraints that can already become events:

**Legacy 1986-1987 permanent-way transition (S117/S118):**
- ordinary sleeper-in-track-concrete generation stops before the turnout event;
- the documented legacy turnout family uses a **rectangular concrete trough + crushed-stone ballast + long wooden switch bearers**;
- ballast extends **15 m before and 15 m after** the turnout, with **0.30 m** beneath the support;
- bearer lengths span **2.75-6.75 m**;
- historical R50 1:9 / 2:9 turnout-crossover construction uses six-bolt rail joints, screw fastening and uncanted turnout plates;
- exact Belorusskaya retention of this R50/1986 arrangement in the 2001-reference service era is **not proven**.

**Current validator/event constraints (S022):**
- turnout has no superelevation in the Frolov reference zone — S058;
- no transition curve in that zone — S058;
- current turnout placement validator: turnout on straight track, longitudinal grade ≤**5‰** normally / ≤**10‰** in difficult conditions, beginning of plan or vertical curves ≥**20 m** from turnout center, station platform start ≥**25 m** from turnout center — S022 §5.3.5;
- current SP requires protective anti-run-over timbers before facing points in the stated main-track condition and at station turnout/crossover locations — S022 §5.7.1.17;
- current SP also requires an UGR-level area near underground turnouts/crossovers for storage of metal turnout/crossover parts; exact pad dimensions are not given — S022 §5.7.1.17;
- at turnout/crossover chambers the evacuation route may cross the permanent way through rails/sleepers; if the contact rail changes side, a **central passage** is required — S022 current evacuation-path rules;
- minimum passage widths: **0.60 m side**, **0.90 m central**; where the route passes in the track gauge through an equipment/contact-rail transition, the covered constrained zone extends at least **1 m beyond each end**;
- illuminated evacuation-direction signs are required at turnout/crossover transition locations;
- current drainage rule for the cited turnout/crossover concrete-track condition: **2×Ø200 mm** pipes, or **3×Ø150 mm** in constrained conditions; trays at least **100×50 mm** (or radius ≥50 mm), grade ≥**0.003**, wells at ≤**20 m**;
- current rules require turnout/crossover limit/clearance markers;
- current electrical rules place trackside power boxes near turnouts, 230/12 V transformer/socket boxes at turnout/ATDP/gate locations, and a dedicated emergency-lighting group for turnout point blades.

These are **current normative event constraints**, not evidence that the original 1950s Belorusskaya chamber had the same service fit-out.

Current foundation rules allow project-specific concrete/ballast/support solutions; do not infer the historical Belorusskaya slab from the modern rule. Project-2976 wooden switch bearers are allowed only as **turnout fallback geometry**, not as proof of the historical as-built chamber.

Therefore PCG handling is explicitly event-based:
`ordinary periodic tunnel services → junction override zone → turnout-specific drainage/passages/power/lighting/signs → ordinary branch/running-tunnel services after the event`.

---

### 8.2 Near-era maintenance storage and safe-passage events

S128 §§7.2–7.4 also closes part of the otherwise vague "safe zones / equipment near turnout" requirement:

- kilometre-stock running/contact rails in tunnels are stored **at the wall**; where a banquette exists, preferably **in breaks in the banquette**;
- rail supports/spacers are placed along the stored rail at no more than roughly **5.5–6 m** spacing;
- spare turnout parts are stored **immediately near the turnout**, but their arrangement must preserve **safe passage for maintenance personnel**;
- the exact spare-parts layout is station-specific and approved by the track division;
- storing turnout parts **between the end of the frog and the limit rail is normally prohibited** and allowed only exceptionally when no other place exists;
- spare stock rails, points and frogs are part of the maintained turnout inventory.

For PCG this creates explicit `STOCK_RAIL_STORAGE` / `TURNOUT_SPARES_STORAGE` events plus a `NO_STORAGE_FROG_TO_LIMIT_RAIL` zone. It still does not define a numeric historical walkway width at Belorusskaya, so that width remains unresolved rather than inferred.

### 8.3 Actual Belorusskaya chamber service presence from photographs

S120 photos 16 and 20 close part of the **object-presence** question for the selected real junction, without supplying dimensions:

- the turnout permanent way is visibly carried by **discrete transverse supports/bearers**, with exposed ballast/aggregate zones around them;
- the chamber does **not** visually resemble an ordinary Stage-10 continuous track-concrete section through the switch;
- contact-rail protective-box runs are present around the chamber, but their exact gap/ramp endpoints cannot be measured from the images;
- dense open cable racks occupy **both sidewalls**;
- several electrical/control cabinets stand immediately adjacent to the turnout zone;
- a trackside signal is visible;
- local chamber lighting is visible;
- service-access steps/platform elements are present at the chamber sides.

For PCG these observations are event-presence constraints only. The numeric turnout foundation remains governed by the tagged service-era rule set (S128/S129/project 2976 fallback), and contact-rail endpoints remain governed by S128 Fig.10 rather than photo measurement.

### Current turnout service events for a modern-retrofit preset

For a **current/modern retrofit** event preset only, S022 now closes several previously generic service placeholders:

- point-blade zone working/emergency lighting: **20 lx at UGR**;
- point blades have a **separate emergency-lighting group**;
- maintenance power boxes are installed at turnouts;
- local **230/12 V transformer/socket boxes** are installed at turnout / ATDP / tunnel-gate locations;
- an UGR-level turnout-parts storage area is required, but its plan dimensions are project-specific;
- limit/clearance marker geometry is mandatory, but its exact local position still depends on the turnout layout.

These are encoded as event objects, not repeated periodic tunnel assets, and are not evidence of the original 1950s Belorusskaya fit-out.

## 9. Exit of the branch

Target PCG sequence:

`main running tunnel`
→ `turnout / divergence chamber`
→ `branch transition`
→ `independent single-track branch tunnel`
→ `END_NODE / cut marker`.

For actual Belorusskaya / Krasnaya Presnya depot connection:
- **existence of a tunnel-branch is source-backed**: S098 explicitly names the tunnel-branch to depot «Красная Пресня»;
- S120 directly shows/captions a **two-track section** of the actual depot branch and a later switch dividing directions toward Belorusskaya and Krasnopresnenskaya; S106 independently gives C-confidence textual corroboration that the main connection is two-track;
- this still does **not** resolve whether every portion shares one common two-track civil shell, uses two separate single-track shells, or changes shell type along the connection;
- for the first local Belorusskaya turnout mesh, a single-track `BRANCH_EDGE` may be cut **before the unresolved downstream merge/two-track system**; it must not be extended through the depot connection as a fabricated single-track tunnel;
- independent branch shell start = `null`;
- civil-shell arrangement = `null`;
- diameter = `null`;
- lining family = `null`;
- Z = `null`;
- cut-marker XY = `null`.

For the generic S058 fallback only:
- chamber 6 begins **46.0 m** after the beginning of chamber 2;
- chamber 6 is a **15 m two-vault common-wall transition chamber**, not yet two independent circular tunnels;
- its open lining arcs use reference radii **Rin=2.57 m / Rout=2.82 m**, with lining axis +**1.70 m** above UGR;
- chamber 6 ends **61.0 m** after the beginning of chamber 2;
- independent single-track tunnels begin only after the inter-track spacing exceeds **6 m**;
- the exact chainage and exact diameter of those independent post-chamber-6 tunnels are **not dimensioned** in the source.

Again: none of these generic dimensions are assigned to the actual Belorusskaya depot branch.

---

## 10. KNOWN / CONSTRAINED / UNKNOWN

| Domain | KNOWN | CONSTRAINED | UNKNOWN |
|---|---|---|---|
| two main tracks | I=inner=clockwise; II=outer=counterclockwise; OSM child routes 300607 Inner / 1462011 Outer are resolved | physical way/node chains must be extracted independently | exact current member way/node IDs |
| junction location | Belorusskaya, Krasnopresnenskaya side; II straight, branch left | multi-switch turnback/depot system | exact switch XY / chainage / Z |
| turnout | ordinary main/turnback turnout uses 1:9 | metro-specific R65 project 2976 usable as tagged fallback | exact installed project at Belorusskaya |
| turnout rails | stock rails, points, frog, guard rails needed; legacy R50 construction family is source-backed | project 2976 R65 and project 2891 R50 are tagged product fallbacks; 1986 VNiR gives foundation/fastening morphology | exact installed rail/project/point machine at Belorusskaya |
| actual chamber | cast-iron tubings + RC end wall | correct visual class confirmed by photo; S102/S103 give generic cast-iron/hybrid morphology references only | actual length/width/height/tubing coordinates |
| generic chamber progression | Frolov 5.56→7.20→7.70→9.00 m widening, then 15 m two-vault common-wall chamber 6 | independent tunnels only after inter-track >6 m; can drive fallback algorithm only | exact post-chamber-6 split chainage and correspondence to Belorusskaya |
| contact rail | must be event-based with gaps/ramps/sectioning | normative ranges known | exact local positions |
| track foundation / drainage / walkway / services | turnout cannot inherit ordinary periodic track concrete; legacy ballasted-trough family and current passage/drainage/power/sign rules are known | event-based legacy/current presets are constrained separately | historical/as-built Belorusskaya foundation plan, drainage levels and service products |
| vertical geometry | no invented Z; S121 now gives actual Krasnopresnenskaya-side depot-branch crown depths at local PK6+28–PK7+57 | crown trend can constrain the downstream branch after graph-edge binding | actual UGR/rail grade, absolute crown Z, Belorusskaya switch Z |
| branch exit | two distinct single-track Line-5 branch legs are source-backed by the 1983 engineering account S134, plus a local depot-side two-track section (S120) | selected Belorusskaya leg may be modeled and cut before unresolved downstream split/common section | exact split/merge chainages, shell arrangement, diameter/lining |

---

### What is now implementable for the selected depot leg

The topology contract is now stronger than the first draft:

- the **Belorusskaya-side Line-5 depot leg is source-backed as a single-track connection** by S134 (S125 later corroboration);
- the **Krasnopresnenskaya-side Line-5 depot leg is a separate single-track connection** by S134 (S125 later corroboration);
- S120 proves that farther depot-side there is a **local two-track section** and then a switch dividing directions toward Belorusskaya/Krasnopresnenskaya;
- therefore the first PCG implementation may safely instantiate one `BRANCH_EDGE` from the Belorusskaya divergence and terminate it at an `END_NODE` **before** the unresolved downstream depot-side merge/two-track/switch system;
- this resolves **track count/topology only**. It does not prove a circular single-track civil shell, its diameter, or the chainage where such a shell begins.

The Krasnopresnenskaya-side leg additionally has S121 archival crown-profile constraints. They must not be copied onto the Belorusskaya leg merely because both serve the same depot.

### Highest-value remaining source acquisition

S121 names several 2024 technical reports that are likely to contain the missing actual geometry:

- `ИСП-24-147` — geotechnical calculation of the lining of existing Moscow Metro structures at the Klimashkina site;
- `Б1210/ОР-24-ИГИ3` — GEOCON engineering-geology **graphical** volume;
- `Б1210/ОР-24-ИГИ1/2` — associated text volumes;
- `24-392-П-КР1` — structural-design volume.

Public search has so far located only the Moscow expertise document that **references** them, not standalone copies. They are recorded as acquisition targets rather than silently treated as available sources.

A second high-value target is Dorman 1971 (S123): RSL marks the complete volume as openly viewable, and S120 specifically says it describes construction of this Krasnaya Presnya branch section. Exact relevant pages are still unresolved.

## 11. Definition of Done A–D

### A. Как построить две независимые physical centerline Кольцевой?

**Route-level contract is resolved; physical way/node centerline extraction is still pending.**

Use current child route 300607 for the Inner candidate chain and 1462011 for the Outer candidate chain, then extract/verify their physical subway-way graphs independently. Map Inner to source-backed clockwise/I and Outer to counterclockwise/II. Never use a constant offset.

### B. Где хотя бы один реальный путь Кольцевой ответвляется от главного тоннеля?

**Answered.**

Белорусская, сторона Краснопресненской: II главный путь идёт прямо к Краснопресненской; налево отходит оборотный тупик и система ветви к ТЧ «Красная Пресня» (S093, S086).

### C. Какая 3D геометрия рельсов и стрелочного перевода нужна?

**Partially answered / constrained, with a usable tagged fallback mesh contract.**

For an ordinary metro turnout the **1:9** frog is source-backed. Project 2976 gives the R65/1520 first-mesh fallback: 31.035 m overall length, R300 m point curve, R200.060 m turnout curve, point-tip → turnout center 12.458 m, turnout center → mathematical frog center 13.722 m, and the stock-rail/point/frog/independent-guard-rail component topology. S128 adds no-poduklonka, ballasted turnout foundation and frog/guard-rail clearance constraints; S129 closes the 68-bearer dimensional set.

Exact installed project, exact point-root/opening profile, full frog/wing-rail CAD, complete bearer longitudinal order, point-machine rods and actual site Z remain unresolved. Project 2976 therefore remains `installed_model_unconfirmed=true`, not an as-built Belorusskaya claim.

### D. Как меняется civil shell до самостоятельного branch tunnel?

**Actual Belorusskaya only partially answered.**

Actual material/class is known (cast iron + RC end wall), but dimensional transformation is unknown. Frolov provides a dimensioned generic widening sequence through chamber 5 and a 15 m **two-vault common-wall chamber 6**; only after inter-track spacing exceeds 6 m do the tracks become independent single-track tunnels. The exact post-chamber-6 split chainage/diameter is not given. This is retained only as a fallback algorithm/reference and never presented as Belorusskaya as-built.

This is the intended hand-off boundary: geometry-agent may implement source-backed topology and explicitly tagged fallback meshes, but must not convert the UNKNOWN column into silent assumptions.
