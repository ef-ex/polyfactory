"""
create_pf_sprite_sheet_hda.py - Build pf_sprite_sheet.hda for Houdini Copernicus (COP).

One node, three jobs (Mode menu):
  Play     - a sprite sheet (a file, or any layer wired in) plays on the timeline.
  Extract  - one frame of a sprite sheet comes out as its own layer.
  Make     - a range of the timeline, rendered by whatever is wired in, becomes one sprite sheet.

Native nodes only for the pixels (File, Crop, Blend, Time Pack, Contact Sheet, Resample, Premultiply,
Switch). Python is used for two things, named in ideas/sprite_sheet.md: parameter expressions that turn
(time, loop mode, grid) into a cell index, and the "Read Grid from Sheet JSON" button (file IO).

Build:  hython devScripts/create_pf_sprite_sheet_hda.py
"""
import hou, os

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_sprite_sheet.hda").replace("\\", "/")
NAME = "pf_sprite_sheet"

PYTHON_MODULE = r'''
import json, math, os
import hou

# Parameter-expression helpers for pf_sprite_sheet. Pure functions of the HDA's own parameters;
# the pixels are moved by native COP nodes (see ideas/sprite_sheet.md, decision log).

def grid(n):
    """(cols, rows, frames used) of the sheet, each at least 1, frames within the grid."""
    cols = max(1, int(n.evalParm("cols")))
    rows = max(1, int(n.evalParm("rows")))
    used = int(n.evalParm("frames")) or cols * rows
    return cols, rows, max(1, min(used, cols * rows))

def index(n):
    """(frame a, frame b, mix a->b): the cells to show now. mix is 0 unless Play with Blend on."""
    cols, rows, used = grid(n)
    mode = int(n.evalParm("mode"))
    if mode == 1:
        return max(0, min(int(n.evalParm("frame")), used - 1)), 0, 0.0
    t = n.evalParm("_t")                       # sheet frames elapsed since Start Frame (float)
    loop = int(n.evalParm("loop"))
    last = used - 1
    if loop == 0:                              # Loop
        u = t % used
        a = int(math.floor(u))
        b = (a + 1) % used
    elif loop == 1:                            # Ping-Pong
        period = 2 * last
        u = 0.0 if period <= 0 else t % period
        if u > last:
            u = period - u
        a = int(math.floor(u))
        b = min(a + 1, last)
    else:                                      # Hold last frame
        u = max(0.0, min(t, float(last)))
        a = int(math.floor(u))
        b = min(a + 1, last)
    a = max(0, min(a, last))
    return a, b, (u - math.floor(u)) if int(n.evalParm("blend")) else 0.0

def cell(n, which, comp, size=False):
    """One component of the Crop box (texture units, origin bottom-left) of frame a (which=0) or b."""
    cols, rows, used = grid(n)
    i = index(n)[which] if int(n.evalParm("mode")) < 2 else 0
    if size:
        return (1.0 / cols, 1.0 / rows)[comp]
    col, row = i % cols, i // cols
    return (col / float(cols), (rows - 1 - row) / float(rows))[comp]

def mix(n):
    return index(n)[2]

def make_end(n):
    """Last frame handed to Time Pack: Range End (never before Range Start), nudged (by a thousandth of a step: Time Pack
    keeps its range as float32) so a fractional step that lands on it (1..2 step 0.1) keeps the end frame."""
    step = max(1e-6, n.evalParm("step"))
    return max(n.evalParm("rangeend"), n.evalParm("rangestart")) + 1e-3 * step

def make_count(n):
    """Frames Time Pack will sample: the same count formula as Time Pack, on make_end."""
    step = max(1e-6, n.evalParm("step"))
    return int(math.floor((make_end(n) - n.evalParm("rangestart")) / step)) + 1

def make_cols(n):
    count = make_count(n)
    c = int(n.evalParm("makecols"))
    return min(c, count) if c > 0 else int(math.ceil(math.sqrt(count)))

def make_info(n):
    count, cols = make_count(n), make_cols(n)
    rows = -(-count // cols)
    text = "%d frame%s in %d column%s x %d row%s" % (count, "" if count == 1 else "s", cols, "" if cols == 1 else "s", rows, "" if rows == 1 else "s")
    if n.evalParm("rangeend") < n.evalParm("rangestart"):
        text = "Range End is before Range Start: " + text
    return text

def read_grid(kwargs):
    """Button: take cols / rows / frames / speed from <sheet>.atlas.json or the sheet's entry in manifest.json."""
    n = kwargs["node"]
    path = hou.text.expandString(n.evalParm("file"))
    if not path:
        return False                       # nothing loaded: do not go looking for ./manifest.json
    folder, name = os.path.split(path)
    own = os.path.splitext(path)[0] + ".atlas.json"
    entry = None
    if os.path.isfile(own):
        entry = json.load(open(own, encoding="utf-8"))
    elif os.path.isfile(os.path.join(folder, "manifest.json")):
        for e in json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8")):
            if str(e.get("file", "")).lower() == name.lower():
                entry = e
                break
    if not entry or not entry.get("cols") or not entry.get("rows"):
        hou.ui.displayMessage("No .atlas.json beside the sheet and no entry in a manifest.json there. "
                              "Set Columns and Rows by hand.", severity=hou.severityType.Warning) if hou.isUIAvailable() else None
        return False
    cols, rows = int(entry["cols"]), int(entry["rows"])
    frames = max(1, min(int(entry.get("frames") or cols * rows), cols * rows))
    n.parm("cols").set(cols)
    n.parm("rows").set(rows)
    n.parm("frames").set(frames if frames != cols * rows else 0)
    if entry.get("duration_s"):
        n.parm("sheetfps").set(frames / float(entry["duration_s"]))
    return True
'''

