# CityGen — Traffic, Crowd & City Life Simulation Research

**Status:** research + **design spec v0 for later pickup — §12.** Sweep run 2026-08-18, spec
written 2026-08-19, branch `cityGen`. **No build started.**
**This file owns:** everything that moves in the city — vehicles, pedestrians, animals — the rules
they obey, the libraries they come from, and the tools the artist uses to direct them. It is the
subsystem doc [`citygen.md`](citygen.md) promised when it deferred *"traffic and pedestrian
simulation"*.
**It does NOT own:** the street graph (that is [`citygen_streets.md`](citygen_streets.md)), building
generation ([`citygen_buildings.md`](citygen_buildings.md)), or vegetation ([`foliage.md`](foliage.md)).
Where this file says the street schema must grow, the change belongs in the streets doc and is
recorded there, not duplicated here.
**Artist-facing UI:** [`artist_ui.md`](artist_ui.md) §6b audits this doc — the §10.5 authoring
tools and the area+POI primitive already match the evidence; the added obligation is a
proxy-density preview mode in the spec from day one (its Theme-4 heaviness finding).

**Reference library:** `polyfactory/resources/citygen/README.md` — gitignored, local only. The two
survey PDFs cited as the spine of §3 were downloaded into `resources/citygen/papers/` by this sweep.

⚠️ **Sequencing, stated up front.** Streets V1 is *not finished* — §S6's seam is open, the
planner/builder split (streets §11) is mid-flight, and the mesher still ignores half of what the
trace writes (streets §4c). Nothing in this document should be built before that lands. This is a
map of the territory so the street schema stops being designed blind, not a work order. The one
thing worth doing *now* is small and belongs to streets anyway: make the graph capable of carrying
lane data (§10.1). Everything else waits. **The pickup spec is §12** and it inherits this
sequencing: nothing builds before streets V1 closes, except the L0-lite schema additions
(§12.4a) and, at the artist's option, the birds gate P4, which depends on neither.

---

## 1. Headline findings

1. **A centreline graph is not a simulation input. A lane graph is.** This is the single most
   consequential finding, and it is stated flatly in the field's own survey: procedural street
   generators *"often fail to provide the necessary information for traffic simulation, such as
   lane-to-lane connections and adjacencies"* (Chao et al. 2020, §2.4 — read directly). Every
   system that actually works — SUMO's net, ASAM OpenDRIVE, Lanelet2, Unreal's ZoneGraph, Golaem's
   traffic lanes, Epic's own City Sample Houdini toolset — consumes **lanes with connectivity and
   rules**, never bare centrelines. Our graph today has `laneWidth` and a `drivable`/`walkable`
   flag on swept cross-section strips. That is roughly 15% of what is needed.
2. **The right-of-way layer is nearly free, because we already decided it.** SUMO derives a
   junction's way-giving rules from road priority, speed and lane count; OpenDRIVE and Lanelet2
   attach the same information as junction/regulatory records. Our `principal_start` /
   `principal_end` booleans (streets §11.3, "widest pair") **are** the major/minor statement, and
   `junction_type` is already a four-value vocabulary that lines up with the standards' junction
   taxonomies. Traffic rules are therefore mostly *derived defaults over data we already compute*,
   which is exactly the cascade in `citygen.md` §2.1 — and the artist override falls out for free.
3. **The simulation is the easy half; the authoring is the product.** Every mature tool has
   converged on a post-simulation, per-agent, non-destructive edit layer — Golaem pivoted its whole
   marketing to it (*"Crowd Simulation is over, step in Character Layout!"*), Houdini 20 shipped
   SOP-level crowd motion paths that bypass the solver entirely, and the most-loved Cities:Skylines
   mod exists solely to let the player overrule the pathfinder. Artists do not ask for better car-
   following equations. They ask to move *that* car.
4. **For an offline-render target, published traffic models are already overkill.** IDM + MOBIL
   lane changing (or the Shen–Jin urban variant) is the field standard and is a few dozen lines of
   VEX. The survey's own open problems are about *fidelity to real measured flow* and autonomous-
   driving validation — questions we do not have to answer. Our fidelity bar is visual.
5. **Houdini ships more of this than expected, and the useful part is the non-simulated part.**
   Verified in the live 22.0.398 session: 14 `popsteer*` behaviours, a full agent/state/trigger
   system, 17 `crowdmotionpath*` SOPs (crowds as *editable geometry*, no DOP network), agent
   terrain adaptation, a render-time crowd procedural — plus `rbdcarrig` with real Ackermann
   steering, suspension and 3-axle truck layouts. The gap is that **none of it knows what a lane
   is**. That gap is ours to fill and it is the same gap §1 describes.
6. **APEX is the right tool for one layer and the wrong tool for two.** Right for per-agent rig
   evaluation and for the layout/re-animation surface (APEX Scene, Motion Mixer, procedural graph
   fusion). Wrong for the traffic solver and wrong for the lane graph. This refines
   `citygen.md` §4b's *"when the splines start driving traffic and crowds, APEX is the obvious
   vehicle"* — half right, and the half that is right is not the driving.
7. **The tool Hannes remembers is 3ds Max Populate, and its successor is anima.** Populate (draw a
   flow, draw an idle area, get looping people) is still documented but community-regarded as
   dated; AXYZ **anima** owns that workflow now and is the archviz default. Its reviewed weaknesses
   are precisely the ones a generator must design against: *close-ups reveal it*, only two base
   actors ship, and filling an area with *standing* people still means hand-rotating most of them.
