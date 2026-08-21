# Artist-Facing UI — the parameter surface study

**Status:** research complete, no design taken. No HDA UI has been built to these rules yet.
**Question asked (Hannes, 2026-08-21):** designing an interface for people who do not understand
the technical side of the tool but need it to create the art. Under "start realistic, end artistic"
we should *expose as many variables as possible* so the artist can do what they need — and at the
same time *expose as little as possible* so the tool doesn't overwhelm. Which complex tools do
artists say get this right (named example: RailClone), which get it wrong, and what do both teach?

**This file owns:** the evidence — tool case studies (good and bad), corroborated artist feedback,
and the verified interaction-design literature on the expose-everything/expose-little tension.
It applies to **every polyfactory tool**, same breadth as the §2.0 house rule in
[`citygen.md`](citygen.md), not just citygen.
**This file does NOT own** any subsystem's actual UI design. It also does not restate what the
repo already holds: [`citygen_buildings.md`](citygen_buildings.md) §5 Theme 5 ("tools die of bad
interfaces"), [`citygen_simulation.md`](citygen_simulation.md) §8 Themes 1/5 (per-agent overrule,
"setup as drawing"), [`terrain_presets.md`](terrain_presets.md) (the Gaea preset corpus), and
[`citygen.md`](citygen.md) §2.0–2.3 (the house rules this study tests against evidence).
**Relation to the `houdini-tool-design` MCP skill:** this study is the evidence layer under that
skill's assertions ("art direction is the cardinal rule", helper vs end-user tools). §6.7 below
proposes what the skill should absorb once these rules are adopted.

Research fanned out 2026-08-21 across four agents (RailClone deep-dive; praised tools; notorious
tools; formal literature). Corroboration: ★★★ multiple independent sources · ★★ some · ★ single
source or inference. Sources inline; vendor-curated quotes flagged.

---

## 0. The one-paragraph answer

