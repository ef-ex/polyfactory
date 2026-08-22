# polyfactory conventions — attribute naming and node hygiene

**Status:** project law, adopted 2026-08-22 (Hannes). Binding on every polyfactory tool.
**This file owns:** the *data* conventions — what attributes are called and what must not escape
a node. It is the data-side sibling of [`artist_ui.md`](artist_ui.md) §6, which owns the
*parameter surface* and is binding the same way.
**Why a new file:** neither `artist_ui.md` (UI) nor `citygen.md` (citygen's own contracts) owns
suite-wide data naming, and the rule applies to every tool including the parked ones.

---

## 0. Status — DONE vs PENDING, so the next reader starts from truth

**DONE** (measured, and each one has a check behind it unless marked):

* §2 the `_*` law, on all four attribute classes, in every SOP that can produce scaffolding.
  Two waves: **12 leaked names out of 7 assets** in wave 1, and in wave 2 **5 more out of 2**
  — `pf::prepare_mesh`'s `__scalefactor` and `__scaleX/Y/Z` (a shipped asset whose cleanup node
  had never run, on a menu branch nothing ever cooked) and the `splitPathGroup` that
  `PF::split_poly` handed `pf::prim_cross`. Wave 2 also moved **8 internal names** that were
  not leaking but were spelled wrong: `p1`…`p4` → `_p1`…`_p4`, and the four `pf_temp*` /
  `pf_split*` working names of §6.
* §5 groups, with a reference implementation in five assets, and the §6 `pf_temp*` debt paid.
* §7 enforcement: **236 parameter branches** swept, both halves of the check set the exit
  status, non-SOP definitions named as out of scope. Mutation-tested — a `_temp` in two
  different HDAs, a branch-only leak, and an UNPREFIXED leak all go red.
* §8 parm-default renames (`pf_enum`, `pf_axis_mask`, `pf_bomber_dir`, `pf_toposelect`),
  including the Help text and the hard-coded fallbacks that the first wave left behind.

**PENDING, and Hannes decides:** everything in §9 — `pf::pf_asset_tag` (9a), the CityGen field
contract (9b), CityGen streets V1 (9c), `pf::primneighbouredge` (9d), and dropping
`pf::ramp_tube`'s compatibility copy (9e, the cheapest and the only one already half-done).
**None of §9 is started.** `pf::ramp_tube` is the one asset where a breaking rename was
executed before it was planned; it now dual-writes both spellings so no saved scene is broken,
and finishing it is 9e.

## 1. Every attribute that leaves a node is prefixed `pf_`

Hannes: *"i did want to prefix every attribute with pf_ but i never implemented it."* Now it is
law. The reason is collision on shared streams: polyfactory geometry travels through other
people's networks, other vendors' assets and other polyfactory tools, and an unprefixed `enum`,
`id` or `width` will eventually meet another one.

**Flat prefix, descriptive name — not stacked prefixes.** `pf_elem_id`, not `pf_pc_elem_id`.
Namespacing comes from the *name*, not from more prefixes:

| Kind | Form | Example |
|---|---|---|
| Suite-wide contract (deliberately shared between tools) | `pf_<thing>` | `pf_elem_id`, `pf_enum` |
| Tool-specific | `pf_<domain><thing>` | `pf_street_class`, `pf_stitch`, `pf_bay_index` |

Sharing a name is a **feature** where the contract is genuinely shared — citygen buildings and
polyChain both want element identity, and they should spell it the same way. Sharing a name by
accident is the failure this rule prevents.

⚠️ **`pf_` is for what LEAVES the node.** Inside a node, see §2.

## 2. Internal attributes start with `_` and must not survive the output

The SideFX practice Hannes asked for: an attribute that exists only to get from one internal node
to the next is named `_something` and is **deleted before the output**. Two reasons, and the
second is the important one:

1. It is self-documenting — a reader knows instantly whether an attribute is contract or scaffolding.
2. **It makes the guarantee checkable.** A single delete of `_*` before the output node, plus one
   test asserting no attribute beginning with `_` appears on any output, means nothing leaks by
   accident. Leaked scaffolding is otherwise found months later, by someone else, in a scene that
   already shipped.

**Required of every polyfactory HDA:**
- internal-only attributes are named `_*` (any class: point, prim, vertex, detail);
- a delete of `_*` sits immediately before the output, on **all four classes** — not a
  literal list of names, and not one class of the four;
- a test asserts the output carries no `_*` attribute — the rule is worth nothing unenforced.