8. **"What can spawn where" is a solved data problem with a proven vocabulary.** SUMO's `vClass`
   (33 classes) plus per-lane `allow`/`disallow` is the model to copy, extended with density
   attributes (which is exactly what Epic's City Sample writes) and with Kallmann-style *smart
   objects* for anything that is not locomotion — sitting, perching, digging, waiting.

---

## 2. What was asked for

> from the graph of curves generated for the streetnetwork we can use those curves and generate the
> paths for the simulation, cars and pedestrians. Also this means there have to be traffic rules.
> also a library for vehicles, people, dogs, cats, brids, squirrels [...] also rules what can be
> spawned where.
>
> the user [should] be able to fully control the animation and appearence and also add tools so they
> can add more cars of people. I think i remember a tool from 3ds max [...] where the artist could
> just draw a custom area and the tool would spawn people with loopable animations in there
>
> — Hannes, 2026-08-18

Plus, added in the same session: *"I would like to be able to use the houdini crowd tools and apex.
Of course only if it makes sense"* — answered in §7, with a verdict per layer.

Six requirements fall out, and they are not equally hard:

| # | Requirement | Difficulty | Where the answer is |
|---|---|---|---|
| R1 | Curves → simulation paths | **hard, and it is a schema problem** | §4, §6, §10.1 |
| R2 | Traffic rules | medium, mostly derived | §4, §10.2 |
| R3 | Asset library (people, vehicles, animals) | easy to *use*, expensive to *own* | §5e |
| R4 | Spawn rules | easy, copy a proven vocabulary | §10.4 |
| R5 | Full artist control of animation + appearance | **the product** | §5a, §8, §10.5 |
| R6 | Draw-an-area spawn tool | easy once R1/R4 exist | §5b, §10.5 |

---

## 3. The paper map

Two surveys carry this field and both were read directly (text extracted from the PDFs, not from
search snippets):

- **Chao, Bi, Li, Mao, Wang, Lin, Deng — *A Survey on Visual Traffic Simulation* (CGF 39(1), 2020).**
  The spine for vehicles. Taxonomy, lineage, road-network critique, validation, open problems.
- **Khan & Deng — *Agent-based Crowd Simulation: An In-depth Survey of Determining Factors for
  Heterogeneous Behaviour* (TVC, 2024).** The spine for people. Locomotion families plus the
  behavioural layers stacked on top.

### 3a. Vehicles — three levels of detail, and only one of them matters to us

| Class | What it models | Named models | Use for us |
|---|---|---|---|
| **Macroscopic** | flow as a continuum: density, velocity, flux | LWR, ARZ | background/off-camera flow, LOD |
| **Mesoscopic** | groups + probability distributions | cluster, headway, gas-kinetic | **no** — survey: rarely used in CG, too many unknown parameters |
| **Microscopic** | each vehicle an agent | cellular automata (Nagel–Schreckenberg 1992); car-following (Pipes 1953, Reuschel 1950); **OVM** (Bando 1995); **IDM** (Treiber–Helbing 2002); **MOBIL** lane changing (Kesting 2007); Shen–Jin 2012 urban IDM + continuous lane change | **yes, this is the one** |

Two refinements worth having on the shelf:

- **Shen & Jin 2012** splits acceleration into a free-road term and a deceleration term with an
  activation control, and splits lane changes into **free** (MOBIL) and **imperative** (lane ends,
  turn required at the crossing, blockage ahead). Imperative lane changing is the behaviour that
  makes junctions read correctly — and it is exactly what Cities:Skylines' vanilla AI lacks (§8).
- **Sewall, Wang & Lin 2011** is the hybrid: agents in the camera's region of interest, continuum
  everywhere else, switching automatically. That is a **LOD strategy for a city-scale shot**, and it
  is the published answer to "I cannot afford a million agents".

Intersections are called out by the survey as the genuinely hard part: *"simulating traffic at
intersections is more difficult"* than lane-following. Doniec 2008 treats it as multi-agent
coordination with anticipation; Chao 2015 adds rule-based vehicle–pedestrian interaction. Nobody
gets this for free.

**Road-network lineage.** Parish & Müller 2001 → CityEngine → Chen 2008 (our own spine) generate
*roads*. Yang & Koutsopoulos 1996 (node/link/segment/lane, used by MITSIM), VISSIM's link+connector,
and **Wilkie, Sewall & Lin 2012** generate *simulation networks* — Wilkie's is the one that
automatically lifts low-detail GIS into a lane-centric topological structure with arc-road geometry,
released as the **Road Network Library** (RoadLib). The survey's verdict on the first family, quoted
in §1, is the finding that should shape our schema.

### 3b. Pedestrians — four locomotion families, then everything on top

Khan & Deng's Table 1 divides the microscopic literature four ways:

| Family | Canon | Character |
|---|---|---|
| **Rule-based** | Reynolds *Boids* 1987 + steering behaviours | cheap, readable, art-directable; the ancestor of every DCC crowd tool |
| **Social force** | Helbing & Molnár 1995 | forces: goal attraction, personal-space repulsion, obstacle repulsion; produces pushing and lane formation |
| **Cellular automata** | grid-based | cheap at scale, visibly discrete |
| **Velocity-based** | VO → RVO (van den Berg 2008) → **ORCA** (2011), HRVO, PedVO | smoothest avoidance, best behaviour in dense two-way flow |

Above locomotion the survey stacks: personality/emotion models (OCEAN, PEN, BDI), emotion contagion,
group dynamics and social distancing, physiology (fatigue, age), and **roles and needs** — the layer
that decides an agent is a commuter, a tourist or a dog-walker before it decides where to step.

Two more that matter for a *city*, not a crowd:

- **Continuum crowds** (Treuille, Cooper & Popović 2006) — global potential field, unified planning
  and avoidance. Still the right model for dense directed flow, e.g. a station exit at rush hour.
- **Menge** (Curtis, Best & Manocha 2016) — not a model, an **architecture**: it decomposes crowd
  simulation into goal selection → plan computation → plan adaptation, with pluggable
  implementations of each. This decomposition is the one to copy (§10.3), independent of which
  locomotion model we run.

### 3c. The recent edge — watch, don't adopt

- **Learned Motion Matching** (Holden et al., SIGGRAPH 2020) and **GPU-based Motion Matching for
  Crowds in Unreal** (SIGGRAPH Asia 2020 poster) — the current answer to "animation quality without
  a clip-per-behaviour explosion". Relevant to foot-sliding and clip repetition (§8), not to
  routing.
- **Gen-C: Populating Virtual Worlds with Generative Crowds** (2025, ACM CGIT) — LLM-bootstrapped
  synthetic crowd *scenarios*, a time-expanded graph of actions and interactions learned by a dual
  VGAE. Its framing is the useful part: it argues the field over-solved the low level (collision
  avoidance, path following, flocking) and under-solved **high-level behaviour sustained over
  time** — which is precisely the difference between "the street has people on it" and "the city is
  alive".
- Neither is a v1 dependency. Both belong in the ledger as directions.

---

## 4. The data models — what a lane graph actually is

Four independent standards, converging on the same shape. This is the strongest available evidence
about what our schema must be able to say.

### 4a. SUMO (Eclipse) — the most complete open reference

- **Network:** edges → lanes; lanes carry `allow` / `disallow` **vClass permission sets**; junctions
  own **internal lanes** on which vehicles drive inside the intersection, and **internal junctions**
  that split them so a left-turner can wait mid-junction for oncoming traffic.
- **Junction types:** `priority`, `traffic_light`, `right_before_left`, `zipper`, `allway_stop`,
  and more. Right-of-way is *computed*: normally from allowed speed and lane count, overridable per
  edge with a `priority` attribute. **Every traffic-light junction still has a priority junction
  underneath it** — the signal plan and the yielding rules are separate layers, which is why
  simultaneous conflicting green streams (`g` vs `G`) work at all.
- **Named mechanisms worth stealing:** `keepClear` / no-block heuristic (don't enter a junction you
  would be stuck in), `visibilityDistance`, `--junctions.limit-turn-speed` (default factor 5.5,
  slows vehicles by turn radius), `stopOffset` per vehicle class, `endOffset`,
  `jmIgnoreKeepClearTime` (driver impatience as a parameter).
- **Vehicle vocabulary:** 33 `vClass` values — `passenger` (default), `bus`, `coach`, `truck`,
  `trailer`, `delivery`, `taxi`, `hov`, `emergency`, `authority`, `army`, `vip`, `motorcycle`,
  `moped`, `bicycle`, `scooter`, `wheelchair`, `pedestrian`, `tram`, `subway`, `rail*`, `ship`,
  `cable_car`, `aircraft`, `drone`, `custom1/2`, `ignoring`. Types carry `length` (5.0 m default),
  `width` (1.8), `height` (1.5), `mass` (1500 kg), `accel` (2.6 m/s²), `decel` (4.5), `tau` (1.0 s
  desired headway), `sigma` (0.5 driver imperfection), `guiShape`, `personCapacity` (4).

That last block is a ready-made **"start realistic"** default table in the sense of `citygen.md`
§2.0, and the class list doubles as the spawn-permission vocabulary (§10.4).

### 4b. ASAM OpenDRIVE — the interchange format

Road reference line + lane sections; lanes defined as offsets from the reference line; explicit
predecessor/successor linkage; signals and objects placed along the reference line. Four junction
kinds: **common** (paths cross), **direct** (change road, no crossing), **virtual** (main road
uninterrupted), **crossing**. Connecting roads spell out which incoming lane reaches which outgoing
lane — *"if lanes are not linked, there is no traversable path between these lanes."* If we ever
want CARLA, SUMO or a driving-sim to consume our city, this is the export target.

### 4c. Lanelet2 — the rules-first model

Three layers: **physical** (points, linestrings), **relational** (lanelets = atomic road pieces
within which rules and topology do not change; areas), **topological**. Rules live in **regulatory
elements** (speed limits, priority, signals) that lanelets *refer to*, and rules are expressed per
**participant** (vehicle, bicycle, pedestrian). Two ideas to take: rules as first-class referenced
objects rather than per-edge scalars, and "a lanelet ends where a rule changes".

### 4d. Unreal ZoneGraph / MassTraffic — the real-time cousin

Lanes as point-by-point corridors carrying **static and dynamic tags** that behaviours query;
`MassEntity` for data-oriented agent storage; **StateTree** driving crowd behaviour (traffic does
*not* run on StateTree); Mass Spawners with pluggable spawn-data generators; runtime density sliders
for crowd / traffic / parked cars. And — the part that matters most to us — **the lane graph and the
spawn point clouds are generated in Houdini and imported**: *"distribution along a ZoneGraph provided
through procedural data from Houdini is used to generate spawn points for the Crowd and Traffic
Systems."* We hold that Houdini project locally. See §6.

---

## 5. The tool landscape

### 5a. VFX crowd systems

| Tool | Shape of it | Notes |
|---|---|---|
| **Massive** | agent brains built from **fuzzy logic** nodes with simulated vision/hearing; the LOTR original | as of May 2026 there is **Massive 101, free for non-commercial** — full sim toolset, unlimited agents, watermarked renders, Arnold + built-in renderer only, USD/geometry export disabled. Cheapest way to study a mature agent-brain design |
| **Golaem** | Maya plug-in; behaviour graph + **Layout** post-sim editing; acquired by **Autodesk, Aug 2024** | has an explicit **Traffic Behaviour** and Traffic Locator: cars placed on lanes automatically, wander or seek a target. Also birds/fish flocking. The closest commercial thing to what Hannes described |
| **Miarmy** | Maya, fuzzy-logic driven, Express edition free | Basefount |
| **Atoms Crowd** | standalone core with Maya / **Houdini** / Katana / Unreal bridges | Toolchefs; the "crowd engine as a library" model |
| **Houdini crowds** | agents + states/triggers/transitions + POP steering + SOP motion paths | see §7 |

**Golaem 9's Layout tool is the reference implementation of R5.** Its layer list is a design spec in
itself: `CreateEntity` (author a character at layout time), `Duplicate`, `SnapTo`, `PlayMotion`,
`GroundAdapt` (snap feet to terrain), a full IK rig layer for re-animating one character, plus
retime/offset/clip-edit and prop/clothing randomisation — all **non-destructive**, all applicable
after the sim, all disable-able. Explicitly pitched at *"choreographing street scenes, where large
numbers of ambient characters are performing separate actions"*.

### 5b. The archviz family — "draw an area, get people"

- **3ds Max Populate** (native since 2014). Draw **flows** (walking paths, tolerating shallow
  inclines), **idle areas** (standing/talking), and **seats**. This is the tool Hannes remembers.
  Still documented through 3ds Max 2024; widely described as dated; I could not verify a formal
  deprecation and am not asserting one.
- **AXYZ anima** — the archviz default (AXYZ acquired by Chaos, 2023 — snippet-level). Draw paths in
  the host viewport, place obstacles and avoid-areas, define walking surfaces; characters handle
  stairs, escalators, moving walkways and slopes. anima 5 added **4D Digital Humans** (animated
  scanned meshes, short loops) and **Neural Crowds** (motion model trained on mocap), plus vertex
  velocities for correct motion blur and a crowd **LOD** system.
- **Reallusion iClone Crowd Sim** (8.4+, free upgrade) — spawn into a volume, along a walkway, on an
  object or straight onto a NavMesh; spawn zones and foot-traffic guidance; aimed at archviz as much
  as film.
- Common shape across all three: **areas and paths as the authoring primitives, loopable clips as
  the content, zero simulation exposed to the user.** That is R6, and it is not hard — it is a
  scatter with a permission mask and a clip assignment.

### 5c. Games — where traffic is actually shipped

- **Unreal City Sample / MassTraffic** — §4d. The most complete public example of a Houdini-authored
  city driving a lane-based traffic + crowd system.
- **Cities: Skylines** — the cautionary tale, §8.
- **GTA-lineage path nodes** — decades-old, still the pattern: hand-tagged node graph with lane
  counts, densities and flags. Not a public spec; mentioned for lineage only.

### 5d. Transport & pedestrian engineering — where the *rules* are rigorous

**Vehicles:** SUMO (open, best-documented), PTV Vissim (Wiedemann car-following), Aimsun, MATSim
(agent-based demand modelling — the "why is this trip happening" layer), MITSIM.
**Pedestrians:** Oasys **MassMotion** (BIM-integrated, "EveryStep" agents), Bentley/JLL **Legion**
(claims 500k unique pedestrians), Thunderhead **Pathfinder** (evacuation), PTV **Viswalk** (social
force, couples to Vissim traffic). Their common interest is throughput and evacuation, not looks —
but the calibrated numbers (walking speeds, densities, level-of-service bands) are exactly the
real-world defaults the house rule wants.

**Signal timing, for defaults that are not invented** (⚠️ sourced but not cross-checked against
MUTCD by me): ITE yellow change interval `t + v/(2a ± 2Gg)` with perception-reaction `t = 1 s`,
deceleration `a = 10 ft/s²` (≈3.05 m/s²); typical yellow 3–6 s; all-red clearance from approach
speed and intersection width (≈2.5 s for 25 mph across 70 ft), bounded 2–6 s; pedestrian clearance
designed at 2.5–3.5 ft/s (0.76–1.07 m/s); NACTO advises against cycle lengths under 60 s in normal
use. Enough to make a signal that looks right without a traffic engineer.

### 5e. The asset side — R3

The generator does not need to *make* the content, but it does need to *specify* it.

- **People:** AXYZ Metropoly (ready-posed + rigged + 4D), Renderpeople, Reallusion ActorCore,
  Mixamo-style clip libraries. anima ships only **two base actors** — the library is the business
  model, and that is the trap to design around: our contract must be "bring your own agent
  definitions", never "our three characters".
- **Vehicles:** any rigged model plus a wheel/steer convention. Houdini's `rbdcarrig` already defines
  one (wheel groups auto-split into front/back/left/right, optional steering-wheel group, 3-axle
  truck layouts).
- **Animals:** dogs, cats, birds, squirrels are *not* a separate system. Birds and fish are flocking
  (Reynolds/`popsteer` align+cohesion+separate; Golaem and Massive both ship it). Ground animals are
  ordinary agents with a different clip set and different placement rules. The real cost is the
  **clip library and the placement affordances** (perch, ledge, wire, tree, bin, bench), not the
  solver.

---

## 6. What the AAA reference actually does — dissected locally

We hold Epic's City Sample Houdini toolset at `resources/citygen/unrealCitygen/`. I expanded
`otls/City_Processors.hda` with `hotl -X` and read it. This is **direct evidence, not a blog post**,
and it is the most useful single artefact in this sweep.

**The toolset is a set of "processor" SOPs over one city layout** — `road_processor`,
`sidewalk_processor`, `lot_processor`, `decal_processor`, `ground_processor`,
`street_furniture_processor`, and **`traffic_data_processor`**. Utilities include
`parking_spaces_from_lots`, `car_alignment` and `road_block_maker`.

**`city::traffic_data_processor::1.0`** — seven inputs (`main_city_layout`, `road lanes output`,
`sidewalk lanes output`, `road traffic output`, `freeway connections`, `freeway out street
connections`, `main city modified by freeway`) and **exactly one parameter: `lane_width`, default 4**.
Everything else is derived. That restraint is itself a finding.

Attributes it reads and writes (extracted from its VEX snippets):

| Attribute | Role |
|---|---|
| `number_of_lane`, `lane_number`, `side_number`, `doubled`, `divider`, `divider_width` | cross-section decomposition into individual lanes |
| `lane_width`, `parking_lane`, `parking_lane_width`, `sidewalk_width`, `width` | metrics |
| `traffic_density`, `pedestrian_density` (+ `_i` variants) | **per-element spawn density — R4, shipped** |
| `sequence`, `sequence_number`, `sequence_array` | lane runs = ZoneGraph lane sequences |
| `cross_to_sequence`, `connection_to_sequence`, `connection_to_string`, `connection_type` | **lane-to-lane connectivity — the thing §1 says everyone else omits** |
| `inter_id`, `inter_id_string`, `inter_id_parent`, `inter_center`, `intersection_user_type` | junction identity, and whether the junction node serves `vehicle` or pedestrians |
| `road_id`, `road_blocked`, `exit_right`, `freeway_connection` | routing flags |

Two mechanisms worth copying outright:

1. **Lane selection is a subtraction, not a construction.** `lane_chooser` is a four-branch VEX
   wrangle that *removes* candidate lane curves by index — outermost each side, and the centre pair
   — leaving the drivable set. Lanes are generated from the cross-section and then filtered.
2. **Crossings are a pairing problem.** `crossing_sequence` sets `cross_to_sequence = -1`, then
   resolves it in two passes: first by matching `road_id` across the street, and if that fails by
   finding the point whose rounded normal is the exact opposite (`rint(N) == rint(-N)`). That is how
   two sidewalk lanes on opposite kerbs become one pedestrian crossing.

**What this tells us:** the AAA answer to R1 is a *processor stage that reads the finished street
cross-section and emits a lane graph with connectivity, junction identity and per-element density*.
It is not a solver. It is schema plumbing — which is the good news, because schema plumbing is what
citygen is already made of.

---

## 7. Houdini and APEX — what ships, and the verdict Hannes asked for

Verified in the live session (Houdini **22.0.398**), not from memory.

### 7a. What exists

**Agents & animation (SOP):** `agent`, `agentclip`, `agentcliptransitiongraph`, `agentlayer`,
`agentprep`, `agentproxy`, `agentterrainadaptation`, `agentlookat`, `agentcollisionlayer`,
`agentconstraintnetwork`, `agentvellumunpack` (Vellum cloth on agents), `crowdsource`,
`crowdassignlayers`, plus KineFX bridges (`kinefx::agentfromrig`, `agentposefromrig`).

**Simulation (DOP):** `crowdsolver`, `crowdobject`, `crowdstate`, `crowdtrigger`,
`crowdtriggerlogic`, `crowdtransition`, `crowdfuzzylogic`, `agentterrainadaptation`,
`agentcliplayer`, and **14 steering behaviours**: `popsteerseek`, `popsteerpath`, `popsteeravoid`,
`popsteerobstacle`, `popsteerseparate`, `popsteeralign`, `popsteercohesion`, `popsteerwander`,
`popsteerturnconstraint`, `popsteercustom`, `popsteersolver`. (Align + cohesion + separate = Boids,
natively.)

**`popsteerpath` is the R1 hook.** Its docs (read from the local help server) describe a **Match by
Attribute** mode: agents follow the curve whose `Curve Attribute` equals their own `Agent Attribute`
— *"useful for precisely controlling which curve each agent follows"*, falling back to nearest curve.
So "assign this agent to lane 3 of edge E17" is a native, supported binding. It also warns that
agents bounce at the end of a curve unless a trigger hands them to a new state — i.e. **lane-to-lane
handover must be authored**, which is §4a's internal-lane problem restated.

**SOP motion paths (Houdini 20+):** 17 `crowdmotionpath*` nodes — `crowdmotionpath` (bake agent
motion to curves), `...evaluate`, `...follow` (deform paths onto guide curves), `...edit` (pin and
deform individual paths), `...layer` (layer a clip, e.g. upper-body over a walk), `...retime`,
`...transition`, `...avoid`, `...trigger`, `...arcinglayer`. **Crowds as editable geometry, with no
DOP network at all.** This is Houdini's Golaem-Layout answer, and it lands exactly on citygen's own
rule that *"the splines are the product"* (streets §4c).

**Vehicles:** `rbdcarrig` (since H20) — wheel groups auto-split front/back/left/right, optional
steering-wheel group, drive modes FWD/RWD/4×4, wheel layouts including 3-wheelers and **3-axle
trucks**, per-wheel or shared configuration, centre-of-mass placement, acceleration profile,
**Ackermann steering angle as a percentage**, camber/caster, tire friction, wheel wobble; plus the
documented **RBD Car Follow Path** workflow that spins and steers wheels along a path and
compensates suspension against the ground.

**Render:** the **Houdini Crowd Procedural** for Solaris/Karma defers agent expansion to render time.
⚠️ Known constraint from the SideFX forums (snippet-level): USD ignores instancing beneath
`SkelRoot`, so naïve USD crowds go unique-per-agent in RAM — people use distance LOD and pre-frame
culling. For an offline film target at city scale this is a real risk and must be prototyped.

**APEX (SOP):** `apex::invokegraph`, `apex::script`, `apex::graph`, `apex::mergegraph`,
`apex::configuregraph`, `apex::packcharacter`, plus the whole **APEX Scene** family —
`sceneaddcharacter`, `sceneaddprop`, `sceneaddconstraint`, `sceneaddcamera`, `sceneanimate`,
`sceneimportanimation`, `scenecopyanimation`, `sceneinvoke`. Houdini 21 declared APEX/KineFX
production-ready and added Motion Mixer (non-linear clip mixing), an Animation Catalog of reusable
poses/clips, and procedural graph fusion.

### 7b. Verdict, per layer

| Layer | Use Houdini crowds? | Use APEX? | Reasoning |
|---|---|---|---|
| Lane graph + rules | **no** | **no** | plain SOPs/VEX on the street graph, as City Sample does. Neither system has a concept of a lane |
| Route choice (which way does this car go) | no | no | graph search in the planner (`plan.py` is already pure-Python and `hou`-free) |
| Vehicle motion along lanes | **not the crowd solver** | no | a POP/VEX pass with IDM-style following is lighter and fully controllable; this is what the published Houdini traffic setups do |
| Vehicle articulation (wheels, steer, suspension) | — | **yes, for hero cars** | `rbdcarrig` for hero/foreground; a kinematic wheel-spin + Ackermann VEX solve for the mass. ⚠️ untested at scale |
| Pedestrian locomotion & avoidance | **yes** | no | this is what the crowd solver and `popsteer*` are for |
| Animals, birds | **yes** | no | `popsteeralign/cohesion/separate` is Boids; ground animals are agents with other clips |
| Animation clips, retarget, variation | yes (agent clips) | **yes** | APEX/KineFX is the rig+clip engine; Motion Mixer for non-linear blending |
| **Layout / artist override / "add one more car here"** | **yes — the motion-path SOPs** | **yes** | bake to motion paths, edit as geometry, re-animate individuals via APEX Scene. This is where APEX genuinely earns its place |

So `citygen.md` §4b's *"when the splines start driving traffic and crowds, APEX is the obvious
vehicle"* resolves to: **APEX is the obvious vehicle for the characters and the edits, not for the
traffic.** Recommend updating that line rather than leaving it ambiguous.

### 7c. Risks in Houdini's crowd system — recorded honestly

From Matt Estela's cgwiki (a practitioner's public notes, ★★ — one strong source, uncorroborated):
agent avoidance *"doesn't like to work for me. I disabled it"*; the steer solver needing to be
inserted manually before forces take effect; clip setup being one-at-a-time and *"not hard, just
boring"*; locomotion cycling warping agents back to the origin without channel surgery; foot-plant
detection needing a *"fudge factor"*. He also states the conclusion that matches everything else in
this document — *"Finding that agents can do things without simulation was an eye opener [...] if you
can get away with that, do it"* — and, to his credit, that he has never run a full crowd setup in
production. Documented limits from SideFX: one terrain object; one-way interaction only (agents
cannot push FLIP/RBD back).