The stated tension — expose everything vs expose little — is **resolved, not balanced**, by every
tool that artists praise: **expose everything to the *author* tier, expose almost nothing — but
the right things — to the *artist* tier, and make the boundary a climbable ramp, not a cliff.**
RailClone is the cleanest proof: its artist-facing parameter panel is **empty by default** — every
visible knob is a deliberate, per-property promotion by the style author, carrying limits, type
and help text — while ~500 browsable presets are the actual front door and the node graph is the
back office. Three findings sharpen it: **(a)** "overwhelming" is mostly *latency*, not parameter
count — artists happily tune 50 knobs that respond instantly and abandon 10 behind a 30-second
cook (★★★); **(b)** defaults are the product — under 5 % of users ever change *any* setting, and
users read defaults as the author's recommendation (★★★, measured); **(c)** the classic failure is
not too many parameters but **code as the interface** (CityEngine's CGA wall) and the **two-tier
cliff** vendors build to fix it (wizard *or* code, nothing between). Our §2.1 cascade and Contract
2 already satisfy the hardest rules on the list; what we do not yet have is the preset corpus, the
naming discipline, the interactive proxy loop, and the one-button path.

---

## 1. RailClone, dissected — why the named good example works

iToo's docs, forum, CGPress/Creative Bloq reviews, r/3dsmax and Polycount threads, read directly.

### 1a. Three layers with an escalating skill gradient — and the artist layer is *authored*

1. **Modify panel** (consumer surface). "The starting point when using RailClone is always the
   Modify panel" ([interface docs](https://docs.itoosoft.com/railclone/getting-started-with-railclone/5-the-railclone-interface)).
   Its **Parameters rollout** shows *only* what the style author promoted: "in order for a
   parameter to appear here, there must be an equivalent Numeric node present in the style
   editor." Empty by default. The consumer contract is: pick preset → pick spline → turn the
   knobs the author left you. ★★★
2. **Library Browser** — thumbnail grid, ~500 presets, user-extensible; the real front door. ★★★
3. **Style Editor** — the node graph, opened only via a button. Deliberately small vocabulary:
   "there are only 21 nodes, and a parametric object can be as simple as just 2 nodes"
   ([iToo tutorial](https://www.itoosoft.com/tutorials/adapting-railclones-built-in-presets)). ★★

### 1b. The exposure mechanism — the load-bearing part

From [Exporting Parameters](https://docs.itoosoft.com/railclone/style-editor/exporting-parameters)
and [Parameters and Attributes](https://docs.itoosoft.com/railclone/next-steps-with-railclone/3-parameters-and-attributes):

- Promotion is **opt-in, per-property, author-driven**: right-click → Export Parameters → tick
  properties → each becomes an input socket, wired to a **Constant** (author-only) or a
  **Numeric** node — which the docs say exists "to create a simplified interface so that the user
  can interact with the style without needing to open or understand the Style Editor." The design
  intent is stated in exactly those words. ★★★
- The Numeric node carries the **artist-proofing metadata**: type (including boolean → checkbox
  and selector → named drop-down), **min/max limits**, a **description** surfaced behind a Help
  button, animatability. An exposed knob without limits and help text is half-exposed. ★★★
- **Expressions/attributes** let one knob drive many internal values coherently ("small tile =
  large tile / 2") — how a complex model stays honest under few knobs. ★★★
- **Macros** ([docs](https://docs.itoosoft.com/railclone/style-editor/macros)): sub-graphs
  collapsed into single named nodes with ordered, categorized parameters, shared as files — a
  *middle tier* where power users package complexity for intermediate users. ★★★

### 1c. The ramp, not the wall

iToo's own pedagogy: consume (preset + knobs) → adapt (**swap the geometry without touching the
logic** — the cheapest art-direction lever there is) → learn (toggle nodes off to deduce function;
"reverse engineering presets is a great way to understand," [official guide](https://docs.itoosoft.com/railclone/getting-started-with-railclone/7-how-to-edit-a-railclone-style))
→ author. Practitioners confirm this is how it is actually learned: "I would just recommend
looking through the presets and seeing how things have been constructed. This is almost entirely
how I learnt it" ([r/3dsmax](https://old.reddit.com/r/3dsmax/comments/7l8fnp/anyone_do_a_lot_of_railclone_pro/)). ★★★

### 1d. Where the money went — the strongest tell

iToo's 2025 endgame, **RailClone Systems**, is presets-with-curated-knobs *as the product*:
"Modify dimensions, spacing, orientation, and more … in the familiar Max modify panel — **all
without touching the graph editor (unless you want to)**"
([Systems page](https://www.itoosoft.com/railclone/railclone-systems)). You don't build that
product line unless most paying users live in the consumer tier. ★★★. And the sibling **Forest
Pack** — narrower problem, *no node editor at all*, fixed rollouts + library — is picked up "in a
great intuitive manner" while RC is "a much tougher nut to crack" (same thread) and is the bigger
seller. ★★★

### 1e. Verified negatives — recorded honestly

- The Style Editor curve is real, longitudinally: a scripting-literate professional bought Pro in
  2017 ("it feels complicated and still a little overwhelming"), and **six years later** posted he
  had drifted to Max's native Array modifier: "I never got any good with RailClone"
  ([2017](https://old.reddit.com/r/3dsmax/comments/7l8fnp/anyone_do_a_lot_of_railclone_pro/),
  [2023](https://old.reddit.com/r/3dsmax/comments/14kvwxe/first_time_using_the_array_modifier_that_ships/)). ★★★
- Documented complaints were almost all **graph-editor ergonomics** (drop-node-on-wire, always-on-
  top, auto-bridge), not capability — and iToo shipped the fixes across RC4–RC6 ([forum](https://forum.itoosoft.com/railclone-pro-(*)/style-editor-usability-improvements/)). ★★
- Hard problems are **refused gracefully** rather than half-shipped: no spline forks/intersections
  — "It's been requested a number of times" ([Polycount](https://polycount.com/discussion/137113/railclone-parametric-modelling-tool)). ★★
- ⚠️ The claim "most users never open the Style Editor" is a well-supported **inference** (design
  intent + product strategy + behavior), not a measured fact — no usage statistics exist. ★★

---

## 2. The good end — what each praised tool's mechanism actually is

| Tool | The mechanism that makes complexity usable | ★ |
|---|---|---|
| **SpeedTree** | Generator hierarchy named in the *artist's ontology* (Trunk → Branches → Leaves, not "L-system depth 2"); every parameter is a **value + variance + profile curve** triple; any procedural element converts to **Hand Drawn** in-viewport | ★★★ |
| **Marvelous Designer** | One deep domain metaphor (patterns, seams, pins) carried through the entire UI — it teaches tailoring whether you like it or not | ★★★ |
| **EmberGen** | Node-based like Houdini, yet called easy — because the sim responds per slider-drag. Real-time feedback converts parameters from "numbers you must understand" into "knobs you can hear" | ★★★ |
| **Substance Painter** | Photoshop layer stack + **smart materials**: one artist noun ("worn steel") bundling dozens of parameters, still fully openable underneath | ★★★ |
| **Townscaper** | Zero parameters; all complexity moved into the generator's judgment; every reachable state authored to look good | ★★★ |
| **Houdini's own wins** (heightfields, Vellum Brush, Labs) | Borrowed Photoshop metaphor (layers/masks), named high-level nodes (Erode, Slump), GPU interactivity, open wrappers | ★★★ mechanism / ★ sentiment |

Details worth keeping verbatim:

- **The Painter/Designer natural experiment** — same company, same domain, same engine; one ships
  layers, one ships nodes. Painter won mass adoption; Designer is "for TDs" and the standard
  advice everywhere is *learn Painter first*. The best-corroborated single finding of this study:
  **the front-end wearing the artist's existing mental model wins; the node one becomes the
  specialist tool.** ★★★ Note the ceiling is real too: power users formally requested a node
  option *in Painter*, and deep layer stacks crawl. ★★★
- **Stålberg's control split**, the cleanest statement found anywhere of our tension: "**I want
  the user to feel like they're in control of the large shapes. But then I get to play around
  with a lot of things on the small shapes**"
  ([Game Developer interview](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making)).
  Also: the generator "is actually allowed to fail silently" — the artist never sees an error —
  and "what's important is what happens when things change… when one material meets another
  material": **author the junctions/transitions; artists judge the tool there.** ★★★. The flip
  side is universally acknowledged: Townscaper is a toy — you cannot leave its aesthetic; every
  screenshot looks like Townscaper. The zero-parameter extreme fails "start realistic, end
  artistic" by construction.
- **EmberGen's design property**, from a (vendor-curated, named) testimonial: "It's hard to
  intentionally make things look bad." The iteration-speed claim itself is independently
  corroborated by comparison writeups ("lookdev in EmberGen, final high-res in Houdini"). ★★★
- **World Machine as the cautionary control**: node-based, respected, feature-rich — "very
  flexible and also node based but somehow still collects dust on my pc… too complicated for my
  taste" ([Polycount terrain-tools thread](https://polycount.com/discussion/228295/gaea-vs-world-machine-vs-world-creator-vs-instant-terra)).
  **Flexibility without approachability loses by default.** ★★
- **Complaints migrate to the boundaries.** When the core UI works, the gripes concentrate on
  export/pipeline (an entire third-party retopo-tool economy exists around Marvelous Designer),
  performance cliffs, stability, licensing — not the creation UI. Budget engineering there. ★★★

## 3. The bad end — failure case studies

- **Esri CityEngine — the grammar wall.** The interface to the core capability *is a programming
  language* (CGA). Reviews split users into castes: "Designers comfortable with scripting
  languages adapt quickly; those expecting visual-only tools face a steeper learning curve." Esri
  has spent 15+ years building ladders over its own wall — Facade Wizard (one-way, can't
  round-trip), Visual CGA, and by 2025 a "no-code modeling environment" plus **Street Designer**
  direct viewport lane editing — i.e. after 17 years they are re-adding *direct manipulation*.
  The fix pattern failed each time the same way: the no-code layer works only inside its library's
  vocabulary; wanting anything else drops you off the cliff back into CGA text. The
  entertainment-artist market it launched into largely walked away; GIS customers kept it alive.
  ★★★ (extends `citygen_buildings.md` §5 Theme 1 with the vendor-response history)
- **Substance Designer — parameter flood + no feedback.** A 20-year power user, directly quoted:
  "still amazed how monstrously inconvenient it is in its every detail… I was an ardent fan of
  everything node based before SD"; on black boxes: "a mixer with gazillion sliders I have no deep
  understanding what they are doing"; on feedback: "you need a special voodoo to see what your
  math change is actually doing"; on errors: "Any your mistake and it never helps you to identify
  it" ([Polycount](https://polycount.com/discussion/211739/can-we-replace-substance-designer-with-something),
  [hate thread](https://polycount.com/discussion/216930/which-software-do-you-hate-the-most-to-work-with-for-whatever-reason)). ★★★
  Adobe's fix was **audience segmentation into separate products** (Painter, Sampler) — which
  worked commercially but lost the depth: the same power-artist found Sampler "same crazy alien"
  because his need was *nuance control*, not fewer nodes. Segmenting into separate *products*
  creates the cliff; segmenting into *tiers of one product* (RailClone) keeps the ramp. ★★
- **ZBrush — bad UI surviving on monopoly capability.** "Totally from the moon in terms of UI…
  but is just so much more powerful… so people live with it"; "Most zbrush users hate the software
  too" ([Polycount](https://polycount.com/discussion/161355/zbrush-i-just-dont-get-it)). Survives
  because the *core loop* (brush on mesh) is intuitive — the hostility is all in the shell — and
  because it had a decade without a competitor. Two lessons: **capability amnesty is real but
  temporary** (Blender sculpt threads fill with defectors), and **UI debt calcifies**: when Maxon
  finally announced a modern UI in Nov 2025, the expert community split, muscle memory fighting
  the fix. ★★★
- **Houdini, as non-technical artists see it.** "Chock-full of programming… Are there tutorials
  that do this kind of thing, but in a more artist-friendly way? Like instead of programming a
  circle of points, just have a node that already does that" (r/vfx). Note what is asked for:
  **the same power, pre-packaged at a higher altitude — not less power.** SideFX's response is
  the one that mostly worked: never simplify the core, build an altitude system (HDAs, Engine,
  Labs) with an explicit TD-authors/artist-drives split. The residual failure is ours to avoid:
  **an HDA is only as good as its author's parameter curation.** ★★★
- **Blender Geometry Nodes — the abstraction leaks.** Artists on fields: "It's still nebulous and
  I'm not confident I understand the concept"; the community's successful explanations are all
  programmer framings ("think of them just as arrays"), and Blender's own devs conceded the 2.93
  design failed because "artists should be able to operate directly on attributes, but how to do
  that was unclear" ([dev blog](https://code.blender.org/2021/08/attributes-and-fields/)).
  Debugger = a spreadsheet. Plus the studio-workflow failure: consuming artists retyping attribute
  names "50 times a day" — **the packaging layer punishing the consumer with the author's debt**
  ([devtalk](https://devtalk.blender.org/t/geometry-nodes-cant-be-used-in-studios-due-to-avoidable-forced-repetition/21627)). ★★★
- **World Machine — UI debt as public identity.** The complaints are *inconsistency*, not
  concepts: mixed fonts, sliders that sometimes accept typing, "some things require a
  double-click… some things require that you select them and then hit a button", windows opened
  and closed to see output ([official forum](https://forum.world-machine.com/t/its-time-to-modernize-the-wm-experience-with-a-complete-ui-overhaul/4885)).
  Gaea won on live feedback and presentation, not algorithms. ★★★
- **The dead city generators** (Suicidator, SceneCity, Ghost Town). Honest reading: maintenance
  economics killed them (one-developer projects vs DCC version churn), **but usability set the
  ceiling** — none crossed from "toy that makes a generic city" to "tool an art director
  controls". SceneCity's rigid 10 m grid ("you cannot change the cell size without changing the
  assets too", [official docs](https://scenecitydoc.cgchan.com/grid-cities)) means every render
  looks like SceneCity — closed vocabulary + rigid generator = no art direction = no paying pros
  = no survival funds. ★★ (the economics reading is inference)
- **In-house tools.** GDC Tool Design Roundtable notes ([rystorm.com](https://rystorm.com/blog/roundtables-gdc-2023)):
  a participant "spent a bunch of time programming a new tool that in the end never got used and
  has been shelved"; recurring advice — observe real workflows first, "it is very easy to keep
  adding more and more things", split mega-tools per-workflow. Positive counterexample: Horizon
  Zero Dawn's procedural placement won adoption via artist-authored rule graphs, live in-viewport
  results, and **placement always respecting hand-placed overrides**
  ([GDC](https://gdcvault.com/play/1024700/GPU-Based-Run-Time-Procedural)) — our Contract 2, shipped. ★★★/★★

## 4. What the verified literature adds

Everything below was located and confirmed by URL; sought-but-unverified items are listed at the end.

1. **Progressive disclosure has a measured ceiling: two levels** (Nielsen, NN/g 2006,
   [article](https://www.nngroup.com/articles/progressive-disclosure/)). Primary parms + one
   Advanced tier; past that users get lost between levels. The primary/secondary split must come
   from **observed frequency of use, not designer intuition**, and the disclosure affordance must
   be obvious — hidden ≠ unadvertised. Staged (wizard) disclosure specifically fails when steps
   are interdependent — which street ↔ lot ↔ building decisions are; a strictly wizard-shaped
   city tool would fight the domain. ★★★
2. **Defaults are the product — measured.** UIE/Jared Spool 2011
   ([source](https://archive.uie.com/brainsparks/2011/09/14/do-users-change-their-settings/)):
   of several hundred collected MS Word configs, **fewer than 5 % had changed *any* setting**.
   Two details: Word's autosave default was off because a programmer zero-initialized a struct —
   defaults ship whether you design them or not; and interviewed users assumed the defaults were
   *recommendations by the author*. Corroborated by Nielsen's "Power of Defaults" (2005). Our HDA
   defaults are our loudest art direction — §2.0's "sourced, not invented" rule now has teeth. ★★★
3. **For discontinuous parameter spaces, show variations, not sliders.** An unbroken 27-year
   research line: Design Galleries (Marks et al., SIGGRAPH '97 — parameter→output mappings are
   "multidimensional, nonlinear, and discontinuous", so auto-generate perceptually dispersed
   alternatives and let the user browse) → Sequential Line Search / Sequential Gallery (Koyama et
   al. 2017/2020 — one meaningful macro-slider or 2D gallery standing in for n raw parameters) →
   CHI 2024 (gallery-style design-space exploration still beating alternatives). Sliders with
   live preview win for *targeted refinement*; galleries win for *exploration* (Terry & Mynatt,
   UIST '02: persistent side-by-side previews, non-destructive what-ifs). ★★★
4. **The flexibility–usability tradeoff** (Lidwell/Holden/Butler, *Universal Principles of
   Design*): flexibility is a hedge against *unknown* needs — **the better you understand your
   users' actual task, the more you should bias toward opinionated, task-shaped controls.** We
   can observe our artists; generic exposure is an excuse not to. Plus Alan Kay: "simple things
   should be simple, complex things should be possible." ★★★
5. **Norman's two gulfs name our failure modes.** Execution gulf: the artist can't map "cozier
   streets" onto `lot_subdiv_bias 0.3` — fixed by result-named macro parameters. Evaluation gulf:
   after moving a slider they can't tell what changed — fixed by live preview and diff
   visualization. ★★★
6. **Game-industry tools UX** (Lightbown's *Designing the UX of Game Development Tools*, GDC Tools
   Tutorial Day, Riot/Bungie/Insomniac talks — all verified): **watch artists work, don't ask**;
   instrument the tool and rank features by measured frequency; adoption is decided by iteration
   speed, stability and familiarity before feature count; internal artists are customers. ★★★
7. **SideFX's official HDA guidance is thinner than folklore claims** — the
   [official guidelines PDF](https://media.sidefx.com/uploads/contests/techchallenge2021/hda_guidelines.pdf)
   covers namespacing, icons, tooltips, docs, and **promoted parameter names "that indicate the
   role of the parameter from the artist's perspective"** — but says nothing about parameter
   count, presets, or layering. The naming rule is the one thing official guidance and every
   community source agree on. ★★★
8. **Sought and NOT verified** (recorded so nobody cites them later): no "designing defaults" by
   Jarrett; no "Jensen Harris Word settings study" (that's Spool's); no GDC talk titled
   "Techniques for building tools artists love"; "one top-level control per decision" and
   "ramp + seed" are **not** written SideFX doctrine — community folklore, principle-compatible
   but uncitable. Stålberg's exact phrase "constrained tools feel better" also unverified —
   paraphrase only.

## 5. The patterns — what survives across all four reports

**Success patterns (all ★★★ unless noted):**

1. **Two contracts, one asset.** Author tier sees everything; artist tier sees an *authored*,
   deliberately promoted subset. The boundary is a ramp (tweak → swap geometry → toggle → author),
   never a cliff — and never two separate products.
2. **Presets are the primary UI.** The library is the front door; parameters are the tweak layer
   behind it; the graph is the back office. Practitioners *learn by dissecting presets*, so
   presets must be built cleanly enough to be teaching material, with shared naming conventions.
3. **Borrowed mental model.** The artist-facing surface wears something artists already operate
   (layers, brushes, curves, palettes, real-world domain nouns) even when a graph lives beneath.
4. **Latency is the real overwhelm.** Interactive response converts parameters into instruments;
   every extra second between tweak and picture is attrition. A live proxy beats a faithful wait.
5. **Control split by scale.** Artist owns the large shapes; the tool guarantees the small ones
   via value + variance + curve, not per-element knobs. (Per-element *override* stays — that's
   Contract 2 — but per-element *parameterization* is the flood.)
6. **Escape hatch to manual, always.** Any generated element convertible to hand-edited without
   leaving the tool, and procedural regeneration must never overwrite the hand edit.
7. **Derived relationships keep few knobs honest** — one exposed value driving many internal ones
   via expressions, so coherence survives simplification.
8. **Refuse the unsolvable gracefully** — a missing feature with a clear "no" beats a knob that
   half-works. (★★)

**Failure patterns (all ★★★ unless noted):**

1. **Code as the interface** — the capability ceiling lives in text (CGA, VEX, Pixel Processor)
   and artists hit it day one. Every vendor eventually builds a no-code layer, always *after*
   losing the audience.
2. **The two-tier cliff** — wizard OR code with nothing between; the artist who outgrows the
   wizard falls the full height of the wall.
3. **Parameter flood without hierarchy** — knobs exposed because the graph has them, not because
   an artist decision maps to them.
4. **Feedback outside the viewport** — spreadsheet debuggers, per-node previews, open/close-to-see.
5. **Leaked internal model** — fields, document/tool, cook order, attribute names surfacing in the
   artist's face, contradicting spatial intuition.
6. **Consumer pays the author's debt** — setup ritual, retyped names, lazy parameter pages.
7. **Destructive or opaque steps in a supposedly procedural tool** — fear of irreversible loss
   kills exploration. (★★)
8. **Errors that don't teach** — red nodes with no memory, failures in solver vocabulary.
9. **Capability amnesty calcifies** — bad UI survives only under monopoly, and by then your own
   experts will fight the redesign.

## 6. What this implies for polyfactory / citygen — *implications, not design*

Checked against what [`citygen.md`](citygen.md) already fixes. Items marked ✅ are already
designed; items marked ⭕ are new obligations this study creates.

1. ✅ **Never overwrite manual edits** — Contract 2 / the override layer is exactly the HZD rule
   and success pattern 6. **Escape-hatch-to-manual is the §2.3 authoring model.** The evidence
   says these are the two rules production tools live or die by; they outrank everything in §5.
2. ✅ **Errors in artist vocabulary, never a wall** — §2.2 (advisory validation, persisted,
   visualizable warnings) matches failure pattern 8's fix and Stålberg's "allowed to fail
   silently" (we go one better: fail *visibly but non-blockingly*).
3. ⭕ **Adopt the RailClone promotion discipline for every end-user HDA:** the artist-facing
   parameter page starts *empty*; every promoted parm is a deliberate opt-in that must (a) be
   nameable in an art director's sentence ("storefront variety", not `facade_module_entropy`),
   (b) carry range limits, units and a help text, (c) map to a *decision*, not a graph value.
   Houdini's parameter interface editor supports all of this natively — this is authoring
   discipline, not new tech.
4. ⭕ **Two disclosure levels, maximum.** Main page + one Advanced folder per HDA (Nielsen's
   ceiling). No folders-in-folders-in-folders. The primary/secondary split gets revisited from
   *observed use* once real artists (or Hannes-as-artist) touch the tools.
5. ⭕ **Defaults are sourced AND every default must render a good-looking result out of the box.**
   §2.0 already demands sourced defaults; Spool adds the second half: ≥95 % of eventual users
   will live entirely on them, and they will read every default as our recommendation.
6. ⭕ **The preset corpus is a deliverable, not an afterthought** — same conclusion
   [`terrain_presets.md`](terrain_presets.md) reached for Gaea, now generalized: presets per
   subsystem (street styles, block characters, junction treatments), thumbnail-browsable, built
   cleanly enough to be dissected as teaching material, under shared naming conventions.
   Houdini's native preset/recipe mechanisms are candidates; which one is a design question for
   build time, not this study.
7. ⭕ **An interactive proxy LOD is a UI feature, arguably *the* UI feature** — a greybox city
   that re-flows while a slider drags beats any parameter-count reduction (success pattern 4).
   This should become an acceptance criterion for every stage HDA: *some* LOD of the stage's
   output responds at interactive rates. Also the "one-button generate everything" wrapper §2.3
   already lists as missing is failure-pattern-3 insurance: never present a blank canvas.
8. ⭕ **Author the junctions.** Artists judge the tool at street corners, slope transitions and
   district seams (Stålberg + buildings Theme 4 on corners agreeing from opposite directions).
   Junction quality is artist-facing UI in the widest sense: it is what the tool's output says
   about itself.
9. ⭕ **Control split by scale, stated as a rule:** expose *distributions* (value + variance +
   profile curve, SpeedTree's proven triple) for small shapes; expose *direct authorship* (paint,
   draw, drag) for large shapes; keep per-element access in the override layer rather than the
   parameter page. This is how "everything changeable" and "nothing overwhelming" coexist.
10. **The graph stays reachable — unlocked HDAs, macros as the middle tier.** Matches the §5
    SideFX Labs policy (open wrappers) already in citygen.md. Power users collapsing sub-nets
    into named, shareable assets is how the vocabulary grows without us shipping every node.
11. **Watch, then curate.** Lightbown/GDC consensus: the promoted-parameter set is a hypothesis
    until someone watches an artist use it. For a solo project this means: dogfood in artist
    mode, and treat every time *we* open the graph to fix something as evidence a knob or preset
    is missing.
12. ⭕ **The `houdini-tool-design` skill should absorb the distilled rules** (empty-by-default
    promotion, two-level ceiling, defaults-are-the-product, latency-is-the-overwhelm, ramp not
    cliff) once adopted — it currently asserts the *why* ("art direction is the cardinal rule")
    without this evidence layer or the concrete numbers. Not done yet; listed here so it isn't
    forgotten.

## 6b. The study applied across every polyfactory tool — audit of the other studies

Added 2026-08-21 on Hannes' request: not only citygen — every tool researched in the past days,
checked against §5's patterns. Format per tool: what its design already gets right / what
obligation or risk this study adds. Same ✅/⭕ marks as §6.

### Streets — [`citygen_streets.md`](citygen_streets.md), in build

- ✅ **Artist owns the large shapes, literally.** S1's field generators are *paintable and
  blendable* (grid/radial/organic/terrain/`brush`), and S3-as-contract-point means hand-drawn
  splines are first-class producers — the ramp has entry points at every altitude. §11.12
  explicitly reserves naming and look decisions for the artist.
- ✅ **The evaluation gulf is already being bridged the hard way**: three times the artist's
  viewport reading overturned green checks (§11.12) — which is this study's argument for
  show-don't-tell made empirical, and exactly why junction quality (§6.8) is UI.
- ⭕ **The promotion pass is still owed.** [`citygen.md`](citygen.md) Contract 7 schedules v1 as
  "everything exposed" with states in v2 — correct build order, but per §6.3 the *artist-facing*
  face of each stage HDA is a separate authored deliverable, not the v1 parameter sheet with
  folders added. The S0–S8 parameter sheets as built are the *author* tier.
- ⭕ **Greybox-while-dragging** (§6.7) needs an answer per stage; the streets chain is currently
  cook-shaped, not drag-shaped.

### Buildings — [`citygen_buildings.md`](citygen_buildings.md), research only

- ✅ The study independently found this study's two biggest failure patterns before it existed:
  the grammar wall (its Theme 1 = §5 failure 1, with CityEngine's own Visual-CGA pivot as
  evidence) and tools dying of interfaces (Theme 5). Its corners finding (Theme 4) and
  Stålberg's junction principle (§2) are the same lesson from opposite directions.
- ✅ **The lot→footprint pluggable operation (§7 there) is a named-high-level-primitive done
  right**: `setback` / `shapeL` / `shapeU` are artist nouns wrapping geometry ops, identity is a
  legal choice, validation is advisory.
- ⭕ **The style problem is the preset corpus problem.** Theme 2 ("one generator = one look",
  everyone sidesteps by swapping data) plus §5 success pattern 2 fix the eventual design's
  shape: style enters as *data* — module libraries + openable style presets under shared naming
  — never as a second grammar. When the building tool is designed, text rules (if any exist
  internally) must never be the only path to an art-directable outcome (§5 failure 1).

### Traffic / crowds — [`citygen_simulation.md`](citygen_simulation.md), design spec v0

- ✅ **The three authoring tools (§10.5 there) are already shaped like the evidence demands**:
  draw-an-area (its Theme 5, "people love it when the setup is *drawing*"), draw-a-path, and
  per-agent overrule through Contract 2 (its Theme 1 = §5 success 6, the escape hatch).
- ✅ **The area+POI primitive (§10.5a) is the best decision-shaped parameter set in the whole
  project**: one authored element carrying capacity, dwell, `gaze_weight`, clip set — every
  field nameable in an art director's sentence, and `gaze_weight` is explicitly the anti-clone
  lever. This is what §6.3 asks every promoted parameter page to look like.
- ⭕ **Latency is the named risk** (its Theme 4: "the tools are heavy, and the heaviness lands on
  the artist"). The static scatter→visibility→gaze path shipping before any solver is the right
  order per §5 success 4; a proxy-density preview mode should be in the spec from day one.

### Terrain presets — [`terrain_presets.md`](terrain_presets.md), parked

- ✅ **That study reached this study's conclusions independently, from one tool**: named landform
  primitives ("a canyon starts with a node called `Canyon`"), meta-nodes as the macro tier
  (Wizard), and its own headline — *naming the looks is most of the usability win and it is the
  scarce part*. Gaea-over-World-Machine is also §2's latency finding.
- ✅ The planned work (~20 named recipes, hand-calibrated to Gaea's reference renders) *is*
  §5 success 2, and the calibrate-to-reference loop enforces §6.5's "every default renders a
  good-looking result".
- ⭕ When the recipes are authored, their parameter faces get the §6.3 promotion discipline —
  Houdini's `heightfield_erode` has 58 parameters and the recipe face should carry the ~6 that
  map to decisions (the Gaea preset carried 23 and most presets touch far fewer).

### Foliage — [`foliage.md`](foliage.md), design complete, parked

The design already follows the tool-design skill deliberately (shape + cost controls, §7 note 1
there; species = preset, bare points must grow). Three findings sharpen it:

- ✅ **Keeping Opara's section grouping is the right call for the wrong-sounding reason**: it is
  a *proven artist-facing grouping* — a borrowed surface from a tool artists demonstrably used,
  which is §5 success 3.
- ⭕ **The parameter names are solver vocabulary.** `Apical Dominance`, `Flush Threshold`, `Pipe
  Exponent` are the execution gulf (§4.5): an artist wants "spreading ↔ pyramidal", which *is*
  λ (its own test T2 proves the mapping!). Fix is cheap: result-named labels and help text on
  the promoted face (λ stays in the tooltip for the botanist), plus a top-level face of the
  ~6 decision knobs; the ten sections become the Advanced tier. Two levels total (§6.4).
- ⭕ **Interactive pruning gets a priority upgrade.** Open question 1 defers The Grove's
  most-loved tool past M5 — but §5 success 6 says the manual escape hatch is the pattern
  production tools live by (★★★). Keep the deferral (scope), but treat it as v1.1, not "maybe";
  the id-scheme-must-not-preclude-replay note is what makes that possible.
- Species corpus: pine + oak proves G2; the *usable* front door needs the SpeedTree-style
  species library eventually — same preset-corpus obligation as terrain and buildings.

### Fabric / polyKnit — [`fabric.md`](fabric.md), design complete, parked

- ✅ **The Marvelous Designer pattern, chosen before this study named it**: panels, seams, charts
  and stitch names are the knitter's own domain carried through the whole tool — the deep
  metaphor §2 says beats shallow simplification. MD's corroborated caveat transfers too: it
  gates artists who don't share the domain. polyKnit's mitigations already exist (five stitch
  presets, paint, chart-*image* input — pixel art is a metaphor every artist has).
- ✅ The mandatory preview SOP (VK viewport won't resolve procedurals) is §5 success 4 arrived at
  from a renderer constraint; M7's acceptance ("authored … in under an hour of artist time") is
  the tool-design skill's test stated as a gate.
- ⭕ **The consumer tier is missing a garment-level front door.** Panels+seams is the *author*
  tier; a non-knitter artist's entry point is a whole-garment preset (sweater/cardigan/scarf
  templates with promoted fit + pattern knobs). Post-M7, but it is the RailClone lesson: the
  preset library, not the panel workflow, is what most users would touch.

### Hair grooming — [`hair_grooming.md`](hair_grooming.md), research, parked

That study is itself partly a UI study; read back through this one's patterns:

- **Disney's hierarchy is §2's control-split principle in production form** — coarse parent
  curves are Stålberg's "large shapes", children keep local structure, and it works pre- *and*
  post-sim. That the on-the-fly variant served all 772 characters without authored hierarchies
  strengthens the §3.1-there build order (on-the-fly first).
- **Wētā is the instructive apparent counterexample to §5 failure 7** (destructive workflow):
  no-history commits, yet beloved. The resolution: destruction is safe when it rides a mental
  model that *is* destructive in the artist's prior life (Photoshop pixels, sculpting) **and**
  transfer/merge tools replace what history would have given you. Destructive-and-alien
  (ZBrush's shell) scares; destructive-and-familiar (brushes on hairs) doesn't.
- **Drawovers as the specification** (the most-repeated Disney finding) is a workflow answer to
  the execution gulf worth remembering for citygen review passes: artists specify in their own
  medium, the tool owner translates.

### Asset library / kitbash — [`asset_library_redesign.md`](asset_library_redesign.md), planning

- ✅ Blender-style browser = borrowed surface (§5 success 3); thumbnail grid = the gallery
  paradigm (§4.3); single-asset HDA replacing the multi-asset kitbash HDA is §5 failure 6 fixed
  (the consumer was paying the author's complexity).
- ⭕ Drag-drop with the interactive placement state is the direct-manipulation half — per §5
  success 4/6 it is the feature, not the polish; prioritize it over browser chrome.

### The cross-study observation

Four studies (buildings, simulation, terrain, and Gaea's own design) independently converged on
the same conclusions this study found in the external evidence — named looks, drawing as setup,
per-element overrule, data-not-grammar. Independent convergence from different corners is itself
corroboration: treat §5 as project law, not one study's opinion.

---

## 7. Corroboration summary and honest gaps

Strongest evidence: the Painter/Designer natural experiment, the RailClone promotion mechanism
(read in vendor docs, corroborated by reviews and user threads), Spool's measured defaults study,
Nielsen's disclosure ceiling, and the cross-tool latency finding. Weakest: "most RailClone users
never open the Style Editor" (inference, ★★); artist sentiment specifically about SideFX Labs
(★ — searches found mechanism, not love); the dead-city-generator economics reading (inference);
EmberGen quotes are vendor-curated (mitigated by independent agreement on the iteration claim).
GDC Vault video content was reachable only via notes and summaries, not transcripts.
