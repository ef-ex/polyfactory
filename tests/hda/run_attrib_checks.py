"""Attribute hygiene for every polyfactory HDA, in a throwaway Houdini session.

    hython tests/hda/run_attrib_checks.py
    hython tests/hda/run_attrib_checks.py --update-baseline
    hython tests/hda/run_attrib_checks.py --json results.json

`ideas/conventions.md` §2 says an internal attribute is named `_*` and is
deleted before the output. That rule is worth nothing unenforced: when this
file was written, TWELVE working attributes were leaking out of seven assets,
three of them all the way onto the shipped CityGen mesh — and four of those
assets already carried a cleanup node that had simply never been checked. So:

  1. THE LAW. No output of any polyfactory HDA may carry an attribute or a
     group whose name begins with `_`. One assertion, no allow-list, no
     exceptions — an allow-list here is how the rule rots.

  2. THE SNAPSHOT. Every published name is recorded in `baseline.json`, so a
     NEW attribute on an output is a diff a human has to look at instead of
     something that ships unnoticed. Rule 1 only catches leaks honest enough
     to be named `_*`; `class`, `keep_component`, `restlength` and `verts`
     were not, and only a snapshot catches that shape. **Both halves set the
     exit status.** They did not always: the snapshot printed its diff and
     returned 0, so an injected `i@junkleak` — the exact shape of all twelve
     original leaks — reported "0 failing checks" and exited green.

  3. THE COLLATERAL. §2's sweep is a wildcard on the whole pass-through
     stream, so it also deletes `_*` attributes and groups that arrived from
     UPSTREAM and were never ours. That is deliberate (conventions.md §2) and
     it is measured here, under the `upstream/` keys, so it is a recorded
     behaviour rather than a surprise found in someone else's scene.

⚠️ "We could not make it leak" is not "it does not leak". Every asset is
cooked at its defaults AND once per non-default value of every toggle and
menu it exposes, because `verts`, `scalefactor` and `__scalefactor` were all
invisible at default parameters — the last of those survived a full survey, a
migration and a review pass, on a menu branch nothing had ever cooked. Assets
needing input this file cannot synthesise (a populated kitbash library, a USD
file on disk) are reported under UNPROVEN, together with every definition in
`otls/` that is not a SOP and therefore never enters the check at all. Read
that block; it is the part of the suite that is missing, stated out loud.
"""

import gzip
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tests", "citygen"))

import cases                                        # noqa: E402

OTLS = os.path.join(REPO, "polyfactory", "otls")
BASELINE = os.path.join(HERE, "baseline.json")

# ⚠️ POLYCHAIN IS IN THE RUN NOW, AND THE NOTE THAT EXCLUDED IT WAS FALSE.
# It read: "DELETE THIS on parity — the `_*` rule is adopted in the rebuild,
# so it should pass on arrival." Measured on the build that claimed it: the
# asset carried ZERO `_*` names on any of the four classes at any of its seven
# Stage values, held exactly one `attribdelete` (point class only, a precision
# fix) and no `groupdelete` — the rebuild had created ~50 internal attributes
# and named every one of them as if it were contract. It would have FAILED on
# arrival, and the one test that could see that was disarmed with a rationale
# that was not true.
#
# conventions.md §3 rule 2 still defers the `pc_*` → `pf_*` rename until the
# native rebuild reaches parity (renaming one side of a parity comparison
# destroys it) and says the `_*` rule applies IMMEDIATELY. So the `_*` half is
# enforced here from now on; the `pf_` half is `NOT_YET_PF`, which this file
# does not test and which polychain.md owns.
#
# The prefix-match form is kept for the exclusion list because that
# workstream once dropped a `pf_polychain_old.hda` beside the real one
# mid-audit, and an exact match let the frozen tree straight into the run.
NOT_YET = "pf_polychain_old"

# Bounds on the parameter sweep. Every toggle gets its other value; every menu
# gets its first MENU_VALUES entries. Unbounded is a combinatorial explosion
# for no extra coverage — a leak lives on a branch, not on a pair of branches.
MENU_VALUES = 4
MAX_VARIANTS = 60

