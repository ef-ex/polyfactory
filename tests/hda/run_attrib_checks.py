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
     were not, and only a snapshot catches that shape.

⚠️ "We could not make it leak" is not "it does not leak". An asset needing
input this file cannot synthesise (a populated kitbash library, a USD file on
disk) is reported under UNPROVEN, along with anything listed in UNEXERCISED,
and assets whose leak only appears on a non-default branch are cooked twice —
see BRANCHES. Read that list; it is the part of the suite that is missing,
stated out loud.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "tests", "citygen"))

import cases                                        # noqa: E402

OTLS = os.path.join(REPO, "polyfactory", "otls")
BASELINE = os.path.join(HERE, "baseline.json")

# polyChain is mid-rebuild and owned by another workstream; conventions.md §3.2
# defers its rename until the native rebuild reaches parity, because parity is
# asserted by comparing its output against the Python reference and renaming
# one side destroys that comparison. DELETE THIS ENTRY when the rebuild lands —
# the `_*` rule is adopted in it immediately, so it should pass on arrival.
NOT_YET = {"pf_polychain"}

# Assets whose leak is invisible at default parameters. Each entry cooks a
# SECOND time with the parms set, because that is exactly how `verts` and
# `scalefactor` survived a full survey of the suite.
BRANCHES = {
    "pf::group_by_topology::1.0": [{"grouptype": "point"}],
}

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


def polyfactory_sops():
    types = []
    for t in hou.sopNodeTypeCategory().nodeTypes().values():
        d = t.definition()
        if d is None:
            continue
        path = d.libraryFilePath().replace("\\", "/").lower()
        if "/polyfactory/otls/" not in path:
            continue
        if os.path.basename(path)[:-4] in NOT_YET:
            continue
        types.append(t)
    return sorted(types, key=lambda t: t.name())


def run_generic(results, uncooked, empties):
    geo = hou.node("/obj").createNode("geo", "hygiene")
    for c in geo.children():
        c.destroy()
    fs = feeds(geo)
    for t in polyfactory_sops():
        variants = [("", {})]
        for p in BRANCHES.get(t.name(), []):
            variants.append(("[%s]" % ",".join("%s=%s" % kv for kv in p.items()), p))
        for label, parms in variants:
            got = None
            for _fname, feed in fs:
                n = geo.createNode(t.name(), "probe_tmp")
                for i in range(min(n.type().maxNumInputs(), 3)):
                    try:
                        n.setInput(i, feed)
                    except hou.InvalidInput:
                        pass
                for k, v in parms.items():
                    n.parm(k).set(v)
                got, empty = cook(n)
                n.destroy()
                if got is not None:
                    break
            key = t.name() + label
            if got is None:
                uncooked.append(key)
            else:
                results[key] = got
                if empty:
                    empties.append(key)


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
        if f.endswith(".hda") and f[:-4] not in NOT_YET:
            try:
                hou.hda.installFile(os.path.join(OTLS, f))
            except Exception as exc:
                print("install failed: %s (%s)" % (f, str(exc)[:120]))

    results, uncooked, empties = {}, [], []
    run_generic(results, uncooked, empties)
    run_citygen(results, uncooked, empties)

    # --- 1. the law --------------------------------------------------------
    failures = 0
    print("=== internal `_*` names on an output (conventions.md 2) ===")
    for key in sorted(results):
        leaked = sorted(set(s for out in results[key].values() for s in scratch(out)))
        if leaked:
            failures += 1
            print("  [FAIL] %-44s %s" % (key, ", ".join(leaked)))
    print("  %d of %d cooked assets leak an internal name"
          % (failures, len(results)))

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
        print("  %d change(s) — every one must be deliberate" % len(moved))
    else:
        print("  no change")

    if uncooked or empties or (set(UNEXERCISED) & set(results)):
        print("\n=== UNPROVEN — not the same thing as clean ===")
        for k in sorted(uncooked):
            print("  did not cook   %s" % k)
        for k in sorted(empties):
            print("  cooked EMPTY   %s (needs input this file cannot make)" % k)
        for k in sorted(set(UNEXERCISED) & set(results)):
            print("  pass-through   %s — %s" % (k, UNEXERCISED[k]))

    if "--update-baseline" in sys.argv:
        with open(BASELINE, "w") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)
        print("\nbaseline written: %s" % BASELINE)
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(results, fh, indent=1, sort_keys=True)

    print("\n%d failing checks" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    import hou                                       # noqa: E402
    sys.exit(main())