HELP_TEXT = """= PF Sprite Sheet =

#type: node
#context: cop
#internal: pf_sprite_sheet
#icon: COP/contactsheet

\"\"\"Plays a sprite sheet, extracts one frame of it, or makes a sprite sheet from a range of the timeline.\"\"\"

A sprite sheet (atlas, flipbook texture) is one image holding an animation as a grid of equal cells,
read left to right, top to bottom. Pick what you want with *Mode*.

*Play* shows the sheet as an animation on the timeline: it starts at *Start Frame*, runs at *Sheet Speed*,
and loops, ping-pongs or holds its last frame. *Blend Between Frames* mixes neighbouring cells so a slow
sheet plays smoothly on a fast timeline.

*Extract Frame* outputs one cell of the sheet as its own layer, the size of one cell.

*Make Sprite Sheet* samples whatever is wired into the input at every frame of a range and packs the frames
into one sheet. Size the cells with *Resize Cells*. The result is an ordinary Copernicus layer (premultiplied, like
every RGBA layer here). To write it, wire an *Image ROP* to it: set the ROP's _PNG/TGA alpha_ option to *Raw* to
get a premultiplied file (flipbook textures, and what Colour In File = Premultiplied reads back unchanged), or to
*Unpremultiply if needed* for an ordinary straight-alpha PNG (read it back with Colour In File = Straight).
Use the same colour space on the ROP and on the File that reads it again.

The sheet is a file, or any layer wired into the input. If a `.atlas.json` sits beside the file, or the folder has a
`manifest.json` listing it, *Read Grid from Sheet JSON* fills Columns, Rows, Frames and Speed.

@parameters
    Mode:
        #id: mode
        Play the sheet, extract one frame, or make a sheet from the timeline.
    Sheet From:
        #id: source
        Load a file, or use the layer wired into the input.
    Sheet File:
        #id: file
        The image file holding the sprite sheet.
    Colour In File:
        #id: premult
        Premultiplied if the colour was multiplied by alpha (flipbooks shot on black usually are), else Straight.
    Columns:
        #id: cols
        Cells across.
    Rows:
        #id: rows
        Cells down.
    Frames Used:
        #id: frames
        How many cells are frames; 0 means all of them. The rest of the last row may be empty.
    Start Frame:
        #id: startframe
        The timeline frame where the sheet's first cell shows.
    Sheet Speed:
        #id: sheetfps
        Cells per second.
    Loop:
        #id: loop
        What happens at the end: loop, ping-pong, or hold the last cell.
    Blend Between Frames:
        #id: blend
        Mix the two neighbouring cells by how far the time is between them.
    Frame:
        #id: frame
        The cell to extract, counting from 0 (top-left, reading order).
    Range Start:
        #id: rangestart
        The first timeline frame to pack.
    Range End:
        #id: rangeend
        The last timeline frame to pack. It defaults to the end of the playback range, so set it before making a sheet.
    Step:
        #id: step
        Frames between samples.
    Columns (0 = auto):
        #id: makecols
        Cells per row of the new sheet; 0 makes it about square. Never more than the number of frames.
    Cell Size:
        #id: cellres
        The size every frame is scaled to when Resize Cells is on.
    Resize Cells:
        #id: cellresize
        Scale every frame to the Cell Size before packing.

@inputs
    Image:
        The sprite sheet (Sheet From: Input), or the animation to pack (Make).

@related
    - [Node:cop/timepack]
    - [Node:cop/contactsheet]
    - [Node:cop/crop]
"""


