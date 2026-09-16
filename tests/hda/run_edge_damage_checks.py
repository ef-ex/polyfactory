"""`pf_edge_damage` parity checks: the SHIPPED asset against the reference dump.

    hython tests/hda/run_edge_damage_checks.py

`pf_edge_damage` is a 1:1 port of Quentin King's Paintable Stylized Edge
Damage. The contract is therefore PARITY, not correctness of my own
choosing: `edge_damage_spec.json` is the reference asset as read off a live
session, and these checks hold the shipped asset to it - every node, wire
and non-default parameter; every parameter template; the viewer state
module byte for byte - plus one behaviour that needs no strokes and the
unlocked-instance condition the reference's stroke cache needs, and the one
requested improvement (Damage Depth cuts flat faces). Six checks, six
mutations, each seen red.

What these checks CANNOT see: a brush stroke landing where the cursor is
(only a human can); the HUD and hotkeys (viewer-side); anything the
reference itself gets wrong, because the reference IS the oracle.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_edge_damage.hda").replace("\\", "/")
SPEC = json.load(open(os.path.join(HERE, "edge_damage_spec.json"), encoding="utf-8"))
# stroke_numstrokes' children are attribpaint's own templates, copied native.
SKIP_PARMS = {"stroke_numstrokes"}


def volume(geo):
    total = 0.0
    for pr in geo.prims():
        vs = [v.point().position() for v in pr.vertices()]
        for i in range(1, len(vs) - 1):
            total += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    return abs(total)


def c1_every_node_wire_and_parm_matches_the_reference(node, spec):
    bad = []
    for n in spec["nodes"]:
        c = node.node(n["name"])
        if c is None:
            bad.append("%s missing" % n["name"]); continue
        if c.type().name() != n["type"]:
            bad.append("%s is %s not %s" % (n["name"], c.type().name(), n["type"]))
        ins = [i.name() if i else None for i in c.inputs()]
        want = [None if s == "box1" else s for s in n["in"]]
        if n["name"] != "IN" and ins != want:
            bad.append("%s inputs %s want %s" % (n["name"], ins, want))
        for pname, val in n["parms"].items():
            p = c.parm(pname)
            got = p.expression() if p.keyframes() and p.expression() else p.eval()
            if got != val and not (isinstance(val, float) and abs(got - val) < 1e-9):
                bad.append("%s.%s = %r want %r" % (n["name"], pname, got, val))
    return not bad, "%d nodes checked, %d differences%s" % (
        len(spec["nodes"]), len(bad), (": " + "; ".join(bad[:4])) if bad else "")


def c2_every_parameter_template_matches_the_reference(node, spec):
    ptg = node.type().definition().parmTemplateGroup()
    bad = []
    for p in spec["parms"]:
        if p["name"] in SKIP_PARMS or "#" in p["name"]:
            continue
        t = ptg.find(p["name"])
        if t is None:
            bad.append("%s missing" % p["name"]); continue
        got = {"type": t.type().name(), "label": t.label(), "hidden": t.isHidden()}
        want = {"type": p["type"], "label": p["label"], "hidden": p["hidden"]}
        if p["type"] in ("Float", "Int", "String", "Toggle", "Menu"):
            got["default"] = list(t.defaultValue()) if isinstance(t.defaultValue(), tuple) else t.defaultValue()
            want["default"] = p["default"]
        if p["type"] in ("Float", "Int"):
            got.update(min=t.minValue(), max=t.maxValue(), minlock=t.minIsStrict(), maxlock=t.maxIsStrict())
            want.update(min=p["min"], max=p["max"], minlock=p["minlock"], maxlock=p["maxlock"])
        if p["type"] == "Menu":
            got["items"], want["items"] = list(t.menuItems()), p["items"]
        if p["type"] == "Button":
            got["callback"], want["callback"] = t.scriptCallback(), p["callback"]
        if got != want:
            bad.append("%s: %s" % (p["name"], {k: (got[k], want[k]) for k in got if got[k] != want[k]}))
    return not bad, "%d templates checked, %d differences%s" % (
        len(spec["parms"]), len(bad), (": " + "; ".join(bad[:3])) if bad else "")


def c3_the_viewer_state_is_the_reference_module(node, spec):
    d = node.type().definition()
    s = d.sections()
    # reference + exactly the declared patches (visualizer guard, HUD bar)
    expected = spec["viewer_state"]
    for old, new in spec["viewer_state_patches"]:
        expected = expected.replace(old, new)
    same = s["ViewerStateModule"].contents() == expected
    state_ok = s["DefaultState"].contents() == d.nodeTypeName()
    flags = all(d.extraFileOptions().get(k) for k in (
        "ViewerStateInstall/IsPython", "ViewerStateModule/IsPython", "ViewerStateModule/IsViewerState"))
    links = hou.hscript("opmultiparm " + node.node("attribpaint1").path())[0].split(None, 2)[2].strip()
    links_ok = links == spec["stroke_links"].strip()
    ok = same and state_ok and flags and links_ok
    return ok, "module verbatim %s, default state %s, python flags %s, stroke links %s" % (
        same, state_ok, flags, links_ok)


def c4_no_strokes_hands_the_input_back(node, spec):
    """With no strokes `mask` is 0 everywhere, `(1 - mask) * 0.1` pushes the
    whole cutter out, and the intersection is the original: same volume."""
    node.parm("stroke_numstrokes").set(0)
    g = node.geometry()
    v = volume(g)
    return abs(v - 1.0) < 5e-3, "volume %.5f of 1.0 (want within 0.5%%)" % v


def c5_the_stroke_cache_can_be_written(node, spec):
    """The reference's onPostApplyStroke writes bakedgeo/strokegeo on the
    INNER attribpaint after every stroke; on a locked instance that is a
    hou.PermissionError on the first stroke (Hannes, 2026-09-16). New
    instances must come unlocked, and the write must succeed on a fresh one."""
    fresh = node.parent().createNode("pf_edge_damage")
    try:
        unlocked = fresh.type().definition().options().unlockNewInstances()
        try:
            fresh.node("attribpaint1").parm("bakedgeo").set(None)
            fresh.node("attribpaint1").parm("strokegeo").set(None)
            writable = True
        except hou.PermissionError:
            writable = False
    finally:
        fresh.destroy()
    return unlocked and writable, "unlockNewInstances %s, inner cache parms writable %s" % (
        unlocked, writable)


# mutations - c1/c4 edit the unlocked INSTANCE; c2/c3 edit the ORACLE, which
# proves the comparison reads the field at all (a definition cannot be
# mutated on an instance without writing the library file back).
def m_rewired(node, spec):
    node.node("boolean2").setInput(1, node.node("remesh4"))


def m_spec_default_moved(node, spec):
    [p for p in spec["parms"] if p["name"] == "dist"][0]["default"] = [0.05]


def m_spec_module_edited(node, spec):
    spec["viewer_state"] = spec["viewer_state"].replace("0.05", "0.06", 1)


def c6_a_stroke_cuts_a_flat_face(node, spec):
    """Hannes: damage anywhere, not only at the edges the blur pulls in.
    With `mask` forced to 1 everywhere (a wrangle slipped in before the
    paint node on the unlocked instance - no stroke can be scripted), the
    +X FACE must lose material: chip faces in its middle, volume down."""
    import hou
    w = node.createNode("attribwrangle", "_force_mask")
    w.setInput(0, node.node("divide4"))
    w.parm("snippet").set("f@mask = 1.0;")
    node.node("attribpaint1").setInput(0, w)
    g = node.geometry()
    grp = g.findPrimGroup("pf_chipped")
    mid = 0
    for pr in (grp.prims() if grp else []):
        vs = [v.point().position() for v in pr.vertices()]
        c = sum(vs, hou.Vector3()) / len(vs)
        if c[0] > 0.3 and abs(c[1]) < 0.25 and abs(c[2]) < 0.25:
            mid += 1
    v = volume(g)
    node.node("attribpaint1").setInput(0, node.node("divide4"))
    w.destroy()
    return mid > 0 and v < 0.97, "%d chip faces mid +X face (want > 0), volume %.4f (want < 0.97)" % (mid, v)


def m_no_depth(node, spec):
    node.parm("damage_depth").set(0.0)          # the original tool


def m_no_mask_bias(node, spec):
    node.node("apply_mask_bias").bypass(True)


def m_instances_locked(node, spec):
    """Flip the option on the loaded definition IN MEMORY (never saved:
    nothing calls updateFromNode or save) and restore it after."""
    d = node.type().definition()
    o = d.options()
    o.setUnlockNewInstances(False)
    d.setOptions(o)


def _restore_unlock(node):
    d = node.type().definition()
    o = d.options()
    o.setUnlockNewInstances(True)
    d.setOptions(o)


REGISTRY = [
    (c1_every_node_wire_and_parm_matches_the_reference, m_rewired),
    (c2_every_parameter_template_matches_the_reference, m_spec_default_moved),
    (c3_the_viewer_state_is_the_reference_module, m_spec_module_edited),
    (c4_no_strokes_hands_the_input_back, m_no_mask_bias),
    (c5_the_stroke_cache_can_be_written, m_instances_locked),
    (c6_a_stroke_cuts_a_flat_face, m_no_depth),
]


def main():
    global hou
    import hou
    import copy
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "edge_damage_checks")
    box = geo.createNode("box")
    node = geo.createNode("pf_edge_damage")
    node.setInput(0, box)

    failures = 0
    t0 = time.time()
    print("pf_edge_damage - %s\n" % HDA)
    for check, mutate in REGISTRY:
        node.allowEditingOfContents()
        ok, detail = check(node, SPEC)
        if not ok:
            failures += 1
        print("  %s  %-52s %s" % ("ok  " if ok else "FAIL", check.__name__, detail))
        spec = copy.deepcopy(SPEC)
        try:
            mutate(node, spec)
            red, mdetail = check(node, spec)
        except Exception as exc:
            red, mdetail = False, "%s: %s" % (type(exc).__name__, exc)
        node.matchCurrentDefinition()
        if mutate is m_instances_locked:
            _restore_unlock(node)
        if mutate is m_no_depth:
            node.parm("damage_depth").revertToDefaults()
        if red:
            failures += 1
            print("        MUTATION %s STAYED GREEN - this check cannot "
                  "fail: %s" % (mutate.__name__, mdetail))
    print("\n%d failing checks in %.2f s" % (failures, time.time() - t0))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
