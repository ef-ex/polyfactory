"""THE COMPARATOR'S OWN MUTATION BATTERY - one row per dimension it claims.

    hython tests/polychain/run_diff_selftest.py

`diff.compare` is the v2 oracle: every scene case is judged by it, so a
dimension it silently cannot see is a hole under the whole suite.  The
discipline rule is that a check is not written until its mutation has been
seen to go red - so every dimension of `snapshot` is mutated here, on a real
`hou.Geometry`, and the run FAILS if any mutation comes back "identical".

It also runs the control both ways: an unmutated pair must compare EMPTY, or
the oracle is a random-number generator and every red it prints is noise.

WHAT IT CANNOT SEE: whether `snapshot` reaches a dimension no mutation below
names.  It is a lower bound on the comparator's power, never a proof of
completeness - the fixture is a small polygon build plus one packed prim.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import runguard                                                  # noqa: E402
runguard.begin()          # before `hou`: `$TEMP` resolves once, at startup
import hou                                                       # noqa: E402
from diff import snapshot, compare, ulp32                        # noqa: E402


def build(shared=True, reverse=False):
    """Two prims sharing a point, a packed prim, and one attribute per class.

    `shared=False` is the SAME geometry with the shared corner split - the
    topology that is present in production and was in zero v1 parity fixtures.
    """
    geo = hou.Geometry()
    pts = [geo.createPoint() for _ in range(4)]
    for i, p in enumerate(pts):
        p.setPosition(hou.Vector3(float(i), 0.0, 0.0))
    a = geo.createPolygon(False)
    for p in (pts[2::-1] if reverse else pts[:3]):
        a.addVertex(p)
    b = geo.createPolygon(False)
    tail = list(pts[2:])
    if not shared:
        twin = geo.createPoint()
        twin.setPosition(tail[0].position())
        tail[0] = twin
    for p in tail:
        b.addVertex(p)
    geo.addAttrib(hou.attribType.Point, "pc_local", (0.0, 0.0, 0.0))
    geo.addAttrib(hou.attribType.Prim, "pc_module", "")
    geo.addAttrib(hou.attribType.Vertex, "pc_uv", 0.0)
    geo.addAttrib(hou.attribType.Global, "pc_warn_fit", 0)
    for i, p in enumerate(pts):
        p.setAttribValue("pc_local", (float(i), 1.0, 2.0))
    for i, prim in enumerate(geo.prims()):
        prim.setAttribValue("pc_module", "mod_%d" % i)
        for v in prim.vertices():
            v.setAttribValue("pc_uv", 0.25 * (v.number() + 1))
    geo.setGlobalAttribValue("pc_warn_fit", 3)
    grp = geo.createPrimGroup("pc_corner")
    grp.add(geo.prims()[0])
    inner = hou.Geometry()
    q = inner.createPoint()
    q.setPosition(hou.Vector3(9.0, 9.0, 9.0))
    geo.createPackedGeometry(inner)
    return geo


# --- the mutations.  Each must make `compare` non-empty. --------------------

def _pt(g, i):
    return g.points()[i]


MUTATIONS = (
    ("point_value", lambda g: _pt(g, 1).setAttribValue(
        "pc_local", (1.0, 1.0, 2.5))),
    ("point_P", lambda g: _pt(g, 0).setPosition(hou.Vector3(0.001, 0, 0))),
    ("prim_string_value", lambda g: g.prims()[0].setAttribValue(
        "pc_module", "mod_X")),
    ("vertex_value", lambda g: g.prims()[0].vertices()[0].setAttribValue(
        "pc_uv", 99.0)),
    ("detail_value", lambda g: g.setGlobalAttribValue("pc_warn_fit", 4)),
    ("attrib_added", lambda g: g.addAttrib(hou.attribType.Point, "_scratch", 0)),
    ("attrib_renamed", lambda g: g.renamePointAttrib(
        "pc_local", "pc_localx")),
    ("attrib_size", lambda g: g.addAttrib(hou.attribType.Prim, "pc_pair",
                                          (0.0, 0.0))),
    ("attrib_default", lambda g: g.addAttrib(hou.attribType.Prim, "pc_d", 7)),
    ("topology_closed", lambda g: g.prims()[0].setIsClosed(True)),
    ("topology_unshared", lambda g: build(shared=False)),
    # counts and values IDENTICAL, only the winding differs - the one row that
    # proves the `topology` dimension rather than riding on `pointcount`.
    ("topology_winding", lambda g: build(reverse=True)),
    ("group_membership", lambda g: g.findPrimGroup("pc_corner").add(
        g.prims()[1])),
    ("group_added", lambda g: g.createPointGroup("pc_extra")),
    ("packed_transform", lambda g: _packed(g).setIntrinsicValue(
        "transform", (2.0, 0, 0, 0, 1, 0, 0, 0, 1))),
    ("packed_contents", lambda g: _repack(g)),
    ("point_count", lambda g: g.createPoint()),
)


def _packed(geo):
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            return prim
    raise RuntimeError("the fixture lost its packed prim")


def _repack(geo):
    """Same wrapper, DIFFERENT contents - the 'image contains no subject' bug."""
    inner = hou.Geometry()
    p = inner.createPoint()
    p.setPosition(hou.Vector3(-9.0, -9.0, -9.0))
    _packed(geo).setEmbeddedGeometry(inner)


def main():
    fails = []
    control = compare(snapshot(build()), snapshot(build()))
    if control:
        fails.append("CONTROL: two unmutated builds compared as different: %s"
                     % "; ".join(control[:4]))
        print("[FAIL] diff_control_is_identical")
    else:
        print("[PASS] diff_control_is_identical")

    ref = snapshot(build())
    if not any(p for p in ref["packed"]):
        fails.append("packed recursion: `snapshot` descended into NO packed "
                     "prim, so `packed_contents` below is proved by the bounds "
                     "intrinsic alone and the contents are compared by nothing")
        print("[FAIL] diff_descends_into_packed")
    else:
        print("[PASS] diff_descends_into_packed")

    for name, mutate in MUTATIONS:
        geo = build()
        try:
            got = mutate(geo)             # a mutation may REBUILD instead
            geo = got if isinstance(got, hou.Geometry) else geo
        except Exception as exc:                                  # noqa: BLE001
            fails.append("%s: the mutation itself raised %s: %s"
                         % (name, type(exc).__name__, exc))
            print("[FAIL] diff_sees_%s (mutation raised)" % name)
            continue
        bad = compare(ref, snapshot(geo))
        if bad:
            print("[PASS] diff_sees_%-20s -> %s" % (name, bad[0][:88]))
        else:
            fails.append("%s: SURVIVED - `compare` called the mutated build "
                         "identical" % name)
            print("[FAIL] diff_sees_%s (SURVIVED)" % name)

    # STORAGE, the dimension `dataType()` is blind to (D246): fpreal32 vs 64
    # cannot be built with `addAttrib`, so it is asserted on the schema itself.
    lhs, rhs = snapshot(build()), snapshot(build())
    rhs["attribs"]["point"]["pc_local"]["storage"] = "numericData.Float64"
    if compare(lhs, rhs):
        print("[PASS] diff_sees_storage_width")
    else:
        fails.append("storage_width: SURVIVED - `numericDataType` is not read")
        print("[FAIL] diff_sees_storage_width")

    # And the tolerance is STATED at the magnitude it is applied at.
    lhs, rhs = snapshot(build()), snapshot(build())
    rhs["values"]["point"]["pc_local"][1] += 1e-6
    loose = compare(lhs, rhs, tol=1e-3)
    tight = compare(lhs, rhs, tol=1e-9)
    if loose or not tight:
        fails.append("tolerance: tol=1e-3 must admit a 1e-6 move and tol=1e-9 "
                     "must reject it; got %r / %r" % (loose[:1], tight[:1]))
        print("[FAIL] diff_tolerance_is_honoured")
    else:
        print("[PASS] diff_tolerance_is_honoured -> %s" % tight[-1][:80])

    # ...and 13.9 N6's `ulp` rule STOPS AT ONE ULP, which is the whole reason
    # it is allowed to exist.  A weakening that is not bounded is a tolerance,
    # and a tolerance nothing tests is a hole: this moves a value by exactly
    # one float32 ULP (must be admitted) and by two (must still be rejected).
    lhs, rhs = snapshot(build()), snapshot(build())
    base = lhs["values"]["point"]["pc_local"][1]
    one = ulp32(base)
    rhs["values"]["point"]["pc_local"][1] = base + one
    admits = compare(lhs, rhs, ulp=True)
    rhs["values"]["point"]["pc_local"][1] = base + 2.5 * one
    rejects = compare(lhs, rhs, ulp=True)
    exact = compare(lhs, rhs)
    if admits or not rejects or not exact:
        fails.append("ulp: one float32 ULP must be admitted and 2.5 rejected, "
                     "and ulp=False must reject both; got %r / %r / %r"
                     % (admits[:1], rejects[:1], exact[:1]))
        print("[FAIL] diff_ulp_rule_stops_at_one_ulp")
    else:
        print("[PASS] diff_ulp_rule_stops_at_one_ulp -> 1 ULP (%.3e) admitted, "
              "2.5 rejected" % one)

    print("\n%d mutation(s), %d failure(s)" % (len(MUTATIONS) + 3, len(fails)))
    for f in fails:
        print("  !! %s" % f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
