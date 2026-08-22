# polyfactory conventions — attribute naming and node hygiene

**Status:** project law, adopted 2026-08-22 (Hannes). Binding on every polyfactory tool.
**This file owns:** the *data* conventions — what attributes are called and what must not escape
a node. It is the data-side sibling of [`artist_ui.md`](artist_ui.md) §6, which owns the
*parameter surface* and is binding the same way.
**Why a new file:** neither `artist_ui.md` (UI) nor `citygen.md` (citygen's own contracts) owns
suite-wide data naming, and the rule applies to every tool including the parked ones.

---

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
- a delete of `_*` sits immediately before the output;
- a test asserts the output carries no `_*` attribute — the rule is worth nothing unenforced.

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

Existing spellings to fold in when each tool is next opened: `pf_tempgroup`
(`pf::group_by_topology`), `pf_tempsplit` (`pf::polysplit`). Both are deleted today, so they are
hygiene debt, not leaks.

## 6. `_*` and `__*` are the same rule — do not add a third spelling

Four tools already wrote `__bankratio`, `__scaleX`, `__library`; two wrote `pf_temp*`. `__*` is a
strict subset of `_*`: one attribute-delete pattern of `_*` removes both, and one test asserting
"no output name begins with `_`" catches both. So the law is **one leading underscore, minimum**;
`__` is allowed where it already exists; and `pf_temp*` is not a spelling of this rule at all — it
says `pf_`, which §1 reserves for what SHIPS. Rename `pf_temp*` to `_*` when the tool is next
opened.

## 7. Enforcement — `tests/hda/run_attrib_checks.py`

    hython tests/hda/run_attrib_checks.py
    hython tests/hda/run_attrib_checks.py --update-baseline

Two checks, and the second is not decoration:

1. **The law.** No output of any polyfactory HDA carries an attribute or group beginning with `_`.
2. **The snapshot.** Every published name is recorded in `tests/hda/baseline.json` and diffed, so a
   new attribute on an output is a diff a human has to look at.

**Why both.** Run against the pre-migration HDAs, check 1 reports **zero failures** — `psplit`,
`origP`, `scaleX/Y/Z`, `scalefactor`, `class`, `keep_component`, `restlength` and `verts` were all
leaks, and not one of them was spelled `_*`. The law only catches leakage honest enough to declare
itself; only the snapshot catches the rest. Check 1 was separately proved able to fail at all: a
throwaway HDA writing `s@_scratch` produced `[FAIL] pf::leak_probe::1.0  detail._scratch`.

The runner prints an **UNPROVEN** block — assets that do not cook, cook empty, or cook only their
pass-through branch (`pf::geoimporter`, `pf::pf_asset_place`, `pf::pf_kitbash`). *"We could not make
it leak"* is not *"it does not leak"*, and that list is the part of the suite that is missing,
stated out loud. `pf::group_by_topology` is cooked twice, at default and in point mode, because
`verts` only ever existed on the second — which is exactly how it survived a full survey.

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
| `pf::ramp_tube` | prim+point `row`, `column` | `pf_row`, `pf_column` | rename, no consumers |

**A parm-default change does not break a saved scene, and this was measured rather than reasoned
about.** A scene holding untouched instances of six of these was saved, the defaults were changed,
and the scene was reloaded in a fresh session: every placed node still read the OLD name, and a
node created after the change read the new one. Houdini writes the value into the `.hip` even at
default. The consequence to plan for is therefore not breakage — it is that **old and new scenes
emit different names side by side**, so anything consuming these must tolerate both for as long as
old scenes exist.

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