### 7d. How does the crowd system know where agents may walk? **It does not.**

Asked directly (Hannes, 2026-08-18: *"sidewalk and zebra stripes are ok, the street should be
avoided"*). Checked against the Houdini 22 documentation, not memory. **There is no navmesh and no
walkability concept anywhere in the crowd system.** Agents are particles carrying a skeleton; the
solver knows only four things about the world, and none of them is semantic:

| Mechanism | What it actually does | Use as a walkability fence? |
|---|---|---|
| **Terrain** (Crowd Solver → Terrain tab) | height and foot placement. *"Only one geometry object can be used as terrain [...] If agents move off the terrain, they will snap to the ZX plane."* | **No.** It answers *how high*, not *where allowed*. Leaving it does not stop an agent, it teleports them to Y=0 |
| **`popsteerobstacle`** | casts a cone of rays (H/V FOV, front search distance), steers toward the least-obstructed ray, brakes along environment normals; near/far avoidance forces, collision padding, optional terrain projection | **Soft only.** Keeping people off the road means invisible kerb walls with gaps at crossings. It is a force, not a constraint — a crowded sidewalk will push someone through it |
| **`popsteerpath`** (Match by Attribute) | binds agents to a named curve with a path variance | **Yes, and this is the strong one** for a street network |
| **`popsteercustom`** / VEX | arbitrary steer force from anything you can sample — a walkable mask volume, an SDF, an attribute lookup | **Yes.** This is what production actually does for "stay on the pavement" |
| **`crowdtrigger`** | Object Bounds (incoming / outgoing / **continuous**), Object Distance (position or point cloud), Object Raycast, attribute, speed, time, custom VEXpression | not a fence, but it is how *"at the kerb → wait → cross"* gets built |

Routing tools exist, but **outside** the crowd system: `findshortestpath` (shortest paths along the
edges of a surface, with per-point and per-edge costs — feed it the walkable mesh) and
`labs::pathfinding_global` 1.0 (paths between points of interest across a terrain, driven by named
**cost** and **avoidance** attributes).

**The consequence for us is architectural, and it is the same conclusion as §10.3: walkability is a
routing decision, not a steering decision.** Pedestrians should get their **own lane graph** —
sidewalk centrelines plus crossing links — and be routed on it, with steering responsible only for
the last metre (other agents, bins, lamp posts). This is precisely what City Sample ships
(`SIDEWALK_LANES` + `cross_to_sequence`, §6) and what Unreal's crowd does (agents on ZoneGraph
pedestrian lanes, not free-roaming with collision). If instead you rely on obstacle avoidance to keep
people out of the road, the fence is soft by construction and will fail exactly when the shot is
busiest.

