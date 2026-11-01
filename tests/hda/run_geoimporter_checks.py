"""pf_geoimporter checks. Run under plain python:   python tests/hda/run_geoimporter_checks.py [--hda other.hda] [--only m1,m2]
It copies the .hda to a temp folder (never edits the original), runs the checks in a throwaway hython session
(no .hip is ever saved), then re-runs them once per MUTATION and requires each to fail.

Fixtures are generated: a folder with .bgeo.sc files (one holds a packed prim of its own), an .obj, glTF files
written by the glTF ROP (.glb, and a .gltf with its _data.bin next to it) and a stray .txt, named a_ .. e_ so the
order mixes the formats. Oracle: each file through a plain File SOP (glTF ones unpacked) - the importer must give the same prims and
points per file, pf_enum = the file's place in the sorted paths, filepath on every prim, the glTF names kept.
Two more folders: one with a corrupt .bgeo.sc and one with a corrupt .glb (each import must come out empty, as it always did - never a partial
import where that file silently vanished; the error sits on the TOP nodes inside, not on the asset) and one with an upper-case .GLB (must be skipped: Houdini 22.0.442 segfaults reading it, so the
upper_case_glb_let_in mutation goes red by crashing, which is the very failure it guards).

What these checks CANNOT see: glTF hierarchies / instancing / node transforms (the fixtures are flat; an audit
compared a hand-made hierarchical glTF to numpy on 2026-11-01), formats other than bgeo.sc, obj and glTF, mixed-case
file names (order), glTF material attributes, cook speed, and the GUI (the TOP cook is forced here).
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HDA = os.path.join(ROOT, "polyfactory", "otls", "pf_geoimporter.hda")
HYTHON = "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/hython.exe"
SCRATCH = "F:/cache/polyfactory" if os.path.isdir("F:/cache") else None  # scratch stays off C: (global rule 23); else the system temp
CRASH_IS_RED = {"upper_case_glb_let_in"}  # its failure IS the Houdini crash; any other crash only counts with FAIL lines before it

# (name: (node path inside the asset, how it breaks)) - every one must turn the suite red
MUTATIONS = {
    "stray_files_reach_geo_import": ("topgeometry1/geo_only", "bypass", None),
    "failed_reads_ignored": ("topgeometry1/geometryimport", "emptygeometry", 1),
    "failed_gltf_reads_ignored": ("topgeometry1/geometryimport_gltf", "emptygeometry", 1),
    "geo_only_keeps_just_bgeo": ("topgeometry1/geo_only", "filterexpression", 'strmatch("*.bgeo.sc", pdgoutput(0, "file", 0)) == 0'),
    "gltf_branch_unplugged": ("topgeometry1/merge_imports", "input1", None),
    "geo_branch_dropped": ("topgeometry1/geometryimport_gltf", "display", None),
    "gltf_filter_bypassed": ("topgeometry1/gltf_only", "bypass", None),
    "gltf_import_takes_geo_tag": ("topgeometry1/geometryimport_gltf", "filetag", "file/geo"),
    "unpack_bypassed": ("unpack_gltf", "bypass", None),
    "unpack_everything": ("unpack_gltf", "group", ""),
    "unpack_drops_filepath": ("unpack_gltf", "transfer_attributes", "name"),
    "unpack_drops_gltf_names": ("unpack_gltf", "transfer_attributes", "filepath"),
    "upper_case_glb_let_in": ("topgeometry1/gltf_only", "filterregex", r"(?i).*\.(glb|gltf)$"),
}

FILES = ["a_box.bgeo.sc", "b_tube.glb", "c_packed.bgeo.sc", "d_sphere.gltf", "e_grid.obj"]


def inner(hda, mutation, scratch):
    import hou
    fails = []

    def check(ok, what):
        if not ok:
            fails.append(what)
            print("FAIL", what)

    work = tempfile.mkdtemp(prefix="work_", dir=scratch)
    geo = hou.node("/obj").createNode("geo", "fixtures")
    shapes = {"a": ("box", {}), "b": ("tube", {"type": 1, "rows": 4, "cols": 9}), "c": ("box", {}), "d": ("sphere", {"type": 2}), "e": ("grid", {"rows": 3, "cols": 4})}
    for f in FILES:
        kind, parms = shapes[f[0]]
        s = geo.createNode(kind, f[0])
        for k, v in parms.items():
            s.parm(k).set(v)
        xf = geo.createNode("xform", f[0] + "_x"); xf.setInput(0, s); xf.parm("tx").set(ord(f[0]) - 96)
        last = xf
        if f.startswith("c_"):  # a bgeo that carries its own packed prim next to polygons: must stay packed
            pk = geo.createNode("pack", "c_pack"); pk.setInput(0, xf)
            mg = geo.createNode("merge", "c_merge"); mg.setInput(0, pk); mg.setInput(1, s)
            last = mg
        path = os.path.join(work, f).replace("\\", "/")
        if ".bgeo" in f or f.endswith(".obj"):
            last.geometry().saveToFile(path)
        else:
            rop = geo.createNode("rop_gltf", f[0] + "_rop")
            rop.setInput(0, last)
            rop.parm("outputfile").set(path)
            rop.render()
        check(os.path.isfile(path), "fixture written: " + f)
    open(os.path.join(work, "notes.txt"), "w").write("not geometry")
    check(os.path.isfile(os.path.join(work, "d_sphere_data.bin")), "the .gltf fixture has its .bin next to it")

    hou.hda.installFile(hda)
    d = hou.hda.definitionsInFile(hda)[0]
    host = hou.node("/obj").createNode("geo", "host")
    imp = host.createNode(d.nodeTypeName(), "imp")
    if mutation:
        path, what, value = MUTATIONS[mutation]
        imp.allowEditingOfContents()
        node = imp.node(path)
        if what == "bypass":
            node.bypass(True)
        elif what == "display":
            node.setDisplayFlag(True)
        elif what == "input1":
            node.setInput(1, None)
        else:
            node.parm(what).set(value)

    def run(folder, pack):
        imp.parm("filepath").set(folder.replace("\\", "/") + "/*")
        imp.parm("pack").set(pack)
        try:
            imp.node("topgeometry1").displayNode().cookWorkItems(block=True)
            imp.cook(force=True)
        except hou.Error as e:
            return None, str(e)
        if imp.errors():  # what the artist sees: an error on the asset node
            return None, " ".join(imp.errors())
        return imp.geometry(), ""

    # oracle: a File SOP per file, glTF unpacked fully
    expect = {}
    for i, f in enumerate(FILES):
        fs = host.createNode("file", "o%d" % i)
        fs.parm("file").set(os.path.join(work, f).replace("\\", "/"))
        src = fs
        if ".gl" in f:
            src = host.createNode("unpack", "u%d" % i); src.setInput(0, fs); src.parm("limit_iterations").set(0)
        g = src.geometry()
        kinds = sorted(p.type().name() for p in g.prims())
        pts = sorted(tuple(round(c, 5) for c in p.position()) for p in g.points())
        expect[f] = (i, kinds, pts)
        if ".gl" in f:
            check("PackedGeometry" not in kinds and len(kinds) > 0, "oracle %s unpacked to polygons" % f)
    check("PackedGeometry" in expect["c_packed.bgeo.sc"][1], "fixture c_ carries a packed prim")

    g, err = run(work, 0)
    check(g is not None, "the mixed folder imports without error: " + err)
    if g is not None:
        by_file = {}
        for p in g.prims():
            fpth = p.attribValue("filepath") if g.findPrimAttrib("filepath") else ""
            by_file.setdefault(os.path.basename(fpth), []).append(p)
        check(sorted(by_file) == sorted(FILES), "every geometry file imported, nothing else (no .bin, no .txt): %s" % sorted(by_file))
        enum = g.findPointAttrib("pf_enum")
        check(enum is not None and enum.dataType() == hou.attribData.Int, "pf_enum is an int point attribute")
        for f, (idx, kinds, pts) in expect.items():
            prims = by_file.get(f, [])
            got_kinds = sorted(p.type().name() for p in prims)
            check(got_kinds == kinds, "%s: prims %d %s vs File SOP %d" % (f, len(got_kinds), sorted(set(got_kinds)), len(kinds)))
            ptset = {pt for p in prims for pt in ([p.points()[0]] if p.type().name() == "PackedGeometry" else p.points())}
            got_pts = sorted(tuple(round(c, 5) for c in pt.position()) for pt in ptset)
            check(got_pts == pts, "%s: point positions match the File SOP (%d vs %d)" % (f, len(got_pts), len(pts)))
            if enum is not None and ptset:
                vals = {pt.attribValue("pf_enum") for pt in ptset}
                check(vals == {idx}, "%s: pf_enum %s, want %d (its place in the sorted paths)" % (f, sorted(vals), idx))
            if ".gl" in f and prims:
                for a in ("gltf_node_name", "gltf_mesh_name", "name"):
                    names = {p.attribValue(a) for p in prims} if g.findPrimAttrib(a) else set()
                    check(names and "" not in names, "%s: glTF %s kept on its polygons: %s" % (f, a, sorted(names)[:3]))
        check(not [gr.name() for gr in g.primGroups() + g.pointGroups()], "no groups leak out")
        check(not [a.name() for a in g.primAttribs() + g.pointAttribs() + g.vertexAttribs() if a.name().startswith("_")], "no _ attributes leak out")

    g, err = run(work, 1)
    check(g is not None, "Pack Primitives imports without error: " + err)
    if g is not None:
        packs = [p for p in g.prims() if p.type().name() == "PackedGeometry"]
        check(len(packs) == len(g.prims()) == len(FILES), "Pack Primitives: one packed prim per file (%d prims)" % len(g.prims()))
        vals = sorted(pt.attribValue("pf_enum") for pt in g.points()) if g.findPointAttrib("pf_enum") else []
        check(vals == list(range(len(FILES))), "Pack Primitives: pf_enum 0..%d once each: %s" % (len(FILES) - 1, vals))

    # a geometry file that cannot be read must stop the import, never vanish
    for corrupt in ("b_corrupt.bgeo.sc", "b_corrupt.glb"):
        bad = tempfile.mkdtemp(prefix="bad_", dir=scratch)
        shutil.copy(os.path.join(work, "a_box.bgeo.sc"), bad)
        open(os.path.join(bad, corrupt), "wb").write(b"not a geometry file")
        g, err = run(bad, 0)
        check(g is None or len(g.prims()) == 0, "a corrupt %s empties the import as it always did, never a partial import (got %d prims)" % (corrupt, len(g.prims()) if g is not None else 0))

    # an upper-case .GLB is skipped (reading it crashes Houdini 22.0.442)
    up = tempfile.mkdtemp(prefix="upper_", dir=scratch)
    shutil.copy(os.path.join(work, "a_box.bgeo.sc"), up)
    shutil.copy(os.path.join(work, "b_tube.glb"), os.path.join(up, "e_torus.GLB"))
    g, err = run(up, 0)
    check(g is not None and {p.attribValue("filepath")[-12:] for p in g.prims()} == {"a_box.bgeo.sc"[-12:]},
          "an upper-case .GLB is skipped, the rest imports: " + err)

    print("checks failed: %d" % len(fails))
    return 1 if fails else 0


def main():
    hda = sys.argv[sys.argv.index("--hda") + 1] if "--hda" in sys.argv else HDA
    if "--inner" in sys.argv:
        mut = sys.argv[sys.argv.index("--inner") + 1]
        sys.exit(inner(hda, None if mut == "none" else mut, sys.argv[sys.argv.index("--scratch") + 1]))
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    tmp = tempfile.mkdtemp(prefix="pf_geoimp_hda_", dir=SCRATCH)
    copy = os.path.join(tmp, os.path.basename(hda))
    shutil.copy(hda, copy)

    def run(mut):  # -u: a crash must not swallow the FAIL lines printed before it; scratch removed even after a crash
        scratch = tempfile.mkdtemp(prefix="run_", dir=tmp)
        r = subprocess.run([HYTHON, "-u", os.path.abspath(__file__), "--hda", copy, "--inner", mut or "none", "--scratch", scratch], capture_output=True, text=True)
        shutil.rmtree(scratch, ignore_errors=True)
        return r.returncode, r.stdout + r.stderr
    code, out = (0, "") if only else run(None)
    print(out[-2500:] if code else "baseline: all checks pass")
    bad = code != 0
    for name in MUTATIONS:
        if only and name not in only:
            continue
        mc, mo = run(name)
        failed = "FAIL " in mo
        red = mc == 1 or (mc != 0 and (failed or name in CRASH_IS_RED))
        if not red:
            why = "CRASHED without a FAIL - unexplained" if mc != 0 else "STILL GREEN - the checks cannot see this"
        else:
            why = "red (good)" if mc == 1 else "red (good): crashed after FAIL lines" if failed else "red (good): the crash it guards"
        print("mutation %-28s %s" % (name, why))
        bad = bad or not red
    shutil.rmtree(tmp, ignore_errors=True)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