# Assets that cook here, but only ever on the pass-through branch: their real
# work needs input this file cannot synthesise, so a PASS on them means
# "nothing leaked out of the part we could reach" and nothing more.
UNEXERCISED = {
    "pf::pf_kitbash::1.0": "needs a populated kitbash library (`__library`, "
                           "`filePath` and the placed-point branch unreached)",
    "pf::geoimporter::1.0.0": "needs USD/geo files on disk; the import branch, "
                              "which is where it writes its enum, is unreached",
    "pf::pf_asset_place::1.0": "needs a USD stage",
}

# Why a whole node-type category is out of scope. These definitions carry
# attribute names as parameter defaults only; there is no geometry output to
# read them off, so this runner can prove nothing about them either way.
OUT_OF_SCOPE = {
    "Vop": "no geometry output — names appear only as parm defaults and wired "
           "VOP inputs (`pf::texture_bombing`'s `dir_attr` lives here)",
    "Cop": "image operators — no geometry, no attributes",
    "Lop": "USD stage operators — primvars, not GA attributes",
}


# Names the migration retired. A cook cannot see these: they survive as a parm
# value on a branch nothing reaches, or as a sentence in a Help card. Both
# happened — `pf::texture_bombing` kept `PF_bomber_dir` on `importpoint6`'s
# `attribute` parm (inert only because a wired VOP input overrides it) AND in
# the help text that tells the artist what to name their point attribute, and
# it is a Vop, so nothing else in this file can reach it. Word-boundary match,
# so `pf_toposelect` does not trip on `toposelect`.
RETIRED = {
    "PF_bomber_dir": "pf::texture_bombing `dir_attr` — now `pf_bomber_dir`",
    "dirr_attr": "pf::texture_bombing help `#id:` typo — the parm is `dir_attr`",
    "axisRamp": "pf::axis_mask `attribute` — now `pf_axis_mask`",
    "toposelect": "pf::group_by_topology `groupname` — now `pf_toposelect`",
    "pf_tempgroup": "pf::group_by_topology working group — now `_topogroup`",
    "pf_tempsplit": "pf::polysplit working name — now `_split`",
    "pf_splitEdges": "pf::polysplit working group — now `_split_edges`",
    "pf_splitPoints": "pf::polysplit working group — now `_split_points`",
    "splitPathGroup": "PF::split_poly's polysplit groupname — now `_split_path`",
    "origP": "efex::normalizemesh — now `_orig_p`",
}


def retired_spellings():
    """[(file, name, why)] for every retired name still written into a library
    file, sections and compressed node contents alike."""
    hits = []
    for f in sorted(os.listdir(OTLS)):
        if not f.endswith(".hda") or f[:-4].startswith(NOT_YET):
            continue
        blobs = []
        for d in hou.hda.definitionsInFile(os.path.join(OTLS, f)):
            for sec in d.sections().values():
                try:
                    c = sec.contents()
                except Exception:
                    continue
                if isinstance(c, bytes):
                    if c[:2] == b"\x1f\x8b":
                        try:
                            c = gzip.decompress(c)
                        except Exception:
                            pass
                    c = c.decode("utf-8", "replace")
                blobs.append(c)
        text = "\n".join(blobs)
        for name, why in sorted(RETIRED.items()):
            if re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % name, text):
                hits.append((f, name, why))
    return hits