**We are unusually well placed to supply what Houdini lacks**, and mostly from data streets already
computes: `walkable` on the sidewalk strips of the swept cross-section becomes both the walkable
surface and the mask; the road strips become the avoid region; the crossing pairs come from the same
sidewalk-endpoint pairing City Sample uses. §10.1's schema additions are what make it derivable.

⚠️ **And a zebra crossing is not statically walkable — it is walkable *when the signal says so*.**
That is a `crowdtrigger` reading the junction's signal phase (§10.2), which is the point where the
pedestrian layer and the traffic-rule layer stop being independent. Worth designing for from the
start, since it is the one coupling that cannot be bolted on later.

---

## 8. What people like and dislike

Themes with corroboration ratings, in the style of `citygen_buildings.md` §5.

### Theme 1 — Artists want to overrule the simulation, per agent, after it has run — ★★★
Golaem's entire Layout product, its marketing line *"Crowd Simulation is over, step in Character
Layout!"*, and its `CreateEntity` layer (build a whole shot in layout, no sim). Houdini 20 shipping
SOP crowds "for simpler shots that don't require complex crowd simulations". A thesis on crowd
software states the problem plainly: *"the control of a crowd's behaviour is [...] time consuming and
frustrating, as manually editing the behaviour of individuals is often the only control approach
available."* **This is R5 and it is the single most-validated requirement in this document.**

### Theme 2 — Repetition is what kills it: the clone army — ★★★
anima ships two base actors; the reviewer's complaint is variety. Studios build bespoke anti-cloning
tooling (Hybride: no existing software gave the flexibility, so they wrote their own combination
tool). Foot sliding is universally hated and has its own literature. In archviz specifically:
*"in closer shots the realism decreases"*, and *"if you want to fill an area with standing people,
you will have to rotate and move most of them by hand, otherwise it looks unnatural."*
**Implication: variation is a first-class feature, not a post-process — and standing/idle crowds are
harder than walking ones.** §10.5a proposes the answer: an authored area plus a point of interest,
with placement and orientation derived from sightlines rather than hand-rotated.

### Theme 3 — Bad routing destroys believability faster than bad steering — ★★★
SimCity 2013's GlassBox: agents had no persistent home or job, they took *the nearest available*
one, and walked the path of least resistance — players reverse-engineered it within days and the
game's reputation never recovered. Cities:Skylines: vehicles pick a path at spawn and never
re-evaluate, *"as if the driver knows the road network 100% and willingly drives into huge traffic
jams"*, and refuse to change lanes once in a multi-lane section; the most popular fix mod adds
**Dynamic Lane Selection** — re-evaluating lane choice at every suitable node. **Nobody notices your
car-following model. Everybody notices a car that drives into a wall of traffic or turns from the
wrong lane.**

### Theme 4 — The tools are heavy, and the heaviness lands on the artist — ★★
Houdini crowds *"covers the most ground of any Houdini system"* (agents, CHOPs, rigging, POPs,
heightfields, DOPs) — §7c. anima freezes the 3ds Max timeline and eats RAM; the workaround is
displaying actors as boxes. Crowd work brings *"file size explosions, render times that stretch
timelines, and licensing complexity"*. Historic anima complaints: actors mis-stepping on stairs and
escalators, poor actor-to-actor collision (later improved).

### Theme 5 — People love it when the setup is *drawing*, not configuring — ★★
The praise for anima is about the path tools: *"no need to adjust the spline and lay it down exactly
on the surface; it's all done automatically"*, 200 actors in *"just a few seconds"*, and a learning
curve measured in hours. Populate's whole design is three verbs: flow, idle area, seat. iClone spawns
into a volume, a walkway, an object, or a NavMesh. **R6 is popular because it is shallow.**

### Theme 6 — Vehicles are treated as second-class by every crowd tool — ★★
Golaem has a Traffic Behaviour; Massive can do vehicles; Houdini has no traffic system at all, and
the public Houdini traffic setups are hand-built POP/VEX systems rather than crowd sims. Nobody
ships the thing Hannes is describing as one integrated product. **That is the gap worth occupying.**

---

## 9. What is genuinely unsolved

1. **High-level behaviour over time** — Gen-C's framing: the field solved local navigation and
   under-solved *why the agent is there*. A city that is alive needs roles, schedules and errands,
   not better avoidance.
2. **Validating realism** — both surveys say it independently: no standardised metrics. Chao's
   dictionary-based fidelity score is the state of the art and needs ground-truth trajectory data
   we will never have for a fictional city. **For us this is liberating: the acceptance test is a
   viewport reading, not a statistic.**
3. **Vehicle–pedestrian interaction** — the survey is blunt that current simulators pre-script it;
   CARLA's pedestrians check for cars once and then commit. Crossings, jaywalking, a car yielding to
   a pram: all still hand-authored in practice.
4. **Dense standing crowds** — everyone solves walking; idling groups that look composed rather than
   scattered are still manual (Theme 2).
5. **Rendering crowds at film scale from USD** — the instancing-under-SkelRoot problem (§7a) is a
   live pipeline issue, not a solved one.

---

## 10. What this implies for citygen

My assessment, not a decision taken. Ordered by when it would have to happen.

### 10.0 Bottom line — **our own system yes, a navmesh mostly no**

Hannes, 2026-08-18: *"bottom line we have to generate our own navmesh and system for this right?"*
Two answers, because the two halves of the question have different ones.

**Our own system: yes, unavoidably.** No tool will hand us a pedestrian or vehicle network for a city
we invented. Houdini has no walkability concept at all (§7d); the engines that do (ZoneGraph) are
*downstream consumers* of exactly the data we would be generating — Epic authors theirs in Houdini
too (§4d). Nobody is going to do this half for us.

**A navmesh: no, and reaching for one would be the wrong instinct.** A navmesh exists to *recover*
walkability from geometry nobody annotated — voxelise the world, find the flat-enough surfaces,
region-grow, contour, triangulate, then A* + funnel across it. That whole apparatus is an inference
step, and **we do not need to infer anything: we generate the city, so we know analytically where the
pavement is.** Paying for a recovery algorithm on top of data we authored is pure waste, and it
throws away the two properties that matter most here — determinism and editability. A navmesh polygon
is not a thing an artist can meaningfully grab; a curve is.

**What replaces it: the same lane graph, tagged by participant.** Pedestrian lanes are just lanes
whose permitted class is `pedestrian` — that is literally how SUMO (`vClass`), Lanelet2
(*participants*) and City Sample (`ROAD_LANES` + `SIDEWALK_LANES` out of **one** processor) all model
it. So this is **not a second system**: it is one lane-graph derivation stage with a permission
vocabulary, which is also §10.1 and §10.4. Routing is then an ordinary graph search — `findshortestpath`
natively, or `plan.py`, which is already pure-Python and `hou`-free.

**Where a walkable *region* is still the right primitive:** open space — plazas, parks, station
forecourts, and the drawn areas of the idle-crowd tool (§10.5a). Corridor lanes are the wrong model
where movement is genuinely 2D. But note that this wants a walkable **mask or surface**, not a
navmesh with pathfinding on it: scatter, avoid, steer locally, and connect to the lane graph through
entry/exit points. Unreal splits it the same way — lanes for corridors, free movement for open areas.

So the thing to build, in five parts, none of which is an engine:

| Part | What it is | New work? |
|---|---|---|
| 1. Pedestrian lane derivation | sidewalk centrelines, crossing links, kerb ramps — from the cross-section we already sweep | **yes**, and it is the bulk of it |
| 2. Permission + density vocabulary | `agent_class`, `allow`/`disallow`, `*_density` (§10.4) | small, schema only |
| 3. Routing | graph search over 1 | `findshortestpath` or `plan.py` — mostly free |
| 4. Binding to Houdini | `popsteerpath` Match by Attribute, `crowdtrigger` at kerbs and signals, terrain projection | glue |
| 5. Region tool for open space | walkable mask + scatter + POI (§10.5a) | small, and it needs no simulation |

