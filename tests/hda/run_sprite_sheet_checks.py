"""
pf_sprite_sheet checks. Run under plain python:   python tests/hda/run_sprite_sheet_checks.py
It copies the shipped .hda to a temp folder (never edits the original), runs the checks in a throwaway
hython session (no .hip is ever saved), then re-runs them once per MUTATION and requires each to fail.

What these checks CANNOT see: the viewer (colour management of what you look at), the Image ROP / PNG
writer, the GUI parameter layout and callbacks (Read Grid button), sheets that are not an exact multiple
of the grid (Crop rounds), and cook speed. Colour values are exact only with the file read as Raw (a
fixture decision); one separate check covers the default sRGB decode to within 0.01.
"""
import os, shutil, struct, subprocess, sys, tempfile, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
HDA = os.path.join(ROOT, "polyfactory", "otls", "pf_sprite_sheet.hda")
HYTHON = "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/hython.exe"

# (name, how it breaks the shipped asset) - every one must turn the suite red
MUTATIONS = {
    "row_flip": ("py", '(rows - 1 - row)', 'row'),
    "pingpong_no_mirror": ("py", 'u = period - u', 'u = u'),
    "hold_wraps": ("py", 'u = max(0.0, min(t, float(last)))', 'u = t % used'),
    "blend_mix_inverted": ("py", "return a, b, (u - math.floor(u)) if int(n.evalParm(\"blend\")) else 0.0",
                           "return a, b, (1.0 - (u - math.floor(u))) if int(n.evalParm(\"blend\")) else 0.0"),
    "sheet_bottom_to_top": ("node", "sheet_grid", "stackvertical", 1),
    "blend_inputs_swapped": ("swap", "blend_cells"),
    "file_premult_inverted": ("expr", "sheet_file", "premultiplied", '1 - ch("../premult")'),
    "frames_used_ignored": ("py", "used = int(n.evalParm(\"frames\")) or cols * rows", "used = cols * rows"),
    "loop_b_is_a": ("py", "b = (a + 1) % used", "b = a"),
    "pingpong_b_is_a": ("py", "b = min(a + 1, last)", "b = a", 1),
    "hold_b_is_a": ("py", "b = min(a + 1, last)", "b = a", 2),
    "loop_ignores_frames_used": ("py", "u = t % used", "u = t % (cols * rows)"),
    "pingpong_hold_ignore_frames_used": ("py", "last = used - 1", "last = cols * rows - 1"),
    "frames_used_not_clamped": ("py", "max(1, min(used, cols * rows))", "max(1, used)"),
    "pingpong_negative_time_clamped": ("py", "t % period", "max(t, 0) % period"),
    "read_grid_swaps_cols_rows": ("py", 'n.parm("cols").set(cols)', 'n.parm("cols").set(rows)'),
    "make_info_miscounts": ("py", "count, cols = make_count(n), make_cols(n)", "count, cols = make_count(n) + 1, make_cols(n)"),
    "make_cols_uncapped": ("py", "return min(c, count) if c > 0", "return c if c > 0"),
    "time_uses_F_not_FF": ("hdaexpr", "_t", '($F-ch("startframe"))/$FPS*ch("sheetfps")'),
    "sheet_background_opaque": ("node", "sheet_grid", "backgrounda", 1),
    "auto_cols_rounds": ("py", "int(math.ceil(math.sqrt(count)))", "int(round(math.sqrt(count)))"),
    "auto_cols_floor_plus_one": ("py", "int(math.ceil(math.sqrt(count)))", "int(math.sqrt(count)) + 1"),
    "info_never_plural": ("py", '"" if cols == 1 else "s"', '""'),
    "make_end_not_nudged": ("expr", "pack_frames", "absrangeframe2", 'ch("../rangeend")'),
    "make_end_before_start_unguarded": ("py", "return max(n.evalParm(\"rangeend\"), n.evalParm(\"rangestart\")) + 1e-3 * step", "return n.evalParm(\"rangeend\") + 1e-3 * step"),
}

CELL_W, CELL_H, COLS, ROWS = 16, 12, 4, 3


def png(path, w, h, px):
    """Write an 8-bit RGBA PNG; px[y][x] = (r, g, b, a), y = 0 at the top."""
    raw = b"".join(b"\x00" + bytes(c for p in row for c in p) for row in px)
    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def cell_colour(i):
    return (20 + 18 * i, 40, 200 - 10 * i, 255)


