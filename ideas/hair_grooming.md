# Hair & Fur Grooming — the Wētā / Disney study

**Status:** research complete, nothing implemented. No code, no HDA, no OTL.
**Question asked (Hannes, 2026-08-15):** *"Houdini has a very solid hair system but I have seen
some features from Disney (Tonic) and Wētā that are amazing. Research the actual tools on the
user side for their hair and fur workflows."*

**This file owns:** what Wētā's Barbershop/Wig and Disney's Tonic/iGroom actually put in front of
an artist, and which of those capabilities Houdini does not have. It is a **tooling** study.

**This file does NOT own** shading/rendering of hair, hair simulation solver internals, or the
foliage/fabric knowledge bases (`polyfactory/resources/foliage`, `.../fabric`). If a hair
subsystem is ever designed it belongs in its own file that links here rather than restating this.

⚠️ **Parked.** CityGen streets are mid-flight. Same parking rule as the foliage and fabric
knowledge bases and as [`terrain_presets.md`](terrain_presets.md) — nothing here starts before
citygen ships. This is research library #3 in the queue.

---

## 0. The one-paragraph answer

The two studios solved the same problem from opposite ends. **Wētā treats a groom like a raster
image**: no procedural stack, no history, direct manipulation of every *final* hair, committed to
a bitmap-like sidecar file. **Disney treats a groom like a sculpture with a skeleton**: volumetric
tubes carrying a *persistent parent/child hierarchy* that survives all the way through simulation,
so a coarse control curve can re-pose a hairstyle after the sim has flattened it. Houdini's guide →
interpolate model already covers Disney's *other* half (iGroom + XGen). What it has no analogue for
is (1) the hierarchy-with-length-preserving-deformer and (2) full-density direct manipulation with
clone-stamp/mirror. Everything else worth stealing — wetness volumes, cage skinning, intersector
clipping — is small. And the whole Wētā artist toolset is **publicly documented**: Unity's Wig
manual is still live and is effectively the Barbershop manual.

---

## 1. Wētā: Barbershop → Wig

### 1.1 Lineage and status

| | |
|---|---|
| **Barbershop** | Original system. Sci-Tech Academy Award 2015 — Marco Revelant (concept/artistic vision), Alasdair Coull and Shane Cooper (architecture/engineering). Hobbit trilogy, Planet of the Apes, Tintin. A "new version" was used on *Kingdom of the Planet of the Apes* (2024) for dry + wet fur, war paint chips and clumped dirt — 95 unique grooms (54 hero apes, 41 extras). |
| **Wig** | Wētā's own description: the latest generation of the same hair-modelling lineage. Maya plug-in, USD-based. |
| **Unity era** | Unity acquired Wētā Digital's tools 2021; launched Unity Wētā Tools at SIGGRAPH 2023 with Wig in beta (final availability slated Oct 2023). Unity ended the Wētā FX services agreement in late 2023 (265 roles cut) and wound the division down. Reported outcome: Unity retained the IP, Wētā FX retained access and the right to extend it. |
| **Today** | ⚠️ Not purchasable. **But the full manual is still live** at `docs.unity3d.com/wig-docs/manual/` — ~110 pages, every tool, every node, every attribute. That document is the single best public artifact on this subject and is the primary source for §1.2–§1.7. |

### 1.2 The paradigm — why this is not Houdini

Four decisions, all deliberate, all the opposite of a procedural DAG:

1. **Full density, not guides.** Systems that groom ~10k guides and interpolate to ~100k at render
   time are described by Wētā as the thing they avoided. In Barbershop/Wig the artist manipulates
   the final hairs, every strand and every CV reachable. What you sculpt is what renders.
2. **No history.** Tools commit and the operation is gone — the explicit analogy from Wētā is
   Photoshop's treatment of an image. Cost: no re-dialling a decision from ten steps ago. Benefit:
   no dependency cascade, and grooms transfer between characters without dragging a graph along.
3. **A bitmap-like file.** Groom state lives in a `.wg` sidecar written on every Maya scene save —
   all strands, all per-strand and per-CV attributes. The manual's own analogy: it stores every
   pixel, not the instructions to draw them. Curves (clump curves, field curves, braid curves) stay
   in the Maya scene; strands live in the `.wg`.
4. **Groom and simulation are separated.** Revelant's stated intent was to *"break the connection
   between what is grooming and what is simulation"*. Clump detection passes strand-level groom
   structure into the solver so sim doesn't destroy the sculpt. Mechanically this shows up as the
   **lock/unlock** state: an unlocked Fur node is editable and un-simulatable; a locked one is
   read-only, and only then do the deformers, volume selectors and intersectors work at all.

**Scale defaults from the manual** (useful calibration): default density 10 strands/cm², recommended
50–100, **250 to approximate a human head**. Default 12 CVs per strand; **≥48 recommended for coils**.
Recommended taper: tip scale 0.5, tip scale offset 0.8. All strands in a fur node share a CV count.