⚠️ **Honest scope check.** Part 1 is a real subsystem and it is *not* small — but it is the same
derivation the vehicles need, so it is paid for once. Everything else on this list is plumbing over
data streets already computes. **Real navmesh generation (Recast-style) only becomes necessary if we
ever want free-roaming agents over arbitrary imported geometry we did not author.** That is a v3
question at the earliest, and possibly never.

### 10.1 The street schema must be able to carry lanes — and this is a *streets* change
The lane graph is derived from the cross-section, so it belongs downstream of §S6 — but three things
have to exist upstream or the derivation is impossible:

| Needed | Where | Status today |
|---|---|---|
| lane count + direction per edge (`number_of_lane`, `oneway`, per-side counts) | prim on edge | ✗ — only `laneWidth` |
| per-lane role in the cross-section template (`travel`, `parking`, `bike`, `bus`, `median`) | already half-there as `elem_type` on swept strips | ◐ — exists on geometry, not on the graph |
| lane-to-lane connectivity through each node | node/junction data | ✗ |
| way-giving statement per node | **`principal_start`/`principal_end` + `junction_type`** | ✔ **already decided** |
| per-element densities (`traffic_density`, `pedestrian_density`) | prim on edge | ✗ — trivial to add, and City Sample proves it is enough |

The cheap, correct move while streets is still open: **make `elem_type`/`u_cross` survive onto the
graph, add lane counts, and add the two density floats.** Nothing else. That keeps the door open at
almost zero cost, which is what streets §10 already promises ("the graph is being designed to make it
possible later, that is all").

### 10.2 Traffic rules are derived defaults with a `warn`-mode override
Follow SUMO's separation: **priority rules underneath, signal plan on top.** Right-of-way default =
principal pair wins, then class, then width — the same ordering SUMO computes from speed/lane count,
and we already have a ratified rule for it. Signals only where `junction_type` warrants, with the ITE
numbers from §5d as defaults. Every rule is an attribute with a computed default and an artist
override, and every violation is a persisted warning, per `citygen.md` §2.1–2.2. **No new mechanism
is required** — that is the point.

### 10.3 Three layers, kept separable (Menge's decomposition)
`goal selection` → `plan computation` (route on the lane graph) → `plan adaptation` (local steering)
→ *plus* `animation`, which Menge does not model but we must. Artists edit at the top (where does
this agent want to go) and the bottom (what does this one look like and do), and the middle stays
replaceable — start with the cheapest thing that reads correctly, upgrade to IDM/MOBIL only if a
shot demands it.

### 10.4 Spawn rules = permissions + densities + affordances
- **`agent_class` vocabulary** modelled on SUMO's `vClass`, pruned to what we render, extensible.
- **Per-strip `allow`/`disallow`**, riding on the existing `drivable`/`walkable`/`parkable` flags —
  which streets already ships. Extend, don't invent.
- **Density attributes** per edge and per region, artist-paintable.
- **Affordance points** (Kallmann & Thalmann 1998 smart objects): a bench carries "sit", a wire
  carries "perch", a bin carries "sniff". This is the only sane way to get dogs, cats, birds and
  squirrels without a bespoke subsystem each — and it reuses the scatter/instancing machinery the
  city already needs for street furniture.

### 10.5 The authoring surface is the deliverable, and it is three tools
1. **Draw an area → fill it** (R6): the archviz tool, with permission masks and clip assignment. The
   shallowest thing here and the most loved (Theme 5).
2. **Draw a path → agents follow it**: `popsteerpath` Match-by-Attribute already binds an agent to a
   named curve; our lane curves *are* named curves.
3. **Edit the result per agent** (R5): bake to crowd motion paths, edit as geometry, commit through
   the same override layer (`citygen.md` Contract 2) that streets already uses — records keyed by
   `elem_id`, merged upstream, generated-vs-authored kept distinguishable. **The override layer was
   designed for exactly this and has never been stress-tested by a consumer that produces thousands
   of edits. That is the real architectural risk to probe.**

### 10.5a The idle-crowd primitive — area + point of interest (Hannes, 2026-08-18)

> if we just define an area where people are standing and not walking away we could also define a
> point of interest. For example a concert or a window in front of a store, that way the system
> knows what the target to look at is

**Correct, and it is an established primitive rather than a workaround.** It is the direct answer to
Theme 2's worst finding (*"you will have to rotate and move most of them by hand"*), and it has prior
art on three sides:

- **Papers.** *Practical simulation of virtual crowds using points of interest* (Computers,
  Environment and Urban Systems, 2016) builds crowds from POIs as the primary authoring unit.
  **Grillon & Thalmann 2009**, *Simulating gaze attention behaviors for crowds*, is the gaze half:
  extract interest points, **score** each candidate per agent (distance, speed, …), turn the scores
  into gaze constraints, solve with a dedicated gaze IK. Follow-ups add personality-driven and
  group-based gaze, and deliberately **distracted** agents.
- **Engineering tools.** Pedestrian simulators already model an attractor as `capacity` +
  `dwell time` + `entry rate`, with dwell classes (skim / swim / dive). Those are the parameters,
  named by people who calibrate against real venues.
- **Houdini, natively.** `agentlookat` 3.0 (since 19.5) is Grillon & Thalmann implemented: target
  types **Position / Object / Points / Agents**, a per-target `agentlookat_targetscore` float that
  scales candidate scoring, horizontal/vertical **FOV visibility**, **Match by Attribute** (string or
  integer, patterns allowed) so an agent only considers the targets addressed to it, and skeleton
  adjustment from Lower Back → Head plus optional eye joints, configured in `agentprep`. **We do not
  have to build the gaze layer.**

**Where the naive version fails, and the fix.** Rotating every agent to face the POI gives a firing
squad — a solid block of people all facing one way, which is not what a real audience looks like.
Real spectators arrange themselves so they can *see*: the crowd around a busker opens into an arc
with a hole in the middle, and people behind stand in the gaps. So **orientation and placement
should both derive from the sightline, not from the vector to the POI**:

1. scatter candidates in the drawn area, subject to the usual permission mask (§10.4),
2. **visibility-test each candidate to the POI** — occluded by city geometry *and* by already-placed
   agents (a cheap "who is in front of me" test, height-aware),
3. reject or nudge candidates that cannot see; the survivors are the audience shape,
4. orient along the sightline with per-agent noise, and let `agentlookat` do the head and eyes.

This is **isovist / Visibility Graph Analysis** applied backwards — the published space-syntax method
computes exactly this visible region and is already used to distribute pedestrians in urban space.
⚠️ The arc-formation claim above is my own reasoning from observation; I found lane formation and
bottleneck self-organisation in the pedestrian-dynamics literature but **no source for spectator arc
formation**. Treat it as a hypothesis to check in the viewport, not a cited fact.

**A POI should carry more than a look-at target.** What makes it earn its keep is that one authored
point supplies five things at once:

| Field | Drives |
|---|---|
| position + height offset | the gaze target (eye height, not floor) |
| area / radius / capacity | how many agents, and where they may stand |
| `dwell` distribution | **turnover** — agents arrive, watch, leave. The difference between a still and a shot |
| `gaze_weight` (0–1) | what fraction actually look, versus phone / neighbour / passing car. **The anti-clone lever** |
| `clip_set` + `agent_class` filter | watching, filming, clapping, browsing, queuing — and *who* is admitted |

**And it generalises far past concerts and shop windows**, which is the strongest argument for making
it a first-class element rather than a one-off tool. The same primitive covers: a bus stop (gaze down
the street, the bus arriving is the dwell terminator), **pedestrians waiting at a red light** (the POI
is the crossing — and City Sample's `cross_to_sequence` data already tells us where every crossing
is, §6), an ATM queue, a food truck, a street performer, people watching a building site through a
hoarding — and the animals: pigeons around crumbs, a dog at a lamppost, squirrels at a bin. Same
element, different clip set and different `agent_class`.

**Architecturally it lands in the right place.** In Menge's decomposition (§10.3) this is *goal
selection* — the layer Gen-C says the field under-solved (§3c). And an area+POI crowd needs **no
simulation at all**: scatter → visibility → clip → gaze IK. That matches both the archviz tools'
model (§5b) and cgwiki's advice (§7c), and it means idle crowds can ship long before any solver does.

⚠️ **What it does not solve:** the *approach*. People walking up to the POI, joining the back, and
peeling off is a routing problem and needs the sim. Ship the static audience first; treat arrival and
departure as a later upgrade. Also, gaze IK across thousands of agents is not free — budget it, and
expect to run it only within camera range.

**Recorded as a design proposal, not a decision.** It is the strongest candidate answer to R6 and
should be prototype #4 in §10.6 if the first three go well.

### 10.5b Birds — flocking is native, **landing is the interesting half** (Hannes, 2026-08-18)

> in cities there are always birds so it would be nice if bird simulations would be part, not only
> the flocking but also rules where they can land and sit

**Not a silly detail — the best life-per-cost element in the whole document, and the cheapest.** It
also exercises two parts of the design nothing else does: genuine 3D space, and affordances as the
*only* navigation data. There is no lane graph for a pigeon.

**Local material (indexed, not copied):** `F:\tutorials\Houdini\CMIVFX_Houdini_FlockSystem.zip`
(4 videos, no `.hip`) and `F:\tutorials\Houdini\Mix Training Nature of Vex\mixtrn - NOVEX _ 07
Flocking.mp4`. Both are technique, not city context.

**The flocking half is solved, and the empirically correct rules are published.**

- Native in Houdini: `popsteeralign` + `popsteercohesion` + `popsteerseparate` **is** Reynolds' 1987
  boids, plus `popsteerwander` and `popsteeravoid`. Nothing to build.
- ⚠️ **But Houdini's neighbourhood is metric, and real starlings are topological.** Verified:
  `popsteercohesion` offers *"Search radius (in meters)"* with an optional field-of-view cone — no
  neighbour-count mode. **Ballerini et al. 2008 (PNAS, the STARFLAG field study)** measured that each
  bird interacts with a **fixed ~6–7 nearest neighbours regardless of distance**, and that this is
  what holds a flock together when density changes under a predator strike. Getting murmuration
  behaviour therefore means a `popsteercustom`/VEX force using a k-nearest lookup, not the stock
  radius forces. Small, but it is the difference between a swarm and a murmuration.
- **Hildenbrandt, Carere & Hemelrijk 2010** (*Self-organised aerial displays of thousands of
  starlings*, Behavioral Ecology — the StarDisplay model) adds the other four ingredients: constant
  **cruise speed**, **banking** — individuals *turn away* rather than slow down, and the difference
  is visible when banking is switched off — **horizontal attraction to the roost**, and a
  **preferred altitude**. Those four forces plus topological neighbours are the whole recipe, and
  every one of them is a couple of lines.
- Hemelrijk's follow-up finding is a free shot detail: **agitation waves through a flock come from
  changes in bird *orientation*, not from density changes.**

**The landing half is where the design work is — and it is the §10.5a machinery again.**

Perches are **affordances derived from geometry we already generate**: wires between poles
(catenaries), ledges and cornices (up-facing edges with clearance above), railings, window sills,
lamp posts, traffic lights, awnings, statues, roof ridges, tree branches. Each emits a `perch` curve
or point carrying:

| Field | Drives |
|---|---|
| `capacity` + `spacing` | how many birds fit, and how far apart |
| `agent_class` filter | pigeon / sparrow / gull / crow — a gull does not perch on a wire |
| approach vector + clearance | can it be landed on, and from where |
| `no_perch` mask | **bird spikes and netting are real street furniture** — a real-world-grounded artist control |

**Spacing is a documented behaviour, not a random scatter.** Perching birds sit near-evenly spaced by
*individual distance*: swallows famously precise, starlings much tighter than pigeons; the two
proposed mechanisms are conflict avoidance and "wing space" — the room needed to land and take off
with wings spread. There is even a modelling paper on it (*Modeling birds on wires*, J. Theor. Biol.
2016). So: per-species spacing with jitter, never uniform, never uniform-random.

**The state machine is ordinary crowd work.** fly → approach → flare → land → perch/idle → hop /
preen → takeoff. Agents in Houdini are skeletons with clips; nothing requires them to be human. And
the best beat in the whole system is nearly free: **takeoff on disturbance** — a `crowdtrigger` Object
Distance (point cloud) against pedestrians or a passing car, flipping the whole flock into a scatter
state. That single interaction is what makes a square read as alive.

Ground birds are not a special case: pigeons pecking in a plaza are agents on a walkable **region**
(§10.0, part 5) with crumbs as POIs (§10.5a).

**Two things birds break, deliberately worth noting:**

1. **Do not run them through the crowd solver's terrain machinery.** One terrain object, and agents
   that leave it snap to the ZX plane (§7d) — meaningless for flight. Birds live in POP space; the
   ground plane matters only at the perch.
2. **They have no lane graph at all** — free space, perch targets, roost. Which is a useful proof
   that the region/affordance half of this design stands on its own, separable from the lane half.

**LOD ladder**, same shape as the traffic hybrid (§3a): distant flocks = instanced particles with a
looping flap cycle, no agents; mid-ground = agents with clips; hero birds = hand-animated.

**Verdict: this could ship before traffic.** Flocking is native, perches are attributes on geometry
the city already produces, and none of it needs the lane graph that everything else in §10 waits on.
Of everything surveyed here it is the shortest path to a city that looks inhabited.

---

### 10.6 The three prototypes that would settle the design
Small, in this order, none of them before streets lands:

1. **Lane graph from one junction.** Take a single four-arm node, emit lane centrelines with
   connectivity and a way-giving statement, visualise it. Proves or kills §10.1.
2. **Fifty cars on it.** POP/VEX, IDM-ish following, stop at the give-way line, turn onto the correct
   outgoing lane. Proves the motion layer is cheap. Wheels: kinematic Ackermann, no Bullet.
3. **Bake and break it.** Simulate a hundred pedestrians, bake to crowd motion paths, move three of
   them by hand, re-cook, confirm the edits survive. Proves the override layer at scale — the
   riskiest claim in this document.

---

## 11. Evidence quality

**Verified directly by me (highest confidence):**
- City Sample `traffic_data_processor` inputs, its single `lane_width` parameter, its attribute set,
  and the `lane_chooser` / `crossing_sequence` / `traffic_data_type` VEX — expanded from the local
  HDA with `hotl -X` and read.
- Houdini 22.0.398 node inventories (crowd, agent, popsteer, apex) — enumerated in the live session.
- `rbdcarrig` and `popsteerpath` parameter documentation — read from the running build's help server.
- Chao et al. 2020 survey §§2.2–2.4, 4, 6 and Khan & Deng 2024 §§4.1, 5 — text extracted from the
  PDFs and read.

**Fetched and read as web pages (high confidence, single source each):**
SUMO Intersections; SUMO vehicle types/vClass; UE City Sample docs; cgwiki Houdini crowds; CGPress
anima review.

**Search-snippet level — treat as leads, not facts:** Golaem Layout layer list and Traffic Behaviour
(the official docs now redirect to Autodesk and did not resolve); Massive 101 free-edition details;
AXYZ acquired by Chaos 2023; Golaem acquired by Autodesk 2024; anima 5 feature list; iClone crowd
features; 3ds Max Populate's current support status; Cities:Skylines and SimCity criticism (forum and
press summaries, not primary sources); the ITE/NACTO signal-timing numbers in §5d.