def _ptg():
    P = hou.parmTemplateType
    g = hou.ParmTemplateGroup()

    def cond(t, expr, kind=hou.parmCondType.HideWhen):
        t.setConditional(kind, expr)
        return t

    g.append(hou.MenuParmTemplate("mode", "Mode", ("play", "frame", "make"),
                                  menu_labels=("Play Sprite Sheet", "Extract Frame", "Make Sprite Sheet"), default_value=0))
    g.append(cond(hou.MenuParmTemplate("source", "Sheet From", ("file", "input"), menu_labels=("File", "Input"), default_value=0), "{ mode == 2 }"))
    f = hou.StringParmTemplate("file", "Sheet File", 1, default_value=("",), string_type=hou.stringParmType.FileReference,
                               file_type=hou.fileType.Image)
    g.append(cond(f, "{ mode == 2 } { source != 0 }"))
    g.append(cond(hou.MenuParmTemplate("premult", "Colour In File", ("on", "off"), menu_labels=("Premultiplied", "Straight"), default_value=0),
                  "{ mode == 2 } { source != 0 }"))
    g.append(cond(hou.IntParmTemplate("cols", "Columns", 1, default_value=(8,), min=1, max=64, min_is_strict=True), "{ mode == 2 }"))
    g.append(cond(hou.IntParmTemplate("rows", "Rows", 1, default_value=(8,), min=1, max=64, min_is_strict=True), "{ mode == 2 }"))
    g.append(cond(hou.IntParmTemplate("frames", "Frames Used (0 = all)", 1, default_value=(0,), min=0, max=4096, min_is_strict=True), "{ mode == 2 }"))
    hint = hou.LabelParmTemplate("nofile", "Sheet File", column_labels=("Pick a Sheet File - or set Sheet From to Input and wire a layer in.",))
    g.append(cond(hint, "{ mode == 2 } { source != 0 } { file != \"\" }"))
    b = hou.ButtonParmTemplate("readgrid", "Read Grid from Sheet JSON")
    b.setScriptCallback("hou.phm().read_grid(kwargs)")
    b.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    g.append(cond(b, "{ mode == 2 } { source != 0 }"))
    # Play
    g.append(cond(hou.FloatParmTemplate("startframe", "Start Frame", 1, default_value=(1.0,), default_expression=("$FSTART",),
                                        default_expression_language=(hou.scriptLanguage.Hscript,)), "{ mode != 0 }"))
    g.append(cond(hou.FloatParmTemplate("sheetfps", "Sheet Speed (cells / second)", 1, default_value=(12.0,), min=0.01, max=120,
                                        min_is_strict=True), "{ mode != 0 }"))
    g.append(cond(hou.MenuParmTemplate("loop", "Loop", ("loop", "pingpong", "hold"), menu_labels=("Loop", "Ping-Pong", "Hold Last Frame"),
                                       default_value=0), "{ mode != 0 }"))
    g.append(cond(hou.ToggleParmTemplate("blend", "Blend Between Frames", default_value=True), "{ mode != 0 }"))
    # Extract
    g.append(cond(hou.IntParmTemplate("frame", "Frame (0 = first)", 1, default_value=(0,), min=0, max=4095, min_is_strict=True), "{ mode != 1 }"))
    # Make
    g.append(cond(hou.FloatParmTemplate("rangestart", "Range Start", 1, default_value=(1.0,), default_expression=("$FSTART",),
                                        default_expression_language=(hou.scriptLanguage.Hscript,)), "{ mode != 2 }"))
    g.append(cond(hou.FloatParmTemplate("rangeend", "Range End", 1, default_value=(24.0,), default_expression=("$FEND",),
                                        default_expression_language=(hou.scriptLanguage.Hscript,)), "{ mode != 2 }"))
    g.append(cond(hou.FloatParmTemplate("step", "Step (frames)", 1, default_value=(1.0,), min=0.01, max=1000, min_is_strict=True), "{ mode != 2 }"))
    g.append(cond(hou.IntParmTemplate("makecols", "Columns (0 = auto)", 1, default_value=(0,), min=0, max=64, min_is_strict=True), "{ mode != 2 }"))
    g.append(cond(hou.ToggleParmTemplate("cellresize", "Resize Cells", default_value=False), "{ mode != 2 }"))
    g.append(cond(hou.IntParmTemplate("cellres", "Cell Size", 2, default_value=(256, 256), min=1, max=8192, min_is_strict=True),
                  "{ mode != 2 } { cellresize == 0 }"))
    info = hou.StringParmTemplate("makeinfo", "Sheet", 1, default_value=("",), default_expression=("hou.node('.').hdaModule().make_info(hou.node('.'))",),
                                  default_expression_language=(hou.scriptLanguage.Python,))
    info.setConditional(hou.parmCondType.DisableWhen, "{ mode >= 0 }")
    g.append(cond(info, "{ mode != 2 }"))
    # internal: sheet frames elapsed since Start Frame - an Hscript expression so the node knows it is time dependent
    t = hou.FloatParmTemplate("_t", "_t", 1, default_value=(0.0,), default_expression=('($FF-ch("startframe"))/$FPS*ch("sheetfps")',),
                              default_expression_language=(hou.scriptLanguage.Hscript,))
    t.hide(True)
    g.append(t)
    return g