⚠️ **A literal delete list is not a weaker version of this rule, it is a different rule that
fails.** `pf::prepare_mesh`'s cleanup node named `__scalefactor __scaleX __scaleY __scaleZ`
explicitly — in the POINT class, while the wrangles wrote them as DETAIL — so it had never
removed anything, and all four rode out of a shipped asset through a survey, a migration and a
review pass. The wildcard cannot rot that way.

**The wildcard's collateral is deliberate.** `attribdelete _*` on a pass-through stream also
removes `_*` names that arrived from UPSTREAM and were never ours. Measured, not reasoned
about: a point `_vendor_pt`, a prim `_vendor_prim`, a detail `__vendor_detail` and a point
group `_vendor_group` fed through every asset in the suite are destroyed by the ones that
sweep and survive the ones that do not. We keep it, for two reasons: `_` means *scaffolding*
under the same SideFX convention this rule is borrowed from, so a node whose contract is
"no scaffolding leaves" may strip the scaffolding it is handed; and the alternative is the
literal list above. `tests/hda/run_attrib_checks.py` records which asset strips what under its
`upstream/` keys, so it is a diff a human reads rather than a surprise found in someone
else's scene.

## 3. Migration — new code now, existing tools when next touched

A big-bang rename across the suite would touch citygen streets V1, which is **shipped, has a
documented attribute schema** ([`citygen_streets.md`](citygen_streets.md) §, `edge_id`,
`street_class`, `node_id`…) **and baselined regression checks**, while polyChain is mid-rebuild.
That is a lot of breakage bought for no new capability, at the worst possible moment.

So:
1. **New code follows this document immediately.** No exceptions.
2. **polyChain** renames `pc_*` → `pf_*` as its own dedicated pass, **after** the §12 native
   rebuild reaches parity — not before. Technical reason, not caution: parity is asserted by
   comparing the network's output against the Python reference, and renaming one side mid-comparison
   destroys the very check that proves the rebuild correct. The `_*` rule (§2) is adopted
   **immediately** in the rebuild, since it is creating new internal attributes right now.
3. **Every other tool** migrates when it is next opened for other work. Record the migration in
   that tool's own doc.
4. `pf::merge_enum`'s `enum` becomes `pf_enum` — its `enum_attr` parameter already makes this a
   default change, not a breaking one. See [`polychain.md`](polychain.md) §3.2b for why that value
   is prototype identity and must never be used as element identity.

## 4. What this does not change

Houdini's own reserved attributes (`P`, `N`, `Cd`, `pscale`, `orient`, `up`, `v`, `id`, `name`,
`path`, packed-prim intrinsics) keep their names — they are Houdini's contract, not ours.
Never prefix those, never shadow them.

**The reserved set is bigger than Houdini's own attribute list, and this was measured, not
assumed.** A name that is a NATIVE NODE'S PARAMETER DEFAULT is also not ours to rename — we did
not choose it, an artist reading that node's help expects it, and renaming one member of a set
breaks the set. Probed live in H22.0.398:

| Name | Whose default it is |
|---|---|
| `out`, `up`, `N` | `orientalongcurve`'s `xaxisname` / `yaxisname` / `zaxisname` |
| `splitPathGroup` | `polysplit::2.0`'s `groupname` |
| `restlength` | `convertline`'s `lengthname` |
| `class` | `connectivity`'s `attribname` |
| `curveu`, `tangentu`, `ptdist`, `curvenum`, `ptrow`, `ptcol`, `primrow`, `primcol`, `crossnum`, `roll`, `yaw`, `pitch`, `start_up`, `end_up`, `endcaps` | the `sweep` / `resample` vocabulary, which `pf::ramp_sweep` exposes on 18 parameters and which therefore needs **zero** changes |
| `gl_lit` | the viewport's own convention |

This is why `pf::curve_vector`'s point `out` was left alone: it is one third of an
`out` / `up` / `N` frame whose other two thirds are reserved outright.

⚠️ **The exception is a native default that LEAKS.** `restlength` and `class` are Houdini's
spellings, but inside `pf_citygen_segmenter` they were by-products nobody read that rode onto the
shipped city mesh. There the answer is §2 — rename `_*` on the node parameter, delete before the
output — not §1. Reserved means *do not rebrand it as ours*; it never means *let it ship*.

## 5. Groups obey both rules, exactly as attributes do

A working group leaks the same way an attribute does, and a group-name collision between two
stages has already silently corrupted one of them in this codebase (`tests/citygen/checks.py`,
`no_scratch_groups`). So: a group that leaves a node is `pf_*`; a group that exists only to get
from one internal node to the next is `_*` and is deleted before the output; and
`tests/hda/run_attrib_checks.py` asserts both classes together.

