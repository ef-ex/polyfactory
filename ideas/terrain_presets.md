# Terrain Presets — the Gaea study

**Status:** research complete, nothing implemented. No code, no HDA, no recipe written.
**Question asked (Hannes, 2026-08-15):** *"Houdini already ships with really great terrain tools,
but what I miss are presets. Gaea is so user friendly — if we can get that workflow in Houdini
this would already be amazing."*

**This file owns:** what Gaea's authoring model actually is, what Houdini 22 already has, and
whether Gaea's presets can be transferred. It is a **tooling** study.

**This file does NOT own** the terrain subsystem of CityGen. [`citygen.md`](citygen.md) §1 reserves
terrain as an unwritten subsystem (`terrain → vegetation → city`). When that gets designed it
belongs in a `citygen_terrain.md`, which should link here rather than restate this.

⚠️ **Parked.** CityGen streets are mid-flight. Nothing here should start before citygen ships.
Same parking rule as the foliage knowledge base.

**Artist-facing UI:** [`artist_ui.md`](artist_ui.md) §6b audits this doc — the recipe plan is
that study's preset pattern verbatim; the added obligation is the promotion discipline when the
recipe faces are authored (~6 decision knobs, not `heightfield_erode`'s 58).

---

## 0. The one-paragraph answer

Gaea's usability is not better nodes — Houdini's erosion is competitive per-node. It is
**(a) named landform primitives**, **(b) a preset/quickstart corpus**, and **(c) meta-nodes that
collapse a whole look into one node**. Houdini has a modern, supported, programmatically
authorable preset mechanism — the **recipe system**, new in recent builds and the successor to
the gallery — and it is essentially **empty for terrain** (2 shipped recipes) and **Copernicus-only**.
Gaea's *preset names, chain topologies and design notes* transfer freely (MIT licensed).
Its **parameter values do not transfer at all** — the two erosion solvers share exactly one
parameter name.

---

## 1. What Gaea is

**Fixed pipeline:** `Create → Modify → Erode → Texture → Build`.

**~182 nodes across 9 families** — counted by hand from the published node map, so treat the
total as *computed*, not vendor-stated.

| Family | Count | Contents |
|---|---:|---|
| Primitive | 23 | Perlin, Voronoi, Gabor, Cellular, MultiFractal, gradients, Draw |
| **Terrain** | **14** | **Canyon, CraterField, DuneSea, MountainRange, Plates, Ridge, Rugged, Slump, Uplift, Crater, Island, Mountain, MountainSide, Volcano** |
| Modify | 40 | Adjust/Clamp/Equalize, blurs, Warp/SlopeWarp/DirectionalWarp, Curve/Recurve/Fold/Shaper |
| Surface | 21 | Stratify, FractalTerraces, Sandstone, Terraces, Craggy, Outcrops, Shatter, Shear, Sand |
| Simulate | 25 | Erosion, Erosion2, Thermal2, **Wizard/Wizard2**, EasyErosion, Rivers, Lake, Sea, Snow, Glacier, Trees, Shrubs |
| Derive | 14 | Slope, Curvature, Peaks, Normals, Occlusion, FlowMap, RockMap, Soil |
| Colorize | 13 | **SatMap**, CLUTer, SuperColor, Weathering, RGBSplit/Merge |
| Output | 12 | Export, Mesher, Unreal, Unity, PointCloud, AO, Sunlight |
| Utility | 20 | Combine, Mixer, Switch, Gate, LoopBegin/End, Chokepoint, Math, Var |

### 1.1 The four things that make it feel easy

1. **Named landform primitives.** A canyon starts with a node called `Canyon`.
2. **Meta-nodes.** `Wizard` carries a whole erosion look behind named profiles (Craggy,
   Dessicated, Fast Erosion, Rivers). One node, one look.
3. **`SatMap`** — instant satellite-derived colour from preset palettes (New Rock, Sand, Green,
   Blue, Color), with Range/Bias/Processing/Rough. A believable colour pass in one node.
4. **The corpus** — see §2.

---

## 2. The preset corpus — measured, not summarised

Source: [QuadSpinner/Gaea-Quickstarts](https://github.com/QuadSpinner/Gaea-Quickstarts).
**MIT licensed** (`Copyright (c) 2018 QuadSpinner`), with the caveat that *use inside the Gaea
application* is governed by Gaea's own EULA. The **files themselves are MIT**.

Downloaded and parsed in full on 2026-08-15. 388 blobs.

| Kind | Count | Format |
|---|---:|---|
| `.tor` graphs | **158** | base64 → 4-byte LE length prefix → **gzip → plain XML** |
| `.gpr` presets | **95** | **plain XML**, uncompressed |
| `.jpg` previews | 125 | one reference render per recipe |
| `.tor.resource` | 4 | embedded assets |

**All 158 `.tor` files parsed cleanly.** The format is fully machine-readable.

### 2.1 Graph size — the usability number

```
nodes per graph:  min 1   median 6   mean 9.4   max 90
```

- **1 node** — the `Blank/` starters (Perlin, Voronoi, Ridge, Plates, Slump…)
- **2–4 nodes** — the named terrain types
- **3–10** — `Techniques/`
- **30–90** — full ecosystems and texturing chains

Worked examples, verbatim from the parsed graphs:

| Recipe | Chain |
|---|---|
| Hero Mountain | `Mountain → Wizard` |
| Rolling Hills | `Perlin → Rugged → Wizard` |
| Mesa (top-level) | `Canyon → Wizard → FractalTerraces` |
| Cliff | `SlopeNoise → StackedErosion → Wizard` |
| Landslide | `SlopeNoise → Shatter → Anastomosis → Hydro` |
| Carving with Rivers | `Mountain → Rivers → TS` |
| Shallow Canyon | `SlopeNoise → FractalTerraces → FractalWarp → Wizard` |

**A "hero mountain" is two nodes.** That is the entire usability claim, quantified.

### 2.2 Categories present

`Blank` (12), `Canyon` (8), `Cliff` (5), `Crater` (6), `Hill` (8), `Landscape` (16),
`Mountain` (16), `Snow` (6), `Techniques` (22), `Texturing` (6), `Vegetation` (7), `Water` (12),
plus 23 `Houdini/` files (see §5) and `Dax's Doodles`.

### 2.3 The 182 author notes

Every quickstart carries `<Note>` elements explaining *why* each node is there. This is the part
that cannot be reconstructed from the graph alone. Sample, verbatim:

> Shatter LookDev adds all the necessary erosion, debris, and collapses to the basic shape.
> No need to use multiple Erosion nodes for this.

> Erosion with high Random Sedimentation and Sediment Removal gives our craterfield an eroded
> look without creating too many soil deposits. This helps preserve the shape while adding
> erosive details.

> Folding is used to create strong, folded strata across the terrain. In Post Process, Min mode
> is used to avoid any protruding shapes and only keep the inwardly folded shapes.

### 2.4 The `.gpr` preset format

Plain XML, trivially parseable:

```xml
<Preset ApplicableType="Erosion" Name="Old Eroded Mountains">
  <Paramaters>                              <!-- sic, misspelled in the format -->
    <Parameter xsi:type="PDouble"  Name="Duration"      Value="0.23234604034351811" />
    <Parameter xsi:type="PDouble"  Name="Rock Softness" Value="0.65" />
    <Parameter xsi:type="PInt"     Name="Feature Scale" Value="2000" />
    <Parameter xsi:type="PBoolean" Name="Rivers"        Value="false" />
    <Parameter xsi:type="PChoice"  Name="Mask"          Value="3" />
  </Paramaters>
</Preset>
```

**The naming convention is the transferable idea:** `ApplicableType` + a *look name*.

Distribution across the 95 presets:

| ApplicableType | n | Names |
|---|---:|---|
| Erosion | 17 | Ridge Eroder, Old Eroded Mountains, Desert Hills, Mesa or Terraces, Hard Erosion, Strong Channels, Superficial Debris, Quick and Dirty… |
| Snow | 16 | Spring Remnants, Melting Flows, Deep Channels Only, Dusting, Large Snow Field… |
| CE | 14 | Long River Flows, Hard Furrows, Gouge, Deposits, Scramble, Shatter into Rivers… |
| Thermal | 8 | Strong Talus, Heat Fused Rock, Decimated, Thermal Smoothing, Shallow… |
| others | 40 | Lighting (4), Canyonizer (3), Combine (3), Displace (3), Height (3), … |

---

## 3. Houdini today — measured on this install

Houdini **22.0.398**, probed live 2026-08-15.

- **63** SOPs matching heightfield/terrain, **~43 distinct** after version duplicates
  (`heightfield_erode` has ::2.0 and ::3.0), Labs, KineFX and QuadSpinner entries.
- **Parameter counts are not the problem.** `heightfield_erode::3.0` = 58 parms;
  `::2.0` = 108; `heightfield_slump` = 48; `heightfield_scatter::2.0` = 43. Comparable to Gaea.
- **No landform primitives at all.** The only shape node, `heightfield_pattern`, has this
  complete menu: *Ramp, Exp. Ramp, Steps, Stripes, Stars, Cells*. There is no `Canyon`,
  no `Volcano`, no `DuneSea`. Every landform is built by hand from noise.
- **Zero presets.** `oppresetls Sop/heightfield_erode::3.0` → `(none)`. Same for every
  heightfield node. `$HOUDINI_USER_PREF_DIR/presets` does not exist.

---

## 4. The mechanism — recipes, not the gallery

### 4.1 The gallery works, but is the old path

Verified by probe: a gallery entry **does** round-trip an entire multi-node chain, not just one
node's parameters. Built `heightfield → heightfield_noise → heightfield_erode::3.0 →
heightfield_terrace::2.0`, collapsed to a subnet, `hou.galleries.createGalleryEntry(...)`,
re-instantiated into a clean `geo` — **5 children in, identical 5 children out**, parameters
intact. (5 not 4: `collapseIntoSubnet` adds an `output` node.)

Houdini ships **92 gallery entries; the 25 SOP ones are all L-System presets** — Gnarly Tree,
Lightning, Dandelion, Bush, Roots. So SideFX built precisely this UX and never aimed it at terrain.

**But Hannes is right that recipes supersede it.** Use recipes.

### 4.2 The recipe system — the modern path

Present in H22 at `$HFS/houdini/`:

| Path | What |
|---|---|
| `otls/OPlibRecipe.hda` | the recipe asset |
| `python3.13libs/hrecipes/` | the API package — imports live, confirmed |
| `python3.13libs/recipeutils.py` | 608 lines; menu building, lookup |
| `RecipesMenu.xml` | the Recipes submenu in the **parameter** menu |
| `python_panels/RecipeManager.pypanel` | **Recipe Manager** panel |
| `help/heightfields_cop/recipes.txt` | terrain recipe documentation |

**It covers exactly the two preset kinds we want** — from `hrecipes/api/recipedata.py`:

- `recipeDataForParmPreset` — parameter presets (the `.gpr` equivalent)
- `recipeDataForNodePreset` — whole node/network presets (the `.tor` equivalent)
- `recipeDataForTool`, `recipeDataForDecoration`

**Storage:** inside HDAs, as a `data.recipe.json` section, read/written through
`hrecipes.api.recipeassetio.AssetIO` — `saveRecipeData`, `saveMetadata`, `saveRecipePreScript`,
`saveRecipePostScript`. **So recipes are programmatically authorable**; a generator script is
viable. `iconNameForRecipe` means entries carry icons; `submenusForNode` / `submenusForParm`
surface them in node and parameter context menus.

### 4.3 ⚠️ The catch — Copernicus only, and nearly empty

From `help/heightfields_cop/recipes.txt`, verbatim:

> Houdini ships with ready-to-use heightfield recipes. You can load them directly from the tab
> menu's __Terrain__ section.
>
> NOTE: The recipes are _only_ available for Copernicus-based heightfields and don't have a
> SOP-based counterpart.

**Two** terrain recipes ship: **Terrain Cobblestone** and **Terrain Sandy Rocks**. Plus a
[nine-example Learning Library HIP](https://www.sidefx.com/contentlibrary/heightfield-examples/).

And Copernicus is the thinner side: **13** COP terrain nodes against ~43 in SOPs —
`heightfield_erode`, `heightfield_strata`, `heightfield_terrace`, `heightfield_slump`,
`heightfield_clip`, `heightfield_maskbyfeature`, `heightfield_project`, `heightfield_visualize`,
`heightfield_xform`/`xform2d`, `heightfieldtomono`, `monotoheightfield`, `dilateerode`.

**The tradeoff to decide before starting:** recipes are the supported, icon-bearing, authorable
path — but officially they reach only Copernicus, where there are a third as many nodes. If our
terrain work is SOP-based, the recipe system does not officially reach it.

---

## 5. ⚠️ Can the presets transfer? Mechanism yes, numbers no

**This is the load-bearing finding.** Parameter spaces compared directly.

**Gaea `Erosion`** — 23 substantive parameters (union across its 17 presets):
`Duration, Rock Softness, Strength, Downcutting, Inhibition, Base Level, Real Scale,
Feature Scale, Terrain Scale, Verticality, Volume, Debris, Rivers, Depth, Mask, Seed,
Aggressive Mode, Process Mode, Parallel Speed, Bias Type, Bias, Reverse, Sediment Removal`

**Houdini `heightfield_erode::3.0`** — 58 parameters:
`erodability, flow, bankangle, coverage, slopeinfluence, erosion, deposition, removal,
evaporation, weathering, cutangle, reposeangle, spreaditers, erosionscale, iterations,
startframe, resimulate, dofreeze, freezeframe, cacheenabled, cachedframes, checkpointframes,
seed` + a `*maskmode` / `*masklayer` pair for **ten** of those + layer plumbing.

### The result

**Exactly one parameter name matches: `seed`.**

| Relationship | Parameters |
|---|---|
| Direct name match | `Seed` ↔ `seed` — 1 of 23 |
| Defensible analogue | Duration↔`iterations` · Rock Softness↔`erodability` · Sediment Removal↔`removal` · Debris↔`adddebris` · Feature+Terrain Scale+Verticality↔`erosionscale` (3→1, lossy) |
| No Houdini counterpart | Inhibition, Base Level, Depth, Real Scale, Rivers, Aggressive/Process Mode, Parallel Speed, Bias Type/Bias/Reverse |
| No Gaea counterpart | bankangle, coverage, slopeinfluence, evaporation, weathering, reposeangle, spreaditers, and the entire per-parameter mask-layer system |

**And the execution models differ.** Gaea's `Erosion` is a single-cook operator governed by
`Duration`. Houdini's is a **frame-based simulation** — `startframe`, `iterations`, `resimulate`,
`cachedframes`, `freezeframe`. There is no shared unit to convert between.

> A `.gpr` value of `Downcutting = 0.155` has nothing on the Houdini side to translate into.
> **Any automated numeric port would be inventing values.** Do not let a future pass claim
> otherwise.

### What genuinely transfers, descending value

1. **The taxonomy** — 95 preset names + 158 recipe names, MIT. *Ridge Eroder*, *Strong Talus*,
   *Spring Remnants*, *Mesa or Terraces*. Naming the looks is most of the usability win and it
   is the scarce part.
2. **Chain topology** — which node types in what order. Conceptually ~60–70 % mappable.
3. **The 182 notes** — stated intent per node (§2.3).
4. **Nothing numeric.**

### Therefore the work is calibration, not conversion

Per look: pick the Gaea recipe → build the Houdini chain → dial by hand until it matches Gaea's
shipped reference `.jpg` → save as a recipe. Human-in-the-loop, roughly per-look.

The one automatable part: **the repo ships a reference render for all 125 recipes**, so a
render→compare→tune loop is possible. That is its own project, not a side quest.

---

## 6. The shortcut nobody mentioned

**`quadspinner::gaea_terrain_processor::1.0` is already installed**, from
`F:/projects/SideFXLabs22.0/otls/quadspinner.gaea_terrain_processor.1.0.hda` — it ships with
**SideFX Labs 22.0**. Also `quadspinner::gaea_terrain_color_visualizer::1.0`.

Its 10 parameters: `terrain_file` (labelled *"Gaea 2.2 Terrain File"*), `generate_parameters`,
`execute`, `autocook`, `extra_data`, `cachedir`, `custom_swarm_exe`, `swarm_exe`.

So it loads a `.terrain` file, exposes its parameters in Houdini, and cooks it by calling
**`Gaea.SwarmHost.exe`**. It is a **bridge that runs Gaea's own engine**, not a reimplementation
— so it requires Gaea installed and licensed, and produces Gaea results, not Houdini-native ones.
This also explains the 23 `Houdini/*.tor` files in the quickstarts repo (Blank, Erosion, Stratify,
Terrace, Thermal, Snow, Soil, Plates, DuneSea, Shatter, Fold, Flow, Lakes, RockMap, Texture,
SurfTex, Igneous, ImpactCrater, VolcanicCrater, Convector, Protrusion, Stacks, Distribution).

**If the goal is Gaea's looks, this is the zero-porting path.** If the goal is a Houdini-native
preset library, it is irrelevant.

---

## 7. Options, ranked by value over effort

| # | Option | Effort | Notes |
|---|---|---|---|
| 1 | **~20 named node-preset recipes** (Hero Mountain, Shallow Canyon, Mesa, Layered Cliff…) authored via `hrecipes` | medium | The main win. Mechanism verified. Decide COP vs SOP first (§4.3) |
| 2 | **Parameter presets for `heightfield_erode`** using Gaea's taxonomy, values dialled by hand | low–medium | Names transfer free; numbers do not (§5) |
| 3 | **Landform HDAs** — `Canyon`, `DuneSea`, `Volcano` | high | The real gap (§3). Nothing in Houdini covers it |
| 4 | **Render-compare calibration loop** against the 125 reference JPGs | high | Its own project. Do not start casually |
| 5 | **Use the Gaea bridge** | ~zero | Needs a Gaea licence; not Houdini-native (§6) |

**Recommended order if this ever starts: 2 → 1 → 3.** Option 2 is the cheapest way to find out
whether presets alone deliver the feeling Hannes is after, before committing to 1 or 3.

---

## 8. Verification ledger

Respect the difference between categories. Do not restate a *computed* or *snippet* row as fact.

### ✅ Verified — probed live in Houdini 22.0.398 or parsed from the downloaded files

- 63 terrain-ish SOPs; the full node list; all parameter counts quoted in §3
- `oppresetls` returns `(none)` for `heightfield_erode::3.0`, `heightfield_erode`, `heightfield_noise`
- `$HOUDINI_USER_PREF_DIR/presets` does not exist
- 92 gallery entries; all 25 SOP entries are `lsystem` presets
- Gallery entry round-trips a 5-node subnet with parameters intact (§4.1)
- `heightfield_pattern.pattern` menu is exactly the six listed items
- Recipe system files exist at the paths in §4.2; `hrecipes` imports successfully
- `recipeDataForParmPreset` / `recipeDataForNodePreset` / `AssetIO.saveRecipeData` exist
- The Copernicus-only note and the 2 shipped recipes — read from `recipes.txt`
- 13 COP terrain nodes
- `quadspinner::gaea_terrain_processor::1.0` installed, its library path and its 10 parameters
- Gaea repo: 388 blobs, 158 `.tor` (all parsed), 95 `.gpr`, 125 `.jpg`; MIT LICENSE
- Node-per-graph statistics and every chain quoted in §2.1
- The `.gpr` schema and the ApplicableType distribution in §2.4
- Gaea `Erosion` 23-parameter union — computed from the 17 presets themselves

### 🧮 Computed — derived by me, correct method, not vendor-stated

- **~182 Gaea nodes** and the per-family counts in §1 — hand-counted from the published node map
- The parameter-correspondence table in §5 — my judgement of which pairs are analogous

### 📄 Snippet-level — read from docs, not exercised

- Gaea `Erosion2` / `Rivers` / `SatMap` parameter descriptions (§1.1)
- Gaea 2.1 preset shortcodes (LongPass → LP) and preset search
- The nine-example Copernicus Learning Library HIP — **not downloaded**

### ⚠️ Known gaps — do not assume

- ⚠️ **The quickstart corpus is Gaea 1-era.** Node names in the `.tor` files are `CE1`, `SatMaps`,
  `Arboreal`, `TS`, `Shelves`, `StackedErosion` — Gaea 2 renamed these (`Erosion`, `SatMap`,
  `Trees`, …). Recipes translate; **names need remapping** before anyone quotes them as Gaea 2.
- **Gaea was not run.** Everything about Gaea here is from its documentation and its shipped
  files. No hands-on session, no visual comparison.
- **No recipe was authored.** The `hrecipes` write path is *documented and imports*, but writing
  a recipe end-to-end was **not exercised**. Prove it with a throwaway before planning on it.
- Whether a **SOP** network can be stored as a recipe despite the Copernicus-only note — untested.

---

## 9. Sources

**Gaea**
- Node reference — <https://docs.gaea.app/reference/index.html>
- Node map — <https://docs.gaea.app/reference/node-map.html>
- Your first terrain — <https://docs.quadspinner.com/Guide/Getting-Started/Your-First-Terrain.html>
- Quickstarts intro — <https://docs.quadspinner.com/Learning/QuickStarts/Introduction.html>
- Erosion2 — <https://docs.gaea.app/reference/nodes/simulate/erosion2>
- Rivers — <https://docs.gaea.app/reference/nodes/simulate/rivers>
- SatMap — <https://docs.gaea.app/reference/nodes/colorize/satmap>
- **Quickstarts repo (MIT)** — <https://github.com/QuadSpinner/Gaea-Quickstarts>
- Gaea 2.1 preview (shortcodes) — <https://blog.quadspinner.com/gaea-2-1-preview/>

**Houdini**
- `$HFS/houdini/help/heightfields_cop/recipes.txt` — the Copernicus-only statement
- `$HFS/houdini/python3.13libs/hrecipes/`, `recipeutils.py` — the recipe API
- Heightfield examples library — <https://www.sidefx.com/contentlibrary/heightfield-examples/>

**Reproducing the corpus analysis**

```bash
curl -sL https://github.com/QuadSpinner/Gaea-Quickstarts/archive/refs/heads/master.tar.gz | tar xz
```

`.tor` → `base64.b64decode(bytes)` → skip **4** bytes (LE uncompressed length) →
`gzip.decompress` → XML. Nodes are `<Node xsi:type="...">`; notes are `<Note>` elements.
`.gpr` is plain XML, no decoding needed.