**Not investigated, deliberately:** rail/transit simulation; boats and aircraft; traffic *demand*
modelling (MATSim-style origin-destination), which is the layer that would answer "why is this trip
happening" and is a project of its own; crowd rendering economics beyond the USD instancing note;
real-time/game export.

---

## 12. Design spec v0 — for later pickup. 2026-08-19

**This is a spec, not a build.** Precedent: `citygen_buildings.md` §12. Everything below is
designed against the research above; where a decision is still the artist's, it is marked as a
question in §12.13. **No stage may be built before its prototype gate (§12.11) passes**, and no
gate except P4 runs before streets V1 closes.

### 12.0 How to pick this up

Read, in order:

1. `citygen.md` §2 (the cascade, advisory validation, the authoring model) and its Contracts —
   especially Contract 2, the override layer. Every mechanism below assumes them.
2. `citygen_streets.md` §6 (the attribute schema — this subsystem's *input*) and §11 (the
   planner/builder split, `junction_type`, the `principal_start`/`principal_end` booleans — the
   way-giving input).
3. This file: §1 (findings), §4 (what a lane graph is), §6 (the City Sample dissection — the
   worked reference), §7 (Houdini/APEX inventory and verdict, §7d walkability), §10 (implications).
4. `resources/citygen/README.md` §1 — the City Sample HDAs are held locally; when in doubt about a
   derivation, re-expand `otls/City_Processors.hda` with `hotl -X` and read the VEX.
5. Call `houdini_get_skill("houdini-dev-loop")` before touching anything. Rule 0 applies to every
   milestone: nothing is "done" until an independent agent audits it on the current build — before
   that the honest words are *implemented, unverified*. And build **visual repros** for the artist:
   viewport readings have overturned the numbers in this project before.

Working rules, inherited from streets §11.1 and restated for this subsystem:

- **Authored beats computed.** Every attribute below is fill-if-empty.
- **Decide on the plan, steer once.** Routing decisions happen on the abstract lane graph, never on
  meshed geometry a later stage reshapes.
- **An agent is never silently deleted.** Despawning to hide congestion is the most-hated cheat in
  the genre (§8 Theme 3). Failure modes warn and degrade — stop, idle, reroute — never vanish.
- **No ID derives from cook order.** Streets measured what that costs (§S11.3); lane and agent IDs
  are constructed from stable parents.

### 12.1 Scope and non-goals — v1

**In:** passenger / delivery / bus vehicles with kinematic wheels; parked cars; pedestrians,
including signal-obeying crossings; idle crowds (area + POI, §10.5a); dogs, cats, squirrels as
ground agents; birds (flocking + perching, §10.5b); junction rules — priority and fixed-time
signals; the three authoring tools (§12.9); persisted warnings; the acceptance scene (§12.12).