**Done, with a reference implementation.** A `groupdelete` of `_*` now sits beside the
attribute sweep in the five assets that can produce a `_*` group: `PF::split_poly` (its
internal `polysplit::2.0` group was `splitPathGroup`, Houdini's own default — §4's LEAKING
exception, so it is `_split_path` now, not `pf_split_path`), `pf::prim_cross` (which is where
that group actually shipped), `pf::polysplit`, `pf::group_by_topology` and
`pf::prepare_mesh`. An asset that creates no `_*` group of its own does not carry the node;
the test asserts the rule on every asset regardless, so the first one that does will fail with
a pattern to copy sitting next door.

The `pf_temp*` debt of §6 is paid: `pf_tempgroup` → `_topogroup` (`pf::group_by_topology`),
`pf_tempsplit` → `_split` and, in the same node, `pf_splitEdges` / `pf_splitPoints` →
`_split_edges` / `_split_points` (`pf::polysplit`).

## 6. `_*` and `__*` are the same rule — do not add a third spelling

Four tools already wrote `__bankratio`, `__scaleX`, `__library`; two wrote `pf_temp*`. `__*` is a
strict subset of `_*`: one attribute-delete pattern of `_*` removes both, and one test asserting
"no output name begins with `_`" catches both. So the law is **one leading underscore, minimum**;
`__` is allowed where it already exists; and `pf_temp*` is not a spelling of this rule at all — it
says `pf_`, which §1 reserves for what SHIPS. The `pf_temp*` renames are **done** (§5).

## 7. Enforcement — `tests/hda/run_attrib_checks.py`

    hython tests/hda/run_attrib_checks.py
    hython tests/hda/run_attrib_checks.py --update-baseline

Three checks, and only the first is about `_`:

1. **The law.** No output of any polyfactory HDA carries an attribute or group beginning with `_`.
2. **The snapshot.** Every published name is recorded in `tests/hda/baseline.json` and diffed, so a
   new attribute on an output is a diff a human has to look at.
3. **The collateral.** What an upstream `_*` name survives, per asset, under the `upstream/`
   keys — §2's stated cost, recorded so a change to it is also a diff.

**Both of the first two set the exit status**, and that had to be fixed: the snapshot used to
print its diff and return 0, so an injected `i@junkleak` — the exact shape of all twelve original
leaks — reported *"0 failing checks"* and exited green. `--update-baseline` is the sanctioned way
to accept a deliberate move.

**Why both.** Run against the pre-migration HDAs, check 1 reports **zero failures** — `psplit`,
`origP`, `scaleX/Y/Z`, `scalefactor`, `class`, `keep_component`, `restlength` and `verts` were all
leaks, and not one of them was spelled `_*`. The law only catches leakage honest enough to declare
itself; only the snapshot catches the rest.

**Every asset is cooked at defaults AND once per non-default value of every toggle and menu it
exposes** — 236 parameter branches over 33 SOP assets, ~23 s. This replaced a hand-written
`BRANCHES` dict holding ONE entry, and it is not a nicety: `verts`, `scalefactor` and
`__scalefactor` were all invisible at default parameters. The sweep is what finds
`pf::prepare_mesh` on the first run, and restoring that asset's pre-fix definition is the
standing proof that it does (`[FAIL] pf::prepare_mesh::1.0  detail.__scaleX … __scalefactor`).

The runner prints an **UNPROVEN** block — assets that do not cook, cook empty, or cook only their
pass-through branch (`pf::geoimporter`, `pf::pf_asset_place`, `pf::pf_kitbash`), **plus every
definition in `otls/` that is not a SOP**. That last part was missing: the runner enumerated
`hou.sopNodeTypeCategory()` only, so 19 of the 53 definitions — 9 Vop, 8 Cop, 2 Lop, including
`pf::texture_bombing`, which this migration edited — were neither checked nor mentioned, and the
headline read as if they were covered. They are out of scope (no geometry output; their attribute
names live in parm defaults and wired VOP inputs), but out of scope is a thing you say, not a
thing you omit. *"We could not make it leak"* is not *"it does not leak"*.

## 8. Migration log — what has already moved