### 1.3 Grooming tools

Brush-driven, all with radius + falloff + power + effect%, X/Y/Z reflection, `Shift`+MMB to size the
radius and `Ctrl`+MMB the falloff.

| Tool | Substance |
|---|---|
| **Comb** | 8 groom modes: **Comb** (push along stroke), **Gel** (pull in, all directions), **Blow** (push out, all directions), **Mess** (random noise), **Puff** (rotate toward surface normal), **Crush** (push down to surface), **Pinch** (pull in, parallel to stroke), **Spread** (push out, parallel to stroke). Puff/Crush are strands-only. `Ctrl`+LMB drags root/tip weight, `Shift`+LMB drags strength. |
| **Bend** | Two modes: **Accumulate** (adds bend, preserves existing shape) and **Deform** (overwrites). Arc Start/End define *where along the strand* the bend lives, and can be **absolute** (in scene units — strands shorter than Arc Start are skipped) or relative (0–1 fraction). Random noise mode bends each hair to a value between Arc Bend Min/Max. Separate follicle rotation (toward surface) and polar rotation (around normal). |
| **Length** | Blocking tool; has an **Average** mode to smooth length transitions between patches. |
| **Trim** | Instant cut at the cursor — the flyaway/texturizing tool, distinct from Length. Show Trim previews the affected strands. |
| **Eccentricity** | Adds a **wave** or a **helix**, randomized between min/max wavelength and amplitude. Paintable or Flood. |
| **Smooth** | Removes noise, damps sharp bends. **Retain Shape** toggle keeps the silhouette while cleaning the strand. |
| **Clone Stamp** | See §3.2. Shift+LMB sets origin, Ctrl+LMB rotates the stamp, drag previews, **`Enter` commits**. Also mirrors the entire groom across an axis. |
| **Wire-Pin** | Promotes a painted selection of strands into guide curves that then deform them. Two modes (Full, Deformer). Used for one bespoke flyaway *or* to harvest a curve set as input to clumping. |
| **Paint Attributes** | Density, strand width and field maps painted on a **paint mesh** — either a subdivided duplicate of the growth mesh, or a **root-position mesh with one vertex per strand root** (per-strand precision). Stroke reflection for symmetry. Recommended workflow is flood to 0 then paint hair *in*, not paint it out. |
| **Brush** | Sculpts strands along the growth surface — aimed at cleaning up root-level directional flow without touching the overall shape. |

**Field nodes** are the fast blockout alternative: draw curves on a live proxy surface, and they set
the angle at which hairs emerge across the whole surface. `wmWigFieldNodeShape` exposes Bend
Start/End/Angle, follicle angle, normal rotation, self rotation, normal-flow rotation — each with a
min/max randomizer *and* an optional painted map, with a Random Range weight to interpolate between
the map value and the random value. Wave/helix and strand length are also drivable from field maps.
Note the exclusion: field curves drive **either** the bend **or** the follicle angle, not both.

### 1.4 Clumping — a first-class subsystem, not a modifier

Clumps are built from a guide-curve set or from a `wmPelt` mesh. All hair binds to the nearest curve
by default; clumps live in **clump sets** which are colour-coded in the viewport and switchable by an
active-ID. Per set:

- **Shape** — Multiplier (how hard hairs are pulled to a straight line) plus **two clump profiles A
  and B** (position/value/interpolation ramps) with an **A/B ratio and seed**, so a set contains a
  statistical mix of two clump shapes rather than one.
- **Volume** — Compensation Magnitude/Length and Packing Magnitude/Length (how tightly bound to the
  curve, and length compensation for the chunkiness that causes).
- **Trim** — how overshooting hairs inside a clump are handled, with a trim ratio.
- **Strand deformation → Random** — fractal noise with Num Octaves, Octave Ratio, Root Period and
  separate **angular / radial / tangential** magnitudes (rotate around the clump curve, move toward
  or away from it, slide along it) plus Max Radial Overshoot, strands-affected %, and a strength ramp
  along the strand.
- **Strand deformation → Wave** — randomized wavelength and amplitude between min/max, mirroring,
  strands-affected %, adjust-strand-length, strength ramp.
- **Clump deformation → Twist** — up to 720°, sign = direction, with overshoot threshold, mirror,
  **mirror per strand**, randomize scale min/max, seed, strength ramp.
- **Clump deformation → Volume** — the same noise function applied to the clump's cross-section, with
  **Stretch Magnitude** (makes the profile elliptic rather than circular in places) and **Twist
  Magnitude**.

⚠️ **The gotcha, stated in the manual:** strand-level tool edits are overridden when clumps are
active, and any strand edits are discarded if the owning clump is later modified. Clumping is a late,
committing stage.