def feeds(geo):
    """Input geometry, in the order each HDA is offered it. The first one that
    cooks without error wins."""
    grid = geo.createNode("grid", "feed_grid")
    grid.parmTuple("size").set((10, 10))
    grid.parm("rows").set(5)
    grid.parm("cols").set(5)

    box = geo.createNode("box", "feed_box")
    box.parmTuple("size").set((3.0, 7.0, 11.0))
    boxd = geo.createNode("divide", "feed_box_div")
    boxd.setInput(0, box)

    line = geo.createNode("line", "feed_line")
    line.parm("points").set(12)

    sphere = geo.createNode("sphere", "feed_sphere")
    sphere.parm("type").set(4)

    # named + enumerated pieces: mesh_view, and anything piece-wise, needs both
    name = geo.createNode("attribwrangle", "feed_name")
    name.setInput(0, boxd)
    name.parm("class").set(1)
    name.parm("snippet").set('s@name = sprintf("piece%d", @primnum % 3);')
    enum = geo.createNode("attribwrangle", "feed_enum")
    enum.setInput(0, name)
    enum.parm("class").set(2)
    enum.parm("snippet").set("i@pf_enum = @ptnum % 3;")

    return [("pieces", enum), ("grid", grid), ("box", boxd),
            ("line", line), ("sphere", sphere)]


def upstream_feed(geo, src, idx):
    """`src` plus `_*` names that are NOT ours — a third-party or user working
    attribute merely passing through a polyfactory node. What survives is
    recorded, because §2's wildcard sweep deletes these too."""
    w = geo.createNode("attribwrangle", "feed_upstream%d" % idx)
    w.setInput(0, src)
    w.parm("class").set(2)
    w.parm("snippet").set(
        'f@_vendor_pt = 1.0;\n'
        'setprimattrib(0, "_vendor_prim", 0, 1.0);\n'
        'setdetailattrib(0, "__vendor_detail", 1.0);\n'
        'setpointgroup(0, "_vendor_group", @ptnum, 1);\n'
        'i@pf_keepme = 1;')
    return w


def published(geo):
    """Every name on one output, by class."""
    out = {}
    for cls, fn in (("point", geo.pointAttribs), ("prim", geo.primAttribs),
                    ("vertex", geo.vertexAttribs), ("detail", geo.globalAttribs)):
        out[cls] = sorted(a.name() for a in fn())
    out["group"] = sorted([g.name() for g in geo.primGroups()] +
                          [g.name() for g in geo.pointGroups()] +
                          [g.name() for g in geo.edgeGroups()])
    return out


def scratch(pub):
    """The law: nothing named `_*` may leave."""
    return sorted("%s.%s" % (cls, n) for cls, names in pub.items()
                  for n in names if n.startswith("_"))


def merge(into, got):
    """Union one cook's published names into the running record for an asset.
    A branch adds names, it never takes them away, so an asset's snapshot is
    everything it CAN publish rather than what it happens to publish today."""
    for oi, byclass in got.items():
        slot = into.setdefault(oi, {})
        for cls, names in byclass.items():
            slot[cls] = sorted(set(slot.get(cls, [])) | set(names))


def cook(node):
    """({output index: published names}, empty), or (None, False) if it will
    not cook. `empty` means it cooked but every output came back with no
    points and no primitives — which is exactly as unproven as not cooking at
    all, and is reported as such."""
    if node.errors():
        return None, False
    res, count = {}, 0
    for i in range(node.type().maxNumOutputs()):
        try:
            g = node.geometry(i)
        except Exception:
            return None, False
        if node.errors():
            return None, False
        if g is not None:
            res[str(i)] = published(g)
            count += len(g.points()) + len(g.prims())
    if not res:
        return None, False
    return res, count == 0


def variants(node):
    """(label, {parm: value}) for the defaults and for every toggle and menu
    branch the asset exposes. This is the half that was missing: the old
    BRANCHES dict held ONE hand-written entry, so `pf::prepare_mesh`'s
    `__scalefactor` sat on a menu branch nothing ever cooked."""
    out = [("", {})]
    for p in node.parms():
        if len(out) >= MAX_VARIANTS:
            break
        pt = p.parmTemplate()
        try:
            kind = pt.type()
        except Exception:
            continue
        cur = p.eval()
        if kind == hou.parmTemplateType.Toggle:
            out.append(("[%s=%d]" % (p.name(), 1 - cur), {p.name(): 1 - cur}))
            continue
        try:
            items = list(pt.menuItems())
        except Exception:
            items = []
        if not items:
            continue
        if kind == hou.parmTemplateType.String:
            vals = [i for i in items[:MENU_VALUES] if i != cur]
        else:
            vals = [i for i in range(min(MENU_VALUES, len(items))) if i != cur]
        for v in vals:
            out.append(("[%s=%s]" % (p.name(), v), {p.name(): v}))
    return out