**Out, recorded so they don't quietly creep in:** rail / metro / sky-lane traffic (`network_type`
reserved) · demand/OD modelling — *why* a trip happens is a project of its own (§11) · vehicle–
pedestrian negotiation beyond signals (jaywalking, yielding to a pram) — the hook is reserved in
the foe records, Q4 · hero vehicle dynamics (`rbdcarrig` stays a per-shot tool, not pipeline) ·
navmesh generation over unauthored geometry (§10.0) · real-time/game export · actuated/adaptive
signals · personality and emotion models (§3b's upper layers) · weather- or time-of-day-driven
behaviour shifts.

### 12.2 Inherited constraints — binding, with sources

| Constraint | Source |
|---|---|
| Metric, metres; offline film render target | `citygen.md` §1 |
| Every value is a cascade default; no constants anywhere | §2.1 |
| Validation is advisory — `warn`, persisted, never a wall | §2.2 |
| The artist can intervene at any stage | §2.3 |
| Start realistic, end artistic — the SUMO/ITE numbers below are *defaults*, never limits | §2.0 |
| `elem_id` + `source_node` survive to the final output | streets §6 |
| Generated vs authored stay distinguishable; edits live in the override layer, keyed by ID | `citygen.md` Contract 2 |
| Way-giving inputs: `junction_type` vocab + per-edge principal booleans | streets §11.3 |

### 12.3 Architecture — six stages

`L0 lanes → L1 rules → L2 population → L3 motion → L4 animation → L5 authoring`, every stage
forwarding the data stream, every stage readable and overridable on its own. Requirements map:
R1 = L0 · R2 = L1 · R3 + R4 = L2 · R5 = L4 + L5 · R6 = L5.

**Code homes** (the `plan.py` precedent, streets §11.2): pure logic in
`polyfactory/scripts/python/polyfactory/citygen/` (`lanes.py`, `rules.py`, `routes.py`), `hou`-free,
unit-tested at test_citygen speed; thin Python-SOP adapters; VEX/POP builders. ⚠️ **A module lands
with its adapter and consumer in the same milestone or not at all** — `plan.py`'s near-death lesson
applies verbatim.

### 12.4 L0 — the lane graph

#### 12.4a L0-lite — the only pre-streets work; belongs to streets §6 when it lands

| attr | class | type | meaning |
|---|---|---|---|
| `lanes_fwd` / `lanes_bwd` | prim (edge) | int | travel lane counts, fill-if-empty from `street_template` |
| `oneway` | prim (edge) | int | 0/1 |
| `traffic_density` / `pedestrian_density` | prim (edge) | float 0–1 | spawn weights — City Sample proves the pair is sufficient (§6) |

Plus the guarantee that `elem_type` / `elem_index` / `u_cross` survive from the cross-section
template into graph-adjacent data (today they exist only on swept strips). Nothing else. Record the
change in `citygen_streets.md` §6, not here.

#### 12.4b L0 proper — the processor stage (after streets)

Shape: City Sample's (§6) — read the finished street graph + cross-section templates + junction
plans, emit the lane network as **its own cached geometry stream of curves** (default answer to Q1).

**Per lane prim:**

| attr | type | meaning |
|---|---|---|
| `lane_id` | string | **stable**: `{edge_id}:{side}{lane_index}`, or `{junction_id}:i{n}` for internals — never cook order |
| `edge_id` / `junction_id` | string | owner |
| `lane_role` | string | travel · parking · bike · bus · sidewalk · crossing · internal |
| `direction` | int | +1 / −1 along the parent edge parameterisation |
| `width` | float | from the template |
| `allow` / `disallow` | string array | `agent_class` sets, SUMO semantics — disallow wins |
| `speed_default` | float | m/s, from the per-`street_class` table |
| `successors` / `predecessors` | string array | lane_ids — **the attribute the whole field says generators omit (§1)** |
| `sequence_id` | string | maximal run with unchanged rules — Lanelet2's "a lanelet ends where a rule changes" |
| `layer` / `network_type` | int / string | carried from the parent edge |

**Per junction** (node or junction detail record): `junction_id` · `junction_type` · `signalized`
int · internal lanes (own prims, `lane_role = internal`) · **`foes`** — pairs of internal lanes
whose paths cross · `keep_clear` int · `turn_speed_factor` float (default 5.5 — SUMO's
`limit-turn-speed`).

**Crossings:** `crossing_id`, the two sidewalk-lane ends it joins — paired City Sample's way:
`road_id` match first, opposed rounded normals as fallback (§6) — plus linked signal phase and
length. **Parking:** one `parking_id` point per stall on parking-role lanes; stall length default
= design vehicle length 5.0 m + gap; local reference: `parking_spaces_from_lots` +
`car_alignment` in `City_Utilities.hda`.

**Derivation defaults:** lanes by offsetting the centreline per template, then **subtracting**
non-travel candidates (City Sample's `lane_chooser` pattern — subtraction, not construction);
junction connectivity from the junction plan's turn model — every incoming travel lane links to ≥1
outgoing lane per legal turn. A lane with no successor is `sim_warn_dead_lane`, never an error.

### 12.5 L1 — rules

SUMO's separation (§4a), kept exactly: **priority always exists; signals sit on top of it.**

**Priority, derived per junction:** rank arms by principal pair → `street_class` order (highway >
arterial > collector > local > alley) → width quantised to 1 mm → lexicographic `edge_id` — the
same determinism streets ratified (§S11.3). Emit per-foe-pair yield decisions.
`junction_type == merge` ⇒ zipper semantics.

**Signal record, where `signalized`:** `cycle_len` (default 90 s; NACTO floor of 60 s respected as
a warning, not a wall) · `phases[]`, each a list of green lane-connections + `green_len` ·
`yellow` from the ITE formula (v = `speed_default`, t = 1 s, a = 3.05 m/s²), clamped 3–6 s ·
`all_red` from junction width and speed, clamped 2–6 s · pedestrian phases from crossing length ÷
`ped_clearance_speed` (default 1.07 m/s; documented band 0.76–1.07). Simultaneous conflicting
greens ⇒ `sim_warn_invalid_signal`, **still generated** — the artist may want it broken.

**Time:** v1 ships `sim_time` = frame ÷ fps + `time_offset` parameter. The fuller city-clock
question stays open as Q2.

### 12.6 L2 — population

**`AGENT_CLASS_VOCAB`, pinned in `checks.py`** (the `LOT_REJECT_VOCAB` precedent): v1 =
`pedestrian · passenger · delivery · bus · bicycle · dog · cat · bird · squirrel`, plus `custom*`.
Extensible, never implicit.

**Agent definition contract — bring-your-own, nothing hardcoded (§5e's trap):** name ·
`agent_class` · Houdini agent definition (rig + clips, via `kinefx::agentfromrig`) · dims (l/w/h) ·
speed distribution (mean + σ) · clip map {locomotion, idle[], action[]} · variation hooks (palette,
props). Vehicle defaults from the SUMO vType table (§4a: length 5.0, width 1.8, accel 2.6, decel
4.5, tau 1.0, sigma 0.5) — defaults, never limits.

**Spawn sources**, all cascade-respecting: per-lane/edge densities (12.4a) · per-region
multipliers · POI records · affordance points · parking fill ratio.

**POI record** (point; §10.5a, artist-proposed 2026-08-18, ratify at pickup): `poi_id` · position +
`target_height` · radius or area ref · `capacity` · `dwell` (lognormal mean + σ) · `gaze_weight`
0–1 · `clip_set` · `agent_class` filter.

**Affordance points** (§10.4, §10.5b): `afford_type` (seat · perch · queue · sniff · …) ·
`capacity` · `spacing` (per-species default + jitter — never uniform, never uniform-random) ·
approach vector + clearance · `no_perch`/`no_sit` mask (bird spikes are real street furniture).
Emitted fill-if-empty by the furniture/building generators (Q7).

### 12.7 L3 — motion

Common: agents carry `agent_id` (**stable**: `{spawn_id}:{i}`), `agent_class`, and — when
lane-bound — `lane_id` + `s` (Frenet position along the lane, not raw world position). The solver
behind each class is replaceable (Menge's decomposition, §10.3); the acceptance instrument is a
viewport repro, not a statistic (§9.2).

**a) Vehicles — POP/VEX, not the crowd solver (§7b).** IDM car-following with per-agent params
sampled from the vType defaults; lane changes v1 = **imperative only** (lane ends / turn required —
the Shen–Jin split; MOBIL politeness deferred); junction entry gated by the L1 foe/yield records +
`keep_clear`; turn speed via `turn_speed_factor`. Wheels kinematic: spin from s-velocity, steer
from path curvature (Ackermann as a percentage, `rbdcarrig`'s own convention); `rbdcarrig` proper
reserved for hero shots.

**b) Pedestrians — crowd solver.** Route on sidewalk + crossing lanes (`findshortestpath` over the
connectivity arrays, or `routes.py`); bind with `popsteerpath` **Match by Attribute** (agent attr =
current `lane_id`); lane→lane handover via `crowdtrigger` bounds at lane ends — the documented
end-of-curve bounce (§7a) is designed around, not discovered. Kerb behaviour: trigger on the linked
crossing's phase. Steering (separate/avoid/obstacle) is **last-metre only** (§7d); free movement
allowed inside region masks (§12.9a).

**c) Birds — POP, no crowd-solver terrain (§7d's snap-to-ZX hazard).** Topological k-nearest
custom steer force (k default 7 — Ballerini) + cruise speed + banking + roost attraction + altitude
preference (StarDisplay, §10.5b); perch assignment samples perch affordances by capacity + spacing;
states fly → approach → land → perch → takeoff; disturbance = `crowdtrigger` point-cloud distance
against pedestrians/vehicles. LOD ladder: instanced flap-cycle particles far, agents mid, hand
animation for heroes.

**d) Ground animals.** Pedestrian machinery with different clip sets, region-biased, POI-driven.

### 12.8 L4 — animation binding

Agent definitions from KineFX/APEX; idle diversity is a **shipping requirement, not polish**
(Theme 2): minimum three idle clips per class before any crowd ships, retime jitter ±10 % default,
mirrored variants. `agentterrainadaptation` and gaze (`agentlookat`, fed by POI `gaze_weight`) run
within a camera-distance budget only (Q5). Vehicles write wheel transforms as agent channels. APEX
Scene is the per-agent re-animation surface (§7b) — invoked from L5c, not from the solvers.

### 12.9 L5 — the authoring surface (the deliverable — §8 Theme 1)

Three tools. All write override-layer records, all non-destructive, all honouring the Subversion
rule (step in at any stage, §2.3):

**a) Area fill (R6).** Draw a closed curve → region record: permission mask (walkable strips ∪
open-space mask, minus `disallow`) + density + optional POI link + clip set → scatter + orient —
with the sightline pass when a POI is present (§10.5a) → agents, **no simulation**. This is the
Populate/anima verb (§5b).

**b) Path.** Draw a curve → agents bound to it via Match-by-Attribute; count / rate / class
parameters.

**c) Agent edit (R5).** Bake a selection to `crowdmotionpath`; edit, retime, re-clip, APEX
re-pose; **commit** writes records keyed by `agent_id` into the upstream override node —
Contract 2's write-not-wire, feedback across cooks, never within one. Regeneration preserves
authored agents byte-for-byte where untouched — gate P3's exact assertion.

### 12.10 Warnings — persisted attrs, viewport-visualisable, all default `warn`

`sim_warn_dead_lane` · `sim_warn_unreachable` (no route — the agent idles at spawn, never deleted)
· `sim_warn_invalid_signal` · `sim_warn_overcapacity` (POI / perch / parking demand > capacity) ·
`sim_warn_gridlock` (junction blocked longer than a threshold) · `sim_warn_offlane` (steering
forced an agent off its lane). Modes per §2.2.

### 12.11 Prototype gates P1–P5 — in order; a stage is not built until its gate passes

| gate | proves | kill criterion / fallback |
|---|---|---|
| **P1** → L0 | one 4-arm junction → lane curves + `successors` + `foes`, visual repro | lane_ids unstable across re-cooks ⇒ **stop, fix identity first** |
| **P2** → L3a | 50 cars: follow, yield at the give-way line, exit on the correct lane, kinematic wheels; per-frame cost measured | cost explodes ⇒ v1 falls back to open-loop path playback |
| **P3** → L5c | 100 pedestrians baked to motion paths; 3 hand-edited; re-cook; edits survive | the override layer cannot carry thousands of records ⇒ redesign the Contract 2 consumer **before any L5 work**. The riskiest gate in the subsystem (§10.5) |
| **P4** → birds | flock with topological k-NN + 20 perches on wires and ledges; land, space, scatter on disturbance | none — independent of streets, may run first as the morale gate |
| **P5** → render | 10 k agents through the Solaris crowd procedural to Karma; memory measured | USD SkelRoot instancing blows RAM (§7a) ⇒ LOD/culling becomes a v1 stage, not a nicety |

### 12.12 v1 acceptance — "the living block"