| Tool | Was | Is | Kind |
|---|---|---|---|
| `PF::split_poly` | detail `psplit` | `_psplit`, deleted; display/render moved to `OUT` so the delete that already existed finally runs | leak |
| `efex::normalizemesh` | point `origP`, detail `scaleX/Y/Z` | `_orig_p`, `_scale_x/y/z`, deleted | leak |
| `efex::scale_to_one` | detail `scalefactor` | `_scale_factor`, deleted | leak |
| `pf::mesh_view` | detail `scalefactor` | `_scale_factor`, deleted | leak |
| `pf::group_by_topology` | point `verts` | removed — it was a dead write | leak |
| `pf::connectivity_plus` | prim `class` | `_class`, deleted | leak |
| `pf_citygen_segmenter` | prim `class`, `keep_component`, `restlength` | `_class`, `_keep_component`, `_restlength`, deleted — all three reached `mesh.out0` and `mesh.out3` | leak |
| `pf::pf_kitbash` | `__library` | delete node added; **unverified**, needs a populated library | leak |
| `pf::merge_enum`, `pf::connectivity_plus`, `pf::geoimporter`, `pf::mesh_view` | `enum_attr` default `enum` | `pf_enum` | parm default |
| `pf::axis_mask` | `attribute` default `axisRamp` | `pf_axis_mask` | parm default |
| `pf::texture_bombing` | `dir_attr` default `PF_bomber_dir` | `pf_bomber_dir` | parm default |
| `pf::group_by_topology` | `groupname` default `toposelect` | `pf_toposelect` | parm default |
| `pf::ramp_tube` | prim+point `row`, `column` | `pf_row`, `pf_column`, **and `row`/`column` written alongside** | BREAKING — compat dual-write, see §9e |
| `pf::prepare_mesh` | detail `__scalefactor`, `__scaleX/Y/Z` | deleted — the cleanup node named them in the POINT class while the wrangles wrote DETAIL, so it had never run | leak |
| `PF::split_poly` | group `splitPathGroup` | `_split_path` + a `groupdelete _*` before `OUT` | leak (§4's LEAKING exception) |
| `pf::prim_cross` | group `splitPathGroup` (inherited), detail `p1 p2 p3 p4` | `_p1`…`_p4`; literal `dtldel` list → `_*` on all four classes; `groupdelete _*` added | leak |
| `pf::polysplit` | `pf_tempsplit`, `pf_splitEdges`, `pf_splitPoints` | `_split`, `_split_edges`, `_split_points`; literal delete lists → `_*` | §6 debt |
| `pf::group_by_topology` | `pf_tempgroup` | `_topogroup`; `attribdelete _*` + `groupdelete _*` added — it had no attribute delete at all | §6 debt |
| `pf::geoimporter` | dead TOP parm `workitemattributes = enum` | cleared (`addworkitemattributes` is 0, so it never ran; the neighbouring `pieceattribute = class` is `geometryimport`'s own default and stays, §4) | stale hardcode |
| `pf::texture_bombing` | `importpoint6`'s `attribute` parm still `PF_bomber_dir`; node Help still documented `PF_bomber_dir`; `#id: dirr_attr` typo | all three fixed | stale hardcode + doc drift |

The last seven rows are the second wave, from the review of the first. Their common shape:
**the name was migrated and the thing that enforces or documents the name was not.**

**A parm-default change does not break a saved scene, and this was measured rather than reasoned
about.** A scene holding untouched instances of six of these was saved, the defaults were changed,
and the scene was reloaded in a fresh session: every placed node still read the OLD name, and a
node created after the change read the new one. Houdini writes the value into the `.hip` even at
default. The consequence to plan for is therefore not breakage — it is that **old and new scenes
emit different names side by side**, so anything consuming these must tolerate both for as long as
old scenes exist.

⚠️ **`pf::ramp_tube` is not one of those, and the first version of this table said it was.** It
was logged as *"rename, no consumers"* on a survey that established no consumer inside the REPO.
`row` and `column` are hard-coded in eight wrangles and two attribdelete patterns, with no
parameter, so a `.hip` has nothing to remember: saving a scene against the old library, replacing
the `.hda` files in place (what a `git pull` does) and reloading turned `column`/`row` into
`pf_column`/`pf_row` on every already-placed node, and a downstream `i@picked = (i@column == 1)`
went from matching one ring to matching none — silently, because VEX resolves a missing `@column`
to 0. A user scene is exactly the consumer §9 exists to protect. It now dual-writes both spellings
(two ints on a small tube — the §9c "doubling a 60-attribute schema" objection does not apply
here); dropping the old pair is §9e.

## 9. The breaking set — staged plan, not yet executed

Everything below has a real consumer. **None of it is done.** Order is by cost; the two
preconditions in §9c are hard blocks.

### 9a. `pf::pf_asset_tag` — `file` / `category` / `tag`

`file` is the single most collision-prone name in the suite. Read by
`polyfactory/scripts/python/polyfactory/asset_library/batch_importer.py:127-129` via
`_read_str_attrib` — the only non-CityGen HDA with a live Python consumer.

* **Rename to** `pf_asset_file` / `pf_asset_category` / `pf_asset_tag`.
* **Breaks** every already-tagged asset on disk: the tag is baked into saved geometry, so a straight
  swap silently drops the whole library's metadata.
* **Compatibility period: YES, and it costs one line.** `_read_str_attrib` reads the new name and
  falls back to the old. Assets re-tag naturally as they are re-saved; the fallback is deleted after
  a re-tag sweep.
* **Cost:** one HDA, one Python file. No test fixture moves.

### 9b. The CityGen field contract — `field_type` / `field_src` / `weight` / `angle` / `falloff` / `plaza_radius` / `degenerate`

An HDA→HDA contract with **no Python and no VEX-library consumer**: two field assets produce it and
`pf_citygen_tracer`'s VEX consumes it. `weight`, `angle` and `falloff` on a bare point cloud are
exactly the collision §1 exists to prevent.

* **Rename to** `pf_field_type`, `pf_field_src`, `pf_field_weight`, `pf_field_angle`,
  `pf_field_falloff`, `pf_field_plaza_radius`, `pf_field_degenerate`.
* **Breaks** a user scene that hand-authors a field point cloud.
* **Compatibility period: NO.** Three HDAs in one commit is atomic; a dual-write would cost more
  than it buys.
* **Cost:** three HDAs, one commit, no code. The cheapest of the CityGen work and the highest
  collision risk — so do it first of the CityGen items.

### 9c. CityGen streets V1 — the prim schema, the point schema, the `repair_*` diagnostics

The shipped, documented schema of [`citygen_streets.md`](citygen_streets.md) §6, plus the 25
diagnostics that only `tests/citygen/checks.py` reads.

* **Split into three commits, diagnostics FIRST.** The 19 `repair_*` detail attributes have exactly
  one reader, so they are a single-file edit that establishes the pattern and the re-record ritual
  on the cheapest possible group. Then the point schema, then the prim schema.
* **Breaks** user scenes, and it MOVES two committed fixtures: `tests/citygen/baseline.json` and
  `tests/unit/trim_calibration.json`. Both must be re-recorded **in the same commit**, with the
  runner's moved-value report read line by line — a rename must move *names*, and nothing else.
* **Compatibility period: NO — prefer rename-on-load.** Writing both names doubles a 47-to-60
  attribute schema on every prim of a shipped mesh, which is a real memory and confusion cost. If a
  bridge is wanted it belongs in ONE switchable `attribrename` block at the head of the mesher, not
  in the producers.
* **Two hard preconditions, both blocking:**
  1. **`edge_id` and `variant` are read from inside the frozen polyChain tree.**
     `polychain/place.py` reads `edge_id`, `polychain/__init__.py` reads `variant`, and `variant` is
     additionally a `sweep` `crosssectionattrib` in six places in `pf_citygen_mesh`. This cannot
     start until the polyChain native rebuild reaches parity and that tree unfreezes — the same §3
     reasoning that defers polyChain defers this.
  2. **The baselines are re-recorded by the same commit.** Otherwise the comparison that proves
     CityGen correct is destroyed, which is the same failure §3 was written to avoid.

### 9d. Open question, deliberately not decided here

`pf::primneighbouredge`'s `primgroup` default `edges` is both READ and WRITTEN by the asset — a
`grouppromote` promotes a group called `edges` and keeps the name. If it is an input selector it
must NOT be prefixed, because we do not own upstream group names; if it is an output it must be
`pf_edges`. Decide it by looking at how it is wired in a real scene, not by reading the network.

### 9e. `pf::ramp_tube` — drop the `row` / `column` compatibility copy

The cheapest item on this list, and the only one already half-done. `pf_row` / `pf_column` ship
today; `row` / `column` are written beside them by two wrangles named `compat_row_column_prims`
and `compat_row_column_points`, sitting between `groupdelete1` and `output0`.

* **To finish:** delete those two nodes. That is the whole change.
* **Breaks** any scene still reading `@row` / `@column` off a ramp_tube — which is every scene
  saved before the rename, and no scene saved after it.
* **Decide by:** whether Hannes has ramp_tube instances in scenes he still opens. If not, delete
  now; if yes, delete after those scenes are re-authored. There is no code and no fixture on
  either side of this.
* **Cost:** one HDA, one commit, plus `--update-baseline` on `tests/hda/` (which will report
  exactly `-['column','row']` on point and prim, and nothing else).