def build(geo, t, feed, parms):
    n = geo.createNode(t.name(), "probe_tmp")
    for i in range(min(n.type().maxNumInputs(), 3)):
        try:
            n.setInput(i, feed)
        except hou.InvalidInput:
            pass
    for k, v in parms.items():
        try:
            n.parm(k).set(v)
        except Exception:
            pass
    return n


def polyfactory_defs():
    """Every definition that lives in `otls/`, keyed by node-type category.
    The old version asked `hou.sopNodeTypeCategory()` only, so 19 of the 53
    definitions — `pf::texture_bombing` among them, which the pf_ migration
    edited — were neither checked nor mentioned."""
    found = {}
    for cat in hou.nodeTypeCategories().values():
        for t in cat.nodeTypes().values():
            d = t.definition()
            if d is None:
                continue
            path = d.libraryFilePath().replace("\\", "/").lower()
            if "/polyfactory/otls/" not in path:
                continue
            if os.path.basename(path)[:-4].startswith(NOT_YET):
                continue
            found.setdefault(cat.name(), []).append(t)
    for k in found:
        found[k] = sorted(found[k], key=lambda t: t.name())
    return found


def run_generic(results, uncooked, empties, swept):
    geo = hou.node("/obj").createNode("geo", "hygiene")
    for c in geo.children():
        c.destroy()
    fs = feeds(geo)
    ups = dict((nm, upstream_feed(geo, src, i))
               for i, (nm, src) in enumerate(fs))
    for t in polyfactory_defs().get("Sop", []):
        # Find a feed this asset accepts at defaults, then sweep on that one.
        live_feed = None
        for fname, feed in fs:
            n = build(geo, t, feed, {})
            got, empty = cook(n)
            n.destroy()
            if got is not None:
                live_feed, first, first_empty = fname, got, empty
                break
        if live_feed is None:
            uncooked.append(t.name())
            continue
        union = {}
        merge(union, first)
        results[t.name()] = union
        if first_empty:
            empties.append(t.name())
        feed = dict(fs)[live_feed]
        probe = build(geo, t, feed, {})
        vs = variants(probe)
        probe.destroy()
        swept[t.name()] = len(vs) - 1
        for label, parms in vs[1:]:
            n = build(geo, t, feed, parms)
            got, _ = cook(n)
            n.destroy()
            if got is not None:
                merge(union, got)
        # the collateral: which UPSTREAM `_*` names survive the sweep
        n = build(geo, t, ups[live_feed], {})
        got, _ = cook(n)
        n.destroy()
        if got is not None:
            kept = {}
            merge(kept, got)
            results["upstream/" + t.name()] = {"0": {"survives": sorted(set(
                s for out in kept.values() for s in scratch(out)))}}


def run_citygen(results, uncooked, empties):
    """The four-node chain on a grid field — the shipped pipeline, and where
    three of the twelve leaks were hiding. One case, not fifteen: this file
    asserts hygiene, `tests/citygen/run_scene_checks.py` asserts geometry."""
    geo = hou.node("/obj").createNode("geo", "hygiene_citygen")
    for c in geo.children():
        c.destroy()
    field = geo.createNode("pf_citygen_field_grid", "field")
    field.parm("angle").set(18.0)
    seg, solver, mesh = cases._chain(geo, "city", field, False)
    for role, node in (("field", field), ("tracer", seg.input(0)),
                       ("segmenter", seg), ("solver", solver), ("mesh", mesh)):
        got, empty = cook(node) if node is not None else (None, False)
        if got is None:
            uncooked.append("citygen/" + role)
        else:
            results["citygen/" + role] = got
            if empty:
                empties.append("citygen/" + role)