One demo scene on a streets-V1 district: vehicles obeying signals and priority · parked cars ·
pedestrians keeping to sidewalks, waiting on red, crossing on green · one plaza filled by the area
tool with a POI audience (the arc hypothesis of §10.5a checked by eye) · pigeons perching and
scattering when a pedestrian passes · three hand-edited agents surviving full regeneration · every
threshold reachable through the cascade · every warning visualisable. **Signed off by the artist
from the viewport** — that is the instrument.

### 12.13 Open questions carried into the build

1. **Q1 — lane stream representation:** separate cached curve stream (default) vs attributes woven
   into the street graph. Decide at P1.
2. **Q2 — the city clock:** one time authority for signal phases, dwell, future schedules. v1
   ships frame-derived `sim_time`; the real answer shapes L1/L2.
3. **Q3 — signal record shape:** dict attribute vs table prims. With Q2.
4. **Q4 — vehicle–pedestrian negotiation** beyond signals (jaywalking, yielding). v2; the foe
   records already include crossings, so the hook exists.
5. **Q5 — the per-frame animation budget:** gaze, terrain adaptation, foot-locking vs camera
   distance. Needs P5's numbers.
6. **Q6 — hybrid/continuum LOD** for city-scale shots (Sewall, §3a). Not v1.
7. **Q7 — who emits affordances:** the furniture/building generators natively, or a
   geometry-scanning post-pass. Default: both, fill-if-empty.
8. **Q8 — OpenDRIVE export** (§4b). Only when an external consumer exists.
9. **Q9 — ratify the §7b verdict table.** It is my assessment; the artist's ruling so far is "use
   Houdini crowds and APEX if it makes sense". Confirm per layer at each gate, not once globally.

---

## Sources

**Surveys and papers**
- Chao et al., *A Survey on Visual Traffic Simulation* (CGF 2020) — <http://graphics.cs.uh.edu/wp-content/papers/2019/2019-CGF-TrafficSimSurvey.pdf> · <https://onlinelibrary.wiley.com/doi/abs/10.1111/cgf.13803>
- Khan & Deng, *Agent-based Crowd Simulation: An In-depth Survey* (TVC 2024) — <https://graphics.cs.uh.edu/wp-content/papers/2024/2024-TVC-CrowdSimSurvey.pdf>
- Curtis, Best & Manocha, *Menge: A Modular Framework for Simulating Crowd Movement* — <http://gamma.cs.unc.edu/Menge/files/mengeCDMain.pdf> · <https://github.com/MengeCrowdSim/Menge>
- Reynolds, *Boids* — <https://www.red3d.com/cwr/boids/>
- Ballerini et al., *Interaction ruling animal collective behavior depends on topological rather than metric distance* (PNAS 2008) — <https://arxiv.org/pdf/0709.1916>
- Hildenbrandt, Carere & Hemelrijk, *Self-organized aerial displays of thousands of starlings: a model* (Behavioral Ecology 2010) — <https://www.rug.nl/research/gelifes/tres/_pdf/hi_eabeheco10.pdf>
- Hemelrijk et al., *What underlies waves of agitation in starling flocks* — <https://link.springer.com/article/10.1007/s00265-015-1891-3>
- *Modeling birds on wires* (J. Theor. Biol. 2016) — <https://www.sciencedirect.com/science/article/abs/pii/S0022519316304064>
- Individual distance in perching birds, plain-language summary — <https://www.wm.edu/news/stories/2020/social-distancing-in-birds.php>
- Kallmann & Thalmann, *Modeling Objects for Interaction Tasks* (1998) — <http://graphics.ucmerced.edu/publications/1998_EGCAS_Kallmann.pdf>
- Grillon & Thalmann, *Simulating gaze attention behaviors for crowds* (CAVW 2009) — <https://onlinelibrary.wiley.com/doi/abs/10.1002/cav.293>
- Ağıl & Güdükbay, *A group-based approach for gaze behavior of virtual crowds incorporating personalities* (CAVW 2018) — <https://onlinelibrary.wiley.com/doi/abs/10.1002/cav.1806>
- *Modelling distracted agents in crowd simulations* (The Visual Computer 2020) — <https://link.springer.com/article/10.1007/s00371-020-01969-4>
- *Social Crowd Simulation: Improving Realism with Social Rules and Gaze Behavior* (MIG 2024) — <https://dl.acm.org/doi/10.1145/3677388.3696337>
- *Practical simulation of virtual crowds using points of interest* (CEUS 2016) — <https://www.sciencedirect.com/science/article/abs/pii/S0198971516300126>
- Turner et al., *From Isovists to Visibility Graphs* — <https://www.researchgate.net/publication/23541236_From_Isovists_to_Visibility_Graphs_A_Methodology_for_the_Analysis_of_Architectural_Space>
- *Pedestrian simulation and distribution in urban space based on visibility analysis and agent simulation* — <https://www.researchgate.net/publication/253666107_Pedestrian_simulation_and_distribution_in_urban_space_based_on_visibility_analysis_and_agent_simulation>
- Wilkie, Sewall & Lin, Road Network Library — <http://gamma.cs.unc.edu/RoadLib/>
- *Gen-C: Populating Virtual Worlds with Generative Crowds* (2025) — <https://arxiv.org/abs/2504.01924>
- Holden et al., *Learned Motion Matching* — <https://history.siggraph.org/learning/learned-motion-matching-by-holden-kanoun-perepichka-and-popa/>
- *GPU-based Motion Matching for Crowds in the Unreal Engine* — <https://dl.acm.org/doi/10.1145/3415264.3425474>
- *Algorithms for Microscopic Crowd Simulation* (Inria) — <https://inria.hal.science/hal-03197198/document>
- *A review of software for crowd simulation* — <https://urban-analytics.github.io/dust/docs/ped_sim_review.pdf>

**Standards and simulators**
- SUMO Intersections — <https://sumo.dlr.de/docs/Simulation/Intersections.html>
- SUMO Traffic Lights — <https://sumo.dlr.de/docs/Simulation/Traffic_Lights.html>
- SUMO vehicles, types and routes (vClass) — <https://sumo.dlr.de/docs/Definition_of_Vehicles,_Vehicle_Types,_and_Routes.html>
- ASAM OpenDRIVE, junctions — <https://publications.pages.asam.net/standards/ASAM_OpenDRIVE/ASAM_OpenDRIVE_Specification/latest/specification/12_junctions/12_01_introduction.html>
- Lanelet2 — <https://github.com/fzi-forschungszentrum-informatik/Lanelet2>

**Engines and DCC tools**
- UE5 City Sample — <https://dev.epicgames.com/documentation/en-us/unreal-engine/city-sample-project-unreal-engine-demonstration> · quick start: <https://dev.epicgames.com/documentation/en-us/unreal-engine/city-sample-quick-start-for-generating-a-city-and-freeway-in-unreal-engine-5>
- MassTraffic extracted as a standalone plugin — <https://github.com/Myxcil/MassTraffic-Test>
- Houdini Agent Look At — <https://www.sidefx.com/docs/houdini/nodes/sop/agentlookat.html>
- Houdini POP Steer Cohesion (metric search radius) — <https://www.sidefx.com/docs/houdini/nodes/dop/popsteercohesion.html>
- Houdini crowd obstacles — <https://www.sidefx.com/docs/houdini/crowds/obstacles.html> · terrain: <https://www.sidefx.com/docs/houdini/crowds/terrain.html>
- Houdini POP Steer Obstacle — <https://www.sidefx.com/docs/houdini/nodes/dop/popsteerobstacle.html> · Crowd Trigger: <https://www.sidefx.com/docs/houdini/nodes/dop/crowdtrigger.html>
- Houdini Find Shortest Path — <https://www.sidefx.com/docs/houdini/nodes/sop/findshortestpath.html> · Labs Pathfinding Global: <https://www.sidefx.com/docs/houdini/nodes/sop/labs--pathfinding_global-1.0.html>
- Houdini crowds — <https://www.sidefx.com/docs/houdini/crowds/index.html> · SOP motion paths: <https://www.sidefx.com/docs/houdini/crowds/sopcrowds.html> · H20 talk: <https://www.sidefx.com/learn/talks/h20-crowds-sop-based-workflow/>
- Houdini RBD Car Rig — <https://www.sidefx.com/docs/houdini/nodes/sop/rbdcarrig.html> · car follow path: <https://www.sidefx.com/docs/houdini/destruction/carfollowpath.html>
- Houdini Crowd Procedural (Solaris) — <https://www.sidefx.com/docs/houdini/solaris/houdini_crowd_procedural.html>
- Golaem 9 / Layout — <https://www.cgchannel.com/2024/06/golaem-releases-crowd-simulation-tool-golaem-9/> · <https://www.linkedin.com/pulse/crowd-simulation-over-step-character-layout-alexandre-pillon>
- Massive 101 free edition — <https://www.cgchannel.com/2026/05/massive-crowd-simulation-software-gets-free-edition/>
- Atoms Crowd — <https://atoms.toolchefs.com/>
- AXYZ anima — <https://secure.axyz-design.com/en/anima> · anima 5: <https://www.cgchannel.com/2022/10/axyz-design-ships-anima-5-0/> · review: <https://cgpress.org/archives/cgreviews/anima_review>
- 3ds Max Populate — <https://help.autodesk.com/view/3DSMAX/2024/ENU/?guid=GUID-139D1FD6-3815-4A58-9698-BEE2E49A5DAB>
- Reallusion iClone Crowd Sim — <https://www.reallusion.com/iclone/crowd-sim/>

**Artist and player feedback**
- cgwiki, Houdini crowds — <https://tokeru.com/cgwiki/HoudiniCrowd.html>
- Cities:Skylines TM:PE, lane selection — <https://github.com/VictorPhilipp/Cities-Skylines-Traffic-Manager-President-Edition/issues/192>
- SimCity 2013 pathfinding — <https://news.ycombinator.com/item?id=5369105> · <https://community.simtropolis.com/forums/topic/54642-videos-show-path-finding-inherently-broken/>
- Hybride on crowd variation — <https://beforesandafters.com/2020/09/10/hybride-adventures-in-crowds/>

**Traffic engineering defaults**
- NACTO, signal cycle lengths — <https://nacto.org/publication/urban-street-design-guide/intersection-design-elements/traffic-signals/signal-cycle-lengths/>
- NCHRP 3-95, yellow and red intervals — <https://onlinepubs.trb.org/onlinepubs/nchrp/docs/NCHRP03-95_FR.pdf>