Supporting operations: Create Curves from Strands (random N curves at chosen CV count), Generate
Curves from Clumps, Create Clump from Curves / by Radius, Edit Clump Curve Radius (grow a clump's
catchment), Rebind Clump Curves, Freeze Clump Curve Transforms + Reset Strands Length to Clump Curve,
Randomize Clump Strand Length (min/max + effect ratio), Extract/Rebuild clump curves.

### 1.5 Coils and braids

- **Coil** — a helix model. Input curve is the *centre line*, output curve is the helix. Shape comes
  from **Natural Radius** and **Natural Pitch** on the curve, and the **Coil Manipulator** lets you
  click circles onto the curve and drag radius/pitch samples at arbitrary positions along it. Curls
  are then clumped from the coil output curves. Needs CVs/strand raised to ≥48.
- **Braid** — fully procedural on a driving curve; moving the curve moves the whole braid, so it is
  cheap to store and cheap to animate. Modelled as three components: the plait, edge **flyaways**, and
  the **end tuft**. Controls for strand width, overall size, plait direction, taper. The **Braid
  Manipulator** has two modes: **Radius** (click `+` to add a radius sample, drag to set local
  thickness, slide samples along the curve) and **Normals** (add a normal sample, drag the yellow ring
  to set local twist). Render mode switches between solid tube geometry ("strands") and actual
  hairs ("fibers"). Export via `wmExportBraidCurves` / `wmExportBraidFlyAwayGuides` /
  `wmExportBraidMeshes`. The `wmBraidCore` node is disposable — all input lives on the curves, so it
  can be deleted and reconstructed.

### 1.6 Selection and masking

Four mutually-exclusive methods, and the manual is explicit that you should use only one at a time:
**Strand Select tool** (paint a selection; strands select root-to-tip even if you only touch the tip;
stored in a `wmWigStrandSelect` node like a Maya set, with an Apply Selection toggle that scopes all
subsequent tools), **mask by face selection** on the growth mesh, **mask by surface intersection**
(any polygon mesh becomes a selection volume), and the `wmWigStrands` MEL command. Masks are session
state — not saved with the scene.

### 1.7 The animation side — the part Houdini has no equivalent for

All of it requires the groom to be **locked** first.

| Node | Substance |
|---|---|
| **Skinning nodes** | Linear blend skinning of strands, in three modes. **Curves** — NURBS drive strands (same result as guide-curve deformers, much faster); local deformation is read from the skin surface at the curve root, so roots must sit near the skin. **Surfaces** — strands wrap to meshes via the subd limit surface; thin ribbons emulate oriented curves, which is the *only* way to control twist. **Cages** — meshes drive strands by local **volume** deformation, so strands inside a closed cage respond correctly to compression/dilation; outside the cage they fall back to surface wrapping. Controls: Envelope (−2…2), deformation profile, **Cling Power** (how strongly wet strands are attracted to the nearest guide segment/face) and **Wetness Bias**. Degree controls how many curve segments drive each CV (default 2). |
| **Guide curve deformers** | Older/slower path with one extra capability: a **ramp mixing clump-force against guide-force along the strand** (default = clump at the root, guides at the tip), plus **expanded binding** — each strand looks within a radius for up to N *additional* guides applying a secondary force keyed to root or tip, and a matching expanded **smoothing** with its own radius/count/power/key. Deformers bind by snapshotting a bind pose; re-bind and fur-node retarget are explicit operations. |
| **Volume selectors** | Drop a mesh in the scene; strands intersecting it get one of four operations: **Root Disable**, **Root Enable**, **Make Wet**, **Make Flexible**. Wetness and flexibility ramp up with penetration depth to a set max. **Max wetness defaults to 0.85** — as it rises the hair damps and clings; at 0.85 it is fully wet/underwater and starts to *spread out again*. Wetness and flexibility are sim-only attributes, meaningless on a static groom. This is the water-line feature, exposed as a mesh plus a dropdown. |
| **Intersectors** | Geometry that clips strands at the contact point — CV count preserved, length clipped — so fur does not push through cloth. Four **cache modes**: Live Intersect Only, Live + Collect Cache, Apply Cache Only, Live + Apply Cache. Min/max clipped length, and filters for deforming vs non-deforming and re-rootable vs not. |

### 1.8 Transferring a groom

Three distinct operations, worth separating because they are the same machinery at different strictness:

- **Merge Fur** — target selected first. Works across **different topology and UVs**. The source
  strands are *not* added; the existing target strands are reshaped to resemble the nearest source
  strands, and **root positions never move**. Only enabled strands are modified; it can remove hairs
  (density scale → 0) but cannot bring disabled ones back. Options cover interpolation when the
  target is denser than the source (Max Neighbor Strands = 1 short-circuits it when it isn't).
- **Emulate Fur** — same transfer but retains all source attributes and offers no options.
- **Vert Copy by UV** — swap the growth mesh under a finished groom when topology and UVs are
  unchanged. The change is scrubbable on a `Wm Vert Copy Drv1` channel, like a blendshape.

### 1.9 Feathers — Apteryx

Separate tool, named for the kiwi genus, built during *Kingdom of the Planet of the Apes*. Workflow:
procedural generation → hand sculpt → groom. Reported history is instructive: it was not
production-ready when the eagles were first built, so the older plumage tools were used, and the
birds were **re-groomed at the end of the show** once Apteryx was rich enough. Only surface detail is
public — no manual exists.

---

## 2. Disney: Tonic + iGroom + Disney's XGen

### 2.1 Tonic — volumes, not curves

Built on *Frozen*, in-house, still current (used through *Wish*, 2023).

**The scalp graph.** The artist draws a **2D graph on the 3D scalp surface**. Each closed region of
that graph is the root footprint of one lock of hair. Graph nodes can be added, removed and dragged
across the surface *at any point during grooming* — that editability is the stated reason art
direction changes don't force a restart. Three hard requirements the tool exists to enforce: full
scalp coverage (no bald spots), no root-level intersections, and sufficient smoothness.

**The tube.** Each region automatically gets a clump volume represented as a **single centre curve
plus a series of orthogonal planar cross-sections**. Both the centre curve and the cross-sections are
directly manipulable by control vertex — this is the sculpting surface.

**Population.** Tonic fills each tube with guide curves at a prescribed density, reflecting both the
centre curve's profile and the tube's shape/extent. Elsa's numbers, end to end:

```
~50 Tonic tubes → ~1,000 guide curves → ~120 sim curves → ~400,000 rendered hairs
```

Detail (noise, curl, clumping) is added to the guides in Disney's XGen, which also does the render-
time interpolation. The Tonic volumes double as a **visual proxy for the simulation department** —
they show the space the simulated hair should occupy.

### 2.2 The hierarchy — the crown jewel

From the 2018 talk (Kaur, Simmons, Whited). Artists always worked coarse-to-fine, subdividing large
clumps into smaller ones. The change was to make that hierarchy **explicit, persistent and
first-class**: clumps produced by subdivision are permanently parented to the coarse clump they came
from, and that structure is handed to every downstream department.

Three things it buys:

1. **A hierarchical, length-preserving deformation algorithm.** Thick parent curves act as control
   curves; children keep their own length and their local structure relative to the parent. Deforming
   thousands of curves was the stated bottleneck of their Maya hair pipeline, and generic curve
   deformers could not hit the shapes while keeping curves valid as *simulation inputs* (length and
   volume must survive).
2. **Pre-sim goal shapes and post-sim sculpting from the same interface.** Pre-sim: pose target
   shapes that the sim is goaled toward. Post-sim: re-sculpt the sim output at whatever hierarchy
   level restores the silhouette. Parent control curves for post-sim work are **constructed
   recursively bottom-up by averaging the simulation output curves** — so the hierarchy exists even
   on data that came out of a solver.
3. **On-the-fly hierarchy.** In shot work an artist selects any subset of curves and a parent control
   curve is **generated procedurally** — transient for a single edit, or made persistent for a
   shot/sequence. Production result: on *Ralph Breaks the Internet* this made multi-resolution editing
   implicitly available for **all 772 characters with hair rigs**, whether or not their groom shipped
   a hierarchy. Depth is not fixed — a documented loose-structure groom used **seven levels**.

First used on *Moana* (3 main characters), then *Ralph 2* broadly.

### 2.3 iGroom and Disney's XGen

- **XGen** — procedural geometry instancer, expression-based operators plus grooming tools.
  Originated at Disney and was licensed to Autodesk; **Disney kept its own branch** ("Disney's
  XGen"), so studio talks referring to XGen are not describing the shipping Maya feature.
- **iGroom** — interactive **brush-based** tool inside XGen. It produces the *maps* that drive
  procedural fur generation: combing, cowlick patterns, roughness, clumping. Revived from an older
  Disney tool for *Zootopia*.

The split in practice: **Tonic for sculpted locks** (bangs, ponytails, braids — anywhere creative
control matters), **iGroom for coats** (short fur, whole-body). *Strange World* is the explicit case
where neither fit: too many clumps to tube by hand, too much shape control for iGroom's maps.

### 2.4 Where Houdini already crept into Disney's pipeline

**Legend, *Strange World* (2023).** Standard pipeline is Tonic → guide curves + region maps → Disney's
XGen. For this dog they **replaced Tonic with Houdini** for that stage:

- Guides laid down with **GroomBear** — a $59 Gumroad Houdini grooming toolkit (brushes: mask, comb,
  force, shape, scatter, draw, move, copy, cut, lift, rotate, smooth, scale, clump, paint, swirl;
  radial menu; Cards node converts guides to planes/feathers/tubes).
- A **custom Houdini node generating the region maps using geodesic distance**, not Euclidean —
  called out as crucial for thin, close areas like ears and lips.
- Output shaped to match Tonic's, so Disney's XGen and everything downstream saw no difference.
- iGroom still used for the short fur around face, mouth and eyes; a second iGroom description added
  an **undercoat** in high squash-and-stretch areas to hide gaps in motion.
- Two workflow notes: guide density had to be raised locally where regions wrap high-curvature areas
  or interpolation breaks; and the groom is authored in a neutral pose, so a **sim pass to drop the
  ears under gravity** was needed before grooming issues there could even be seen.

**Asha's braids, *Wish* (2024).** Tonic sculpted the structure (level 1 = regions, level 2 = one tube
per braid defining length and flow), then the braid tube centre curves were **exported to Houdini**
for a custom **SOP network**:

- Per-strand width as a percentage of overall braid width; **knot frequency** plus an amount to vary
  frequency by width; a **ramp for width along the braid's length**.
- Braid knots generated from **sine waves with offsets**.
- Global noise frequency with per-braid offset controls; the network copies per braid group with
  unique settings, then merges.
- A separate network purely to **visualise the result while editing**.
- **Vellum** used to fix intra-braid strand collisions — by running the sim while *animating the braid
  width up over a few frames*.
- Volume-profile meshes swept from a circular profile down each braided strand, imported back into
  Tonic as **level-3 hierarchy tubes**, so the hierarchy then controlled both individual strands and
  the braid as a whole.

Cost: the resulting Tonic groom was **two orders of magnitude more complex than average — over 500K
tube vertices**, requiring a **60× optimization** of interactive drawing and selection to stay usable.
Sim ran each of the 80 box braids as a single centre curve with circular collision widths.

### 2.5 Sim-side artist features worth stealing

- **Gravity preloading** (2022, first on *Raya*, now in most hair rigs). Grooms are modelled without
  physics, so gravity pulls them off-design the moment you simulate. This solves for the **rest shape
  that settles into the modelled shape**, treating the simulator as a closed box (no knowledge of the
  material model needed — it approximates ∂x/∂X with the deformation gradient and ramps the external
  force over ~100 steps). Artist control is **a per-vertex map, required to be monotonically
  increasing root→tip**, saying how much gravity to compensate where. Practical note from the paper:
  full compensation makes hair energetic and bouncy, so production used *partial* preloading plus
  layer collisions. Cost is trivial — 10,034 vertices in 5.2 s on 24 cores, run once per rig build.
- **Initial-pose dials.** Asha's rig shipped **four** draped start poses with continuous blending
  between them, picked per shot by camera angle and continuity with neighbouring shots.
- **Choreography system, *Moana 2* (2025).** Performances categorised on two axes — *environment
  interaction* (underwater, storm/wind from breeze to hurricane, terrain contact) × *character
  behaviour and emotion* (despair, playfulness, determination, musical-number sync), each with 4–5
  sub-categories. Rig **variants** per condition (underwater/windy/wet/dry), tuned per sub-category.
  **Wind tags** set sim parameters at *sequence* level and can be shared across sequences. Per-
  character force dials (e.g. how much Moana's hair stays back off her face). Casting groups similar
  shots to one artist; reviews happen at sequence rather than shot level. Scale: 1,668 shots, Moana in
  1,000+, 500+ with wind, 71 damp/drenched/underwater hair shots for Moana and 64 for Maui.
- **Interleaved animation and simulation, *Tangled* (2011)** — still the underlying philosophy. Shots
  triaged into **passive** (batch-simmed with a default setup), **animation-driven**, and
  **simulation-driven**. The hair rig has IK, FK, twist and pinch at global *and* sub-group level,
  with **ten break-up controls** pulling sub-groups out of the main volume, and per-shot control
  counts. Rig-animated shots then get a sim layer targeted toward the animated curves; sim-driven
  shots get post-sim rig/deformer manipulation riding along with the simulated hairs so shapes can be
  edited **without re-running the sim**. ~500 art-directed hair shots.
- **XGen LOD + a wedging tool, *Zootopia* (2016).** Pruning switched from stochastic culling to simply
  *emitting fewer primitives per face* (kills patchiness; up to 99% cull), dynamic **CV reduction** per
  primitive on top, auto-computed near/far pixel widths from a chosen camera, optional intermediate
  waypoints, per-shot overrides, and an automated **render-wedge tool** that renders the character at
  4 canonical distances with time/memory/primitive-count stats burned into the images. Numbers: sheep
  2.47 GB → 0.062 GB, render 296 s → 45 s.
- **Drawovers as the actual specification.** 2D hand-drawn overlays on animation are the deliverable
  that defines hair performance — consistently, from *Tangled* (2011) through *Wish* and *Moana 2*
  (used at both sequence and shot level). This is a workflow, not a feature, and it is arguably the
  most-repeated finding in the whole Disney literature.

---

## 3. The five gaps — what Houdini does not have

Ranked by value. #1 and #2 are the ones worth building; 3–5 are small.

### 3.1 ⭐ Volume/tube sculpting with a persistent hierarchy and a length-preserving deformer

**What it is.** A groom whose editable representation is a tree of tubes (centre curve + oriented
cross-sections), where every curve knows its parent, and where a deformer lets you grab a coarse
parent and re-pose everything below it *without changing any child's length or local structure*.
Usable pre-sim (as goal shapes) and post-sim (to restore a silhouette the solver flattened).

**Why Houdini has no analogue.** Guide Groom SOPs brush guides, and Guide Deform drives hair from
guides — but there is no persistent multi-level parent/child structure carried on the curves, no
coarse-control-curve editing at an arbitrary level, and no length-preserving hierarchical deformation.
Post-sim, you are back to generic curve deformers, which is exactly the situation Disney describes as
their bottleneck.

**Design sketch** (⚠️ untested — this is my construction, not a documented Disney implementation):

| Piece | Approach |
|---|---|
| Data model | Curve prims with `level` (int) and `parent` (int/prim id) attributes. Tube = centre curve + per-CV cross-section (radius + up-vector, or an explicit profile prim). Everything travels as ordinary geometry, so it survives the whole SOP chain. |
| Scalp regions | Draw curves on the scalp (curve-on-surface / topo transform); close them into regions. Region influence maps computed by **geodesic** distance, per *Strange World* — `Find Shortest Path` SOP or a `Measure`-based flood, **not** point-cloud Euclidean. Ears and lips are where this shows. |
| Population | Scatter roots in the region; sweep the cross-sections along the centre curve to get the volume; place guides by interpolating cross-sections along the parameter. |
| Bind | For each child CV, store its parent arc-length parameter *plus* its offset expressed in the parent's local frame (parallel-transport frames, not Frenet — Frenet flips). Store child segment lengths. |
| Deform | On parent edit: rebuild the parent's frame field, place each child CV at (new arc param, same local offset), then **re-integrate the child from the root using the stored segment lengths** so length is preserved exactly. VEX first, OpenCL if it needs to be interactive. |
| Subdivide | Split a clump into N children, parent them, resample. Persistent. |
| **On-the-fly hierarchy** | Select any curve set → generate a parent by resampling to a common CV count and averaging → deform → push back. **Build this first.** It is a fraction of the work, it is exactly what Disney says made hierarchy available to all 772 characters, and it works on sim output with no groom-side hierarchy at all. |

**Effort:** the on-the-fly variant is days. The full persistent tube-hierarchy authoring tool is a
project — Disney had to spend a 60× interactivity optimization to make it hold 500K tube vertices.

### 3.2 ⭐ Full-density direct manipulation, clone stamp and mirror

**What it is.** Brushing the *final* hairs rather than guides, plus a Photoshop clone stamp that
copies groom shape from one patch of the body to another (with rotation), the same operation mirrored
across an axis, and the same operation across two different meshes (Merge/Emulate).

**The key insight** (🧮 my reading, not stated as such by Wētā — but it is consistent with the manual's
description of Merge): **clone stamp, axis mirror, merge fur and emulate fur are one operator**. All
four are *shape transfer by nearest-strand correspondence in a local frame*, differing only in how the
source and destination frames are defined:

| Operation | Source frame | Destination frame |
|---|---|---|
| Clone stamp | brush disc at origin point, optional rotation | brush disc under cursor |
| Mirror | reflected copy of the groom | itself, handedness flipped |
| Merge / Emulate | a different fur node, possibly different topology/UVs | this fur node |

Mechanism in each case: build a tangent frame at the surface point (normal + reference direction),
express each source strand as (2D offset within the patch, shape in local frame), then for each
destination strand find the nearest source strand by offset and write the shape into the destination
frame. Root positions never move. Disabled strands are not resurrected.

**What it needs in Houdini:**

- **Density.** Wētā's model is effectively "guides *are* the final hairs" — so the semantic change is
  just running the existing brush tools at 100k+ curves. The blocker is interactivity, not concept:
  OpenCL brush kernels and a viewport representation that doesn't collapse. This is squarely in
  known-good territory here (studio hair procedurals, HDK, OpenCL).
- **Commit semantics.** Houdini brushes apply incrementally; the clone stamp needs a *preview then
  commit* model (Wig previews under the brush and applies on `Enter`). That is a real UI behaviour to
  design, not a parameter.
- **Frames.** Same parallel-transport frame machinery as §3.1 — build it once, both features use it.

**Effort:** the clone/mirror/merge operator itself is small once the frame + nearest-strand
correspondence exists. Making full density *interactive* is the expensive half.

### 3.3 Wetness and flexibility as a spatial volume query

Drop a mesh, and strands intersecting it ramp wetness/flexibility with penetration depth (max 0.85 →
past that it reads as underwater and spreads again), plus root enable/disable. A weekend in Houdini:
SDF from the volume mesh, sample per CV, write attributes the solver and the shader already read. The
0.85 spread-again detail is the part that makes it look right and is the part nobody guesses.

### 3.4 Cage-mode skinning

Strands driven by the **volume** deformation of a closed cage mesh rather than its surface, so fur
inside a compressing cage behaves correctly; outside the cage it falls back to surface wrap. Also
worth taking: the ribbon trick — thin ribbon control surfaces to get twist control that pure curve
control cannot give.

### 3.5 Intersector clipping with frame caching

Geometry that clips strand length at the contact point (CV count preserved) so fur doesn't push
through cloth, with four cache modes (live only / live+collect / cache only / live+apply) and min/max
clipped length. Small, and it kills the single most common fur artifact.

---

## 4. Comparison at a glance

| | Houdini | Wētā (Wig/Barbershop) | Disney (Tonic/XGen) |
|---|---|---|---|
| Editable unit | guides → interpolated hairs | **every final hair** | **tube volumes** → guides → hairs |
| History | full procedural DAG | **none** (commits, Photoshop-like) | procedural downstream of a sculpted hierarchy |
| Structure carried to sim | clumps/guides | clump detection ("groom-aware") | **persistent parent/child hierarchy** |
| Post-sim reshaping | generic curve deformers | deformers/skinning nodes | **hierarchical length-preserving sculpt** |
| Groom transfer | attribute transfer, manual | Merge / Emulate / Vert-Copy-by-UV | XGen descriptions, region maps |
| Wet / underwater | manual attribute plumbing | **volume selector, 4 operations** | rig variants per condition |
| Fur-through-cloth | manual | **intersectors + caching** | (not documented) |
| Braids | manual / Vellum | **procedural braid on a curve + manipulator** | custom Houdini SOP → Tonic tubes |
| Curls | clump/curl SOPs | **coil helix node + on-curve manipulator** | Disney Elastic Rods (twist), Multicurve |
| Art-direction spec | — | — | **2D drawovers, sequence + shot level** |

---

## 5. Evidence tiers

### ✅ Verified — read from the primary source

- Every Wig tool, node, attribute and default in §1.2–§1.8 — read from the live Unity Wig manual
  (~110 pages pulled and converted to text, 2026-08-15).
- Elsa's 50 → 1,000 → 120 → 400,000 pipeline; the scalp graph; the three tube requirements (§2.1) —
  from the Disney/Eurographics 2014 PDF.
- The hierarchy, the length-preserving deformer, on-the-fly hierarchy, 7 levels, 772 characters
  (§2.2) — from the SIGGRAPH 2018 talk PDF.
- The Houdini braid SOP network, 500K tube vertices, 60× optimization, 80 braids, 4 initial poses
  (§2.4) — from the SIGGRAPH 2024 talk PDF.
- GroomBear, geodesic region maps, undercoat, ear-drop sim pass (§2.4) — from the SIGGRAPH 2023 talk PDF.
- Gravity preloading algorithm, monotonic map, 5.2 s / 10,034 verts, *Raya* origin (§2.5) — from the
  SIGGRAPH 2022 talk PDF.
- *Moana 2* categorisation axes, wind tags, force dial, all shot counts (§2.5) — SIGGRAPH 2025 talk PDF.
- *Tangled* triage, ten break-up controls, ~500 shots (§2.5) — SIGGRAPH 2011 talk PDF.
- Zootopia LOD numbers and wedge tool (§2.5) — SIGGRAPH 2016 talk PDF.

### 🧮 Computed — my derivation, not stated by the source

- **§3.2's central claim** that clone stamp, mirror, merge and emulate are one operator. Consistent
  with the manual's description of Merge (existing target strands reshaped toward nearest source
  strands, roots unmoved) but nowhere stated as a unification.
- The entire §3.1 design sketch — parallel-transport frames, bind representation, re-integration for
  length preservation. Disney publishes *that* they have a hierarchical length-preserving algorithm,
  not how it works.
- The Houdini-gap ranking in §3 and the comparison table in §4.

### 📄 Snippet-level — read from secondary sources, not primary

- Barbershop's paradigm statements and the Revelant quote — fxguide's 2015 Sci-Tech article.
- *Kingdom of the Planet of the Apes* fur numbers (95 grooms) and Apteryx — trade press, not a paper.
- iGroom's description — Disney's own tech page plus fxguide's Zootopia article. **No Disney paper on
  iGroom was found.**
- Unity's acquisition/wind-down timeline — trade press; the "Unity retained the IP, Wētā FX retained
  access" arrangement is *reported*, not confirmed from a primary document.

### ⚠️ Known gaps — do not assume

- ⚠️ **Nothing here was run.** No Wig install exists to test against; the docs describe behaviour that
  was never exercised. Every "it works like X" is documentation, not observation.
- ⚠️ **Tonic has no public manual.** §2.1–§2.2 are reconstructed from four 2-page talks. The actual
  UI, hotkeys, and the shape of the tube-editing interaction are unknown.
- ⚠️ **Barbershop ≠ Wig is unresolved.** Wētā calls Wig the latest generation of the same lineage;
  *Kingdom* (2024) is described as using "a new version of Barbershop". Whether these are one codebase
  under two names, or a successor and a maintained original, is not established.
- **Wig availability is unclear.** The division closed; the docs are still hosted. Whether the product
  can be licensed today was not determined — no 2025/2026 source found either way.
- **No effort estimate is grounded.** The "days / weekend / project" figures in §3 are judgement, not
  measured against a prototype.
- **Disney's XGen ≠ Autodesk XGen.** Anything read about Maya's XGen does not transfer to the studio
  talks without checking.

---

## 6. Sources

**Wētā**
- Wig manual (primary source for §1) — <https://docs.unity3d.com/wig-docs/manual/index.html>
- Wig, Wētā FX — <https://www.wetafx.co.nz/research-and-tech/technology/wig>
- Barbershop at Wētā, Sci-Tech winner explained (fxguide) — <https://www.fxguide.com/fxfeatured/barbershop-at-weta-sci-tech-winner-explained/>
- Unity walks away from the Wētā deal (fxguide) — <https://www.fxguide.com/quicktakes/unity-software-with-a-company-reset-walks-away-from-film-vfx-and-the-weta-deal/>
- Unity ends Wētā FX services agreement (CG Channel) — <https://www.cgchannel.com/2023/11/unity-ends-services-agreement-with-weta-fx-265-staff-laid-off/>
- *Kingdom of the Planet of the Apes* VFX (Variety) — <https://variety.com/2024/artisans/artists/kingdom-of-the-planet-of-the-apes-weta-fx-erik-winquist-1236202166/>
- SIGGRAPH 2020 studio fur/hair roundup (also covers MPC Furtility, Framestore Fibre, DNEG Furball) — <https://www.animationxpress.com/vfx/siggraph2020-how-leading-studios-furnish-their-characters-with-fur-and-hair/>

**Disney**
- Tonic — <https://disneyanimation.com/technology/tonic/>
- Fur Grooming / iGroom — <https://disneyanimation.com/technology/fur-grooming/>
- Disney's Hair Pipeline: Crafting Hair Styles From Design to Motion (2014) — <https://media.disneyanimation.com/uploads/production/publication_asset/121/asset/hairPipeline.pdf>
- Hierarchical Controls for Art-Directed Hair at Disney (2018) — <https://media.disneyanimation.com/uploads/production/publication_asset/175/asset/a13-kaur.pdf>
- Art Directing Asha's Braids in Disney's *Wish* (2024) — <https://cdn.disneyanimation.com/uploads/publications/WishAshaHair_sig2024_talk.pdf>
- Creating the Art-Directed Groom for Legend in *Strange World* (2023) — <https://cdn.disneyanimation.com/uploads/publications/creating-the-art-directed-groom-for-legend-in-disneys-strange-world/SIGGRAPH_2023_Grooming_Legend3.pdf>
- Gravity Preloading for Maintaining Hair Shape (2022) — <https://cdn.disneyanimation.com/uploads/Gravity+Preloading+for+Maintaining+Hair+Shape+Using+the+Simulator+as+a+Closed-box+Function.pdf>
- Choreography of Hair and Cloth in *Moana 2* (2025) — <https://cdn.disneyanimation.com/uploads/publications/SIGGRAPH2025_ChoreographyofHairandCloth.pdf>
- The Art and Technology of Simulating Hair in *Moana* (2017) — <https://media.disneyanimation.com/uploads/production/publication_asset/167/asset/moanaHair_abstract1.pdf>
- Directing Hair Motion on *Tangled* (2011) — <https://media.disneyanimation.com/uploads/production/publication_asset/8/asset/artDirectHair11.pdf>
- Artist Friendly Level-of-Detail in a Fur-filled World, *Zootopia* (2016) — <https://media.disneyanimation.com/uploads/production/publication_asset/137/asset/lod_paper.pdf>
- The fur-reaching tech of *Zootopia* (fxguide) — <https://www.fxguide.com/fxfeatured/the-fur-reaching-tech-of-zootopia/>
- Full publication index (filter for hair/groom/fur) — <https://disneyanimation.com/publications/>

**Houdini-side**
- GroomBear — <https://kwac.gumroad.com/l/groombear> · <https://www.sidefx.com/gallery/groombear-grooming-toolkit/>

**Reproducing the Wig manual pull**

The manual's nav is JS-driven, but DocFX exposes a flat TOC. Fetch
`https://docs.unity3d.com/wig-docs/manual/toc.html`, take every `href`, then request each
`manual/<page>.html` and strip to the `<article id="_content">` body.