def main():
    cases.install_hdas()
    for f in sorted(os.listdir(OTLS)):
        if f.endswith(".hda") and not f[:-4].startswith(NOT_YET):
            try:
                hou.hda.installFile(os.path.join(OTLS, f))
            except Exception as exc:
                print("install failed: %s (%s)" % (f, str(exc)[:120]))

    results, uncooked, empties, swept = {}, [], [], {}
    run_generic(results, uncooked, empties, swept)
    run_citygen(results, uncooked, empties)

    law = dict((k, v) for k, v in results.items()
               if not k.startswith("upstream/"))

    # --- 1. the law --------------------------------------------------------
    failures = 0
    print("=== internal `_*` names on an output (conventions.md 2) ===")
    for key in sorted(law):
        leaked = sorted(set(s for out in law[key].values() for s in scratch(out)))
        if leaked:
            failures += 1
            print("  [FAIL] %-44s %s" % (key, ", ".join(leaked)))
    print("  %d of %d cooked assets leak an internal name, across %d "
          "parameter branches" % (failures, len(law), sum(swept.values())))

    # --- 1b. retired spellings still written into a library ----------------
    print("\n=== retired names still in a library file (conventions.md 8) ===")
    stale = retired_spellings()
    for f, name, why in stale:
        failures += 1
        print("  [FAIL] %-28s %-16s %s" % (f, name, why))
    if not stale:
        print("  none of the %d retired names survives in any of the %d "
              "libraries" % (len(RETIRED),
                             len([f for f in os.listdir(OTLS)
                                  if f.endswith(".hda")
                                  and not f[:-4].startswith(NOT_YET)])))

    # --- 2. the snapshot ---------------------------------------------------
    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            base = json.load(fh)
    moved = []
    for key in sorted(set(base) | set(results)):
        old, new = base.get(key), results.get(key)
        if old is None:
            moved.append("  NEW ASSET  %s" % key)
        elif new is None:
            moved.append("  GONE       %s (no longer cooks, or was removed)" % key)
        elif old != new:
            for oi in sorted(set(old) | set(new)):
                o, n = old.get(oi, {}), new.get(oi, {})
                for cls in sorted(set(o) | set(n)):
                    added = sorted(set(n.get(cls, [])) - set(o.get(cls, [])))
                    gone = sorted(set(o.get(cls, [])) - set(n.get(cls, [])))
                    if added or gone:
                        moved.append("  %s out%s %s: +%s -%s"
                                     % (key, oi, cls, added or [], gone or []))
    print("\n=== published names vs baseline ===")
    if moved:
        print("\n".join(moved))
        print("  %d change(s) — every one must be deliberate "
              "(--update-baseline accepts them)" % len(moved))
    else:
        print("  no change")

    print("\n=== UNPROVEN — not the same thing as clean ===")
    for k in sorted(uncooked):
        print("  did not cook   %s" % k)
    for k in sorted(empties):
        print("  cooked EMPTY   %s (needs input this file cannot make)" % k)
    for k in sorted(set(UNEXERCISED) & set(results)):
        print("  pass-through   %s — %s" % (k, UNEXERCISED[k]))
    defs = polyfactory_defs()
    for cat in sorted(defs):
        if cat == "Sop":
            continue
        print("  out of scope   %d %s definition(s): %s"
              % (len(defs[cat]), cat, ", ".join(t.name() for t in defs[cat])))
        print("                 %s" % OUT_OF_SCOPE.get(cat, "not cooked here"))

    if "--update-baseline" in sys.argv:
        with open(BASELINE, "w") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)
        print("\nbaseline written: %s" % BASELINE)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)

    accepted = "--update-baseline" in sys.argv
    print("\n%d failing checks, %d unreviewed baseline change(s)"
          % (failures, 0 if accepted else len(moved)))
    return 1 if failures or (moved and not accepted) else 0


if __name__ == "__main__":
    import hou                                       # noqa: E402
    sys.exit(main())