def _py(node, parm, expr):
    node.parm(parm).setExpression(expr, language=hou.exprLanguage.Python)


def _hs(node, parm, expr):
    node.parm(parm).setExpression(expr, language=hou.exprLanguage.Hscript)


def create():
    hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(OUTPUT_HDA):
        os.remove(OUTPUT_HDA)
    img = hou.node("/img") or hou.node("/").createNode("img", "img")
    copnet = img.createNode("copnet", "_build_ctx")
    subnet = copnet.createNode("subnet", "_build")
    subnet.parm("inputs").set(1)
    subnet.parm("outputs").set(1)
    subnet.parm("outputtype1").set(4)  # RGBA
    subnet.parm("outputlabel1").set("sheet")

    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=OUTPUT_HDA, description="PF Sprite Sheet",
                                    min_num_inputs=0, max_num_inputs=1, version="1")
    defn = hda.type().definition()
    defn.setParmTemplateGroup(_ptg())
    defn.addSection("PythonModule", PYTHON_MODULE)
    defn.setExtraFileOption("PythonModule/IsPython", True)
    hda.allowEditingOfContents()
    for c in hda.children():
        if c.type().name() not in ("input", "output"):
            c.destroy()
    kids = {c.type().name(): c for c in hda.children()}
    in1 = [c for c in hda.children() if c.type().name() == "input"][0]
    out = [c for c in hda.children() if c.type().name() == "output"][0]

    # ---- sheet source: file or input
    fl = hda.createNode("file", "sheet_file")
    _hs(fl, "filename", 'chs("../file")')
    # File COP "Pre-Multiply if Necessary": on multiplies a straight PNG's colour by alpha (Copernicus layers are
    # premultiplied). Ours: 0 = file is Premultiplied already -> off (0); 1 = Straight -> on (1).
    fl.parm("premultiplied").setExpression('ch("../premult")', language=hou.exprLanguage.Hscript)
    fl.parm("aovs").set(1)
    fl.parm("aov1").set("C")
    src = hda.createNode("switch", "sheet_source")
    src.setInput(0, fl)
    src.setInput(1, in1)
    _hs(src, "input", 'ch("../source")')

    # ---- extract / play: crop the cell(s), blend neighbours
    crops = []
    for which, nm in ((0, "cell_a"), (1, "cell_b")):
        c = hda.createNode("crop", nm)
        c.setInput(0, src)
        c.parm("mode").set(1)        # discard cropped and reframe to the crop
        c.parm("units").set(1)       # texture
        c.parm("method").set(1)      # lower-left + size
        for k in range(2):
            _py(c, "xy_texture" + "xy"[k], 'hou.node("..").hdaModule().cell(hou.node(".."), %d, %d)' % (which, k))
            _py(c, "size_texture" + "xy"[k], 'hou.node("..").hdaModule().cell(hou.node(".."), %d, %d, True)' % (which, k))
        crops.append(c)
    mixn = hda.createNode("blend", "blend_cells")
    mixn.setInput(0, crops[0])
    mixn.setInput(1, crops[1])
    _py(mixn, "mask", 'hou.node("..").hdaModule().mix(hou.node(".."))')

    # ---- make: resample -> time pack -> contact sheet
    rs = hda.createNode("resample", "cell_resize")
    rs.setInput(0, in1)
    rs.parm("sizecontrol").set(0)
    rs.parm("basesize").set(0)
    for k in range(2):
        _hs(rs, "resolution" + "12"[k], 'ch("../cellres%s")' % ("xy"[k]))
    sw_rs = hda.createNode("switch", "resize_or_not")
    sw_rs.setInput(0, in1)
    sw_rs.setInput(1, rs)
    _hs(sw_rs, "input", 'ch("../cellresize")')
    tp = hda.createNode("timepack", "pack_frames")
    tp.setInput(0, sw_rs)
    tp.parm("mode").set(1)
    tp.parm("method").set(0)
    _hs(tp, "absrangeframe1", 'ch("../rangestart")')
    _py(tp, "absrangeframe2", 'hou.node("..").hdaModule().make_end(hou.node(".."))')
    _hs(tp, "stepframe", 'ch("../step")')
    cs = hda.createNode("contactsheet", "sheet_grid")
    cs.setInput(0, tp)
    cs.parm("limitlines").set(0)
    _py(cs, "stride", 'hou.node("..").hdaModule().make_cols(hou.node(".."))')
    # ---- mode
    sw_mode = hda.createNode("switch", "by_mode")
    sw_mode.setInput(0, mixn)
    sw_mode.setInput(1, cs)
    _hs(sw_mode, "input", 'ch("../mode") >= 2')
    for slot in range(8):
        try:
            out.setInput(slot, None)
        except Exception:
            break
    out.setInput(0, sw_mode)
    out.setDisplayFlag(True)
    hda.layoutChildren()

    defn.addSection("Help", HELP_TEXT)
    defn.save(OUTPUT_HDA, template_node=hda)
    assert defn.embeddedHelp().strip(), "help not embedded"
    print("[OK] Saved:", OUTPUT_HDA)
    hda.destroy()
    copnet.destroy()
    return OUTPUT_HDA


if __name__ == "__main__":
    create()