def make_sheet(path):
    px = [[(0, 0, 0, 0)] * (CELL_W * COLS) for _ in range(CELL_H * ROWS)]
    for i in range(COLS * ROWS):
        c, r = i % COLS, i // COLS
        col = cell_colour(i)
        if i == 11:
            col = (100, 40, 100, 128)         # a premultiplied half-transparent cell
        for y in range(CELL_H):
            for x in range(CELL_W):
                px[r * CELL_H + y][c * CELL_W + x] = col
        px[r * CELL_H][c * CELL_W] = (255, 255, 255, 255)   # marker: top-left pixel of the cell
    png(path, CELL_W * COLS, CELL_H * ROWS, px)


def inner(mutation):
    import hou
    fails = []

    def check(ok, what):
        if not ok:
            fails.append(what)
            print("FAIL", what)

    work = tempfile.mkdtemp(prefix="pf_sprite_")
    hda = os.path.join(work, "pf_sprite_sheet.hda")
    shutil.copy(HDA, hda)                      # never edit the shipped file
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(hda)
    nt = hou.nodeType(hou.copNodeTypeCategory(), "pf_sprite_sheet")
    m = MUTATIONS.get(mutation)
    if m and m[0] == "py":
        d = nt.definition()
        src = d.sections()["PythonModule"].contents()
        nth = m[3] if len(m) > 3 else 1
        at_ = -1
        for _ in range(nth):
            at_ = src.find(m[1], at_ + 1)
            assert at_ >= 0, "mutation target missing: " + m[1]
        d.addSection("PythonModule", src[:at_] + m[2] + src[at_ + len(m[1]):])
    sheet = os.path.join(work, "sheet.png")
    make_sheet(sheet)
    cn = (hou.node("/img") or hou.node("/").createNode("img", "img")).createNode("copnet", "t")

    def sprite(name="s"):
        n = cn.createNode("pf_sprite_sheet", name)
        n.allowEditingOfContents()
        n.node("sheet_file").parm("colorspace").set(1)       # Raw: exact values (fixture decision)
        if m and m[0] == "node":
            n.node(m[1]).parm(m[2]).set(m[3])
        if m and m[0] == "hdaexpr":
            n.parm(m[1]).setExpression(m[2], language=hou.exprLanguage.Hscript)
        if m and m[0] == "expr":
            n.node(m[1]).parm(m[2]).setExpression(m[3], language=hou.exprLanguage.Hscript)
        if m and m[0] == "swap":
            b = n.node(m[1]); a_, b_ = b.input(0), b.input(1)
            b.setInput(0, b_); b.setInput(1, a_)
        return n

    def layer(n):
        try:
            n.cook(force=False)
        except hou.OperationFailed:
            pass
        errs = n.errors() + tuple(c.name() + ": " + e for c in n.allSubChildren() for e in c.errors())
        check(not errs, "%s cooks without errors: %s" % (n.name(), errs))
        return n.layer(0)

    def at(L, x, y):
        return L.bufferIndexV4(x, y)

    def near(a, b, tol, what):
        check(all(abs(p - q) <= tol for p, q in zip(a, b)), "%s: got %s want %s (tol %s)" % (what, tuple(round(v, 4) for v in a), tuple(round(v, 4) for v in b), tol))

    def setc(n, name, value):
        """Set a parm that carries a default expression ($FSTART...) to a plain value."""
        n.parm(name).deleteAllKeyframes()
        n.parm(name).set(value)

    # tolerance for 8-bit PNG values: half a level
    TOL = 0.5 / 255 + 1e-4

    # ---- Extract: every cell, exact colour, size, orientation
    ex = sprite("extract")
    ex.parm("mode").set(1); ex.parm("file").set(sheet); ex.parm("premult").set(1)   # Straight: opaque cells are unaffected either way
    ex.parm("cols").set(COLS); ex.parm("rows").set(ROWS)
    for i in range(COLS * ROWS - 1):
        ex.parm("frame").set(i)
        L = layer(ex)
        check(tuple(L.bufferResolution()) == (CELL_W, CELL_H), "extract %d size %s" % (i, L.bufferResolution()))
        want = [v / 255.0 for v in cell_colour(i)]
        near(at(L, CELL_W // 2, CELL_H // 2), want, TOL, "extract %d centre" % i)
        near(at(L, CELL_W - 1, CELL_H - 1), (1, 1, 1, 1), TOL, "extract %d marker sits at the cell's top-left" % i) if False else None
    # orientation inside the cell: the marker is the top-left pixel of the picture. Find which buffer corner holds white.
    ex.parm("frame").set(5)
    L = layer(ex)
    corners = {c: at(L, *c)[:3] == (1.0, 1.0, 1.0) or min(at(L, *c)[:3]) > 0.99 for c in ((0, 0), (CELL_W - 1, 0), (0, CELL_H - 1), (CELL_W - 1, CELL_H - 1))}
    check(sum(corners.values()) == 1 and corners[(0, CELL_H - 1)], "marker is only in the top-left of the cell: %s" % corners)
    # frames used clamps the frame index
    ex.parm("frames").set(6); ex.parm("frame").set(9)
    near(at(layer(ex), CELL_W // 2, CELL_H // 2), [v / 255.0 for v in cell_colour(5)], TOL, "Frames Used 6 clamps frame 9 to cell 5")
    ex.parm("frames").set(0)
    # premultiplied cell: stored (100,40,100,128) read as Premultiplied comes out un-premultiplied
    ex.parm("premult").set(0); ex.parm("frame").set(11)
    near(at(layer(ex), CELL_W // 2, CELL_H // 2), (100 / 255.0, 40 / 255.0, 100 / 255.0, 128 / 255.0), 0.003, "a premultiplied file is taken as it is")
    ex.parm("premult").set(1)
    near(at(layer(ex), CELL_W // 2, CELL_H // 2), (100 / 255.0 * 128 / 255.0, 40 / 255.0 * 128 / 255.0, 100 / 255.0 * 128 / 255.0, 128 / 255.0), 0.003, "a straight file is premultiplied on load (Copernicus layers are premultiplied)")
    ex.parm("premult").set(0)
    # default colour management (sRGB decode) differs from raw for a mid-grey; it must not be raw
    ex.node("sheet_file").parm("colorspace").set(0); ex.parm("premult").set(1); ex.parm("frame").set(0)
    v = at(layer(ex), CELL_W // 2, CELL_H // 2)
    near(v[:1], (((cell_colour(0)[0] / 255.0 + 0.055) / 1.055) ** 2.4,), 0.01, "default file colour is sRGB-decoded")
    ex.node("sheet_file").parm("colorspace").set(1)

    # ---- Play: one cell per timeline frame, loop / ping-pong / hold, blend between cells
    pl = sprite("play")
    pl.parm("mode").set(0); pl.parm("file").set(sheet); pl.parm("premult").set(1)
    pl.parm("cols").set(COLS); pl.parm("rows").set(ROWS); setc(pl, "startframe", 1); pl.parm("sheetfps").set(hou.fps()); pl.parm("blend").set(0)

    reds = [cell_colour(i)[0] / 255.0 for i in range(11)] + [100 / 255.0 * 128 / 255.0]     # cell 11 is the half-transparent one, read Straight

    def shown(frame):
        hou.setFrame(frame)
        r = at(layer(pl), CELL_W // 2, CELL_H // 2)[0]
        best = min(range(12), key=lambda i: abs(reds[i] - r))
        return best if abs(reds[best] - r) < 0.002 else None

    def seq(loop, frames):
        pl.parm("loop").set(loop)
        return [shown(f) for f in frames]

    pl.parm("loop").set(0)
    got = [shown(f) for f in (1, 2, 3, 11, 12, 13, 14)]
    check(got == [0, 1, 2, 10, 11, 0, 1], "loop order: %s" % got)
    pl.parm("loop").set(1)
    got = [shown(f) for f in (1, 11, 13, 14, 15, 23, 24, 25)]
    check(got == [0, 10, 10, 9, 8, 0, 1, 2], "ping-pong order: %s" % got)
    pl.parm("loop").set(2)
    got = [shown(f) for f in (1, 5, 11, 40)]
    check(got == [0, 4, 10, 11], "hold last frame: %s" % got)
    # negative time (before Start Frame 1)
    for loop, want in ((0, [11, 10, 11]), (1, [1, 2, 9]), (2, [0, 0, 0])):
        got = seq(loop, (0, -1, -12))
        check(got == want, "loop mode %d before Start Frame: %s want %s" % (loop, got, want))
    # Frames Used = 5 of 12 stops every mode at cell 4; 99 is clamped to the 12 cells
    pl.parm("frames").set(5)
    for loop, want in ((0, [0, 1, 2, 3, 4, 0, 1, 2, 3, 4, 0]), (1, [0, 1, 2, 3, 4, 3, 2, 1, 0, 1, 2]), (2, [0, 1, 2, 3, 4, 4, 4, 4, 4, 4, 4])):
        got = seq(loop, range(1, 12))
        check(got == want, "Frames Used 5, loop mode %d: %s want %s" % (loop, got, want))
    pl.parm("frames").set(99)
    got = seq(2, (14, 40))        # Hold: a Frames Used above the grid must stop at the last of the 12 cells (a wrap-around crop would hide a miss in Loop)
    check(got == [11, 11], "Frames Used 99 is clamped to the 12 cells: %s" % got)
    pl.parm("frames").set(0)
    pl.parm("loop").set(0); setc(pl, "startframe", 5)
    got = [shown(f) for f in (5, 6, 1)]
    check(got == [0, 1, 8], "Start Frame shifts the sheet (before it, a loop runs from the end): %s" % got)
    setc(pl, "startframe", 1); pl.parm("sheetfps").set(hou.fps() / 2.0); pl.parm("blend").set(1)
    hou.setFrame(2)                                  # half a cell after cell 0 -> halfway between cell 0 and 1
    a, b = cell_colour(0)[0] / 255.0, cell_colour(1)[0] / 255.0
    near(at(layer(pl), CELL_W // 2, CELL_H // 2)[:1], ((a + b) / 2,), 0.003, "blend halfway between neighbouring cells")
    hou.setFrame(1)
    near(at(layer(pl), CELL_W // 2, CELL_H // 2)[:1], (a,), 0.003, "blend at a whole cell shows that cell")
    # the neighbour cell at the loop wrap, the ping-pong turnaround and the hold end (half speed, Blend on)
    def red_at(frame):
        hou.setFrame(frame)
        return at(layer(pl), CELL_W // 2, CELL_H // 2)[0]
    mean = lambda i, j: (reds[i] + reds[j]) / 2.0
    pl.parm("loop").set(0)
    near((red_at(24),), (mean(11, 0),), 0.003, "loop wrap blends the last cell into the first")
    pl.parm("loop").set(1)
    near((red_at(24),), (mean(10, 11),), 0.003, "ping-pong turnaround blends back from the last cell")
    pl.parm("loop").set(2)
    near((red_at(22),), (mean(10, 11),), 0.003, "hold blends up to the last cell")
    near((red_at(26),), (reds[11],), 0.003, "hold stays on the last cell")
    pl.parm("loop").set(0)
    pl.parm("sheetfps").set(hou.fps())
    near((red_at(2.5),), (mean(1, 2),), 0.003, "a fractional timeline frame (2.5) blends cells 1 and 2")
    pl.parm("sheetfps").set(hou.fps() / 4.0)
    hou.setFrame(2)                                  # a quarter of the way from cell 0 to 1: closer to cell 0
    near(at(layer(pl), CELL_W // 2, CELL_H // 2)[:1], (a + 0.25 * (b - a),), 0.003, "blend a quarter way is nearer the first cell")
    pl.parm("blend").set(0)
    near(at(layer(pl), CELL_W // 2, CELL_H // 2)[:1], (a,), 0.003, "Blend off shows whole cells")
    hou.setFrame(1)

    # ---- Make: a timeline range becomes a sheet; wired to Extract it comes back
    k = cn.createNode("constant", "anim")
    for p_, e in (("f4r", "$FF/20"), ("f4g", "0.5"), ("f4b", "0.25"), ("f4a", "1")):
        k.parm(p_).setExpression(e, language=hou.exprLanguage.Hscript)
    k.parm("signature").set("f4")      # the Constant COP's RGBA signature
    mk = sprite("make")
    mk.setInput(0, k)
    mk.parm("mode").set(2); setc(mk, "rangestart", 1); setc(mk, "rangeend", 6); mk.parm("step").set(1); mk.parm("makecols").set(3)
    L = layer(mk)
    kres = tuple(layer(k).bufferResolution()) if False else None
    cw, ch = L.bufferResolution()[0] // 3, L.bufferResolution()[1] // 2
    check(L.bufferResolution() == (cw * 3, ch * 2), "6 frames in 3 columns make 3 x 2 cells: %s" % (L.bufferResolution(),))
    for i in range(6):
        cx, cy = (i % 3) * cw + cw // 2, (1 - i // 3) * ch + ch // 2     # reading order, first row on top
        near(at(L, cx, cy), ((i + 1) / 20.0, 0.5, 0.25, 1.0), 0.003, "make cell %d is timeline frame %d" % (i, i + 1))
    mk.parm("makecols").set(0); setc(mk, "rangeend", 6); mk.parm("step").set(2)           # frames 1, 3, 5 -> auto 2 columns x 2 rows
    L = layer(mk)
    check(L.bufferResolution() == (cw * 2, ch * 2), "step 2 over 1..6 is 3 frames in an auto 2 x 2 grid: %s" % (L.bufferResolution(),))
    near(at(L, cw + cw // 2, ch + ch // 2), (3 / 20.0, 0.5, 0.25, 1.0), 0.003, "second cell is frame 3")
    near(at(L, cw // 2, ch // 2), (5 / 20.0, 0.5, 0.25, 1.0), 0.003, "third cell (second row) is frame 5")
    mk.parm("step").set(1); mk.parm("makecols").set(3); mk.parm("cellresize").set(1); mk.parm("cellresx").set(40); mk.parm("cellresy").set(20)
    L = layer(mk)
    check(L.bufferResolution() == (120, 40), "Resize Cells 40 x 20, 3 x 2: %s" % (L.bufferResolution(),))
    mk.parm("cellresize").set(0)
    # the number of cells Make produces equals what the label and the columns are computed from
    mk.parm("cellresize").set(1); mk.parm("cellresx").set(16); mk.parm("cellresy").set(16)     # small cells: 91 of them stay under the size limit
    kres = (16, 16)
    mk.parm("makecols").set(1)
    for rs, re_, st in ((1, 2, 0.1), (1, 10, 0.1), (1, 10, 3), (5, 5, 1), (1, 24, 0.5), (3, 9, 2.5), (1, 6, 1), (2, 3, 0.3)):
        setc(mk, "rangestart", rs); setc(mk, "rangeend", re_); mk.parm("step").set(st)
        L = layer(mk)
        count = L.bufferResolution()[1] // kres[1]
        check(count == mk.hdaModule().make_count(mk), "range %s..%s step %s: sheet has %d cells, make_count says %d" % (rs, re_, st, count, mk.hdaModule().make_count(mk)))
        want_last = rs + (count - 1) * st
        near(at(L, kres[0] // 2, kres[1] // 2), (want_last / 20.0, 0.5, 0.25, 1.0), 0.003, "range %s..%s step %s: last cell is frame %s" % (rs, re_, st, want_last))
    mk.parm("step").set(1); setc(mk, "rangestart", 1); setc(mk, "rangeend", 5); mk.parm("makecols").set(3)       # 5 frames in 3 columns: the 6th cell is empty
    L = layer(mk)
    check(L.bufferResolution() == (48, 32), "5 frames in 3 columns of 16 px: %s" % (L.bufferResolution(),))
    near(at(L, 40, 8), (0.0, 0.0, 0.0, 0.0), 0.001, "the unused cell is transparent")
    mk.parm("makecols").set(0)
    for count, want in ((1, 1), (2, 2), (4, 2), (5, 3), (7, 3), (10, 4)):
        setc(mk, "rangeend", count)
        got = (mk.hdaModule().make_cols(mk), layer(mk).bufferResolution()[0] // 16)
        check(got == (want, want), "auto columns for %d frames: %s want %d" % (count, got, want))
    setc(mk, "rangeend", 6); mk.parm("makecols").set(3)
    check(mk.hdaModule().make_info(mk) == "6 frames in 3 columns x 2 rows", "label: %s" % mk.hdaModule().make_info(mk))
    mk.parm("makecols").set(1)
    setc(mk, "rangestart", 5); setc(mk, "rangeend", 2); mk.parm("step").set(1)                 # end before start: one cell, frame 5, not black
    L = layer(mk)
    check(L.bufferResolution() == tuple(kres), "end before start gives one cell: %s" % (L.bufferResolution(),))
    near(at(L, 2, 2), (5 / 20.0, 0.5, 0.25, 1.0), 0.003, "end before start shows the start frame")
    check(mk.hdaModule().make_info(mk).startswith("Range End is before Range Start"), "the label says so: %s" % mk.hdaModule().make_info(mk))
    mk.parm("cellresize").set(0)
    setc(mk, "rangeend", 5); mk.parm("makecols").set(5)
    check(mk.hdaModule().make_info(mk) == "1 frame in 1 column x 1 row", "label with more columns than frames: %s" % mk.hdaModule().make_info(mk))
    setc(mk, "rangestart", 1); setc(mk, "rangeend", 6); mk.parm("makecols").set(3)

    # union: the sheet made from the timeline, extracted again, is the same frames
    ex2 = sprite("again")
    ex2.setInput(0, mk)
    ex2.parm("mode").set(1); ex2.parm("source").set(1); ex2.parm("cols").set(3); ex2.parm("rows").set(2)
    for i in range(6):
        ex2.parm("frame").set(i)
        near(at(layer(ex2), 2, 2), ((i + 1) / 20.0, 0.5, 0.25, 1.0), 0.003, "make -> extract round trip, frame %d" % i)

    # Read Grid button: sidecar first, then manifest.json; speed from duration
    import json
    rg = sprite("readgrid")
    rg.parm("file").set(sheet)
    json.dump({"file": "sheet.png", "cols": 2, "rows": 6, "frames": 11, "duration_s": 1.0}, open(os.path.join(work, "sheet.atlas.json"), "w"))
    rg.parm("readgrid").pressButton()
    got = (rg.parm("cols").eval(), rg.parm("rows").eval(), rg.parm("frames").eval(), round(rg.parm("sheetfps").eval(), 3))
    check(got == (2, 6, 11, 11.0), "Read Grid from .atlas.json: %s" % (got,))
    os.remove(os.path.join(work, "sheet.atlas.json"))
    json.dump([{"file": "other.png", "cols": 9, "rows": 9}, {"file": "SHEET.png", "cols": 3, "rows": 4, "frames": 12, "duration_s": 2.0}], open(os.path.join(work, "manifest.json"), "w"))
    rg.parm("readgrid").pressButton()
    got = (rg.parm("cols").eval(), rg.parm("rows").eval(), rg.parm("frames").eval(), round(rg.parm("sheetfps").eval(), 3))
    check(got == (3, 4, 0, 6.0), "Read Grid from manifest.json: %s" % (got,))

    # Make -> Image ROP (PNG alpha option "Raw") -> file -> Extract (Premultiplied): a half-alpha pixel comes back unchanged
    half = cn.createNode("constant", "half")
    half.parm("signature").set("f4")
    for p_, v in (("f4r", 0.2), ("f4g", 0.1), ("f4b", 0.05), ("f4a", 0.5)):
        half.parm(p_).set(v)
    one = sprite("one_frame")
    one.setInput(0, half)
    one.parm("mode").set(2); setc(one, "rangestart", 1); setc(one, "rangeend", 1)
    rop = cn.createNode("rop_image", "w")
    out_png = os.path.join(work, "made.png").replace("\\", "/")
    rop.parm("coppath").set(one.path()); rop.parm("copoutput").set(out_png); rop.parm("trange").set(0)
    labels = list(rop.parm("pngtga_alpha_multiplication").menuLabels())
    rop.parm("pngtga_alpha_multiplication").set(labels.index("Raw"))
    rop.parm("execute").pressButton()
    check(os.path.isfile(out_png), "Image ROP wrote the PNG")
    if os.path.isfile(out_png):
        back = sprite("read_back")
        back.node("sheet_file").parm("colorspace").set(0)        # the default decode, as the ROP encoded it
        back.parm("mode").set(1); back.parm("file").set(out_png); back.parm("premult").set(0)
        back.parm("cols").set(1); back.parm("rows").set(1)
        near(at(layer(back), 4, 4), (0.2, 0.1, 0.05, 0.5), 0.004, "Make -> Image ROP (Raw) -> Extract (Premultiplied) round trip")

    print("checks failed: %d" % len(fails))
    return 1 if fails else 0


def main():
    if "--inner" in sys.argv:
        mut = sys.argv[sys.argv.index("--inner") + 1]
        sys.exit(inner(None if mut == "none" else mut))
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None

    def run(mut):
        r = subprocess.run([HYTHON, os.path.abspath(__file__), "--inner", mut or "none"], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr
    code, out = (0, "") if only else run(None)
    print(out[-1500:] if code else "baseline: all checks pass")
    bad = code != 0
    for name in MUTATIONS:
        if only and name not in only:
            continue
        mc, mo = run(name)
        status = "red (good)" if mc != 0 else "STILL GREEN - the checks cannot see this"
        print("mutation %-24s %s" % (name, status))
        if mc == 0:
            bad = True
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
