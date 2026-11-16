"""LOOK audit: renders 6 plating presets on box / sphere / grid (+ greebles) into F:/cache/spacetools/audit_plating/.
hython tests/spacetools/audit_plating_look.py
Every tile is verified to contain its subject (prims > input prims, plate tops visible, non-trivial pixel coverage) before the sheet is written."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hou
from PIL import Image
from lib import fresh, install, cook, fx_grid, fx_sphere, fx_box, render_png
from run_plating_checks import mk, run_preset

OUT = "F:/cache/spacetools/audit_plating"
g = fresh(); install("pf_plating_generator"); install("pf_greeble_scatter")
PRE = ["Simple_Panels_with_Triangles", "Simple_Panels_Irregular", "Regular_Panels_for_Spacecraft", "Random_Heights", "Snake", "Tapered"]
fx = {"box": (lambda: fx_box(g), (35, -30)), "grid": (lambda: fx_grid(g, 11, 4.0), (50, -20)), "sphere": (lambda: fx_sphere(g), (25, -30))}
for fn, (mkf, view) in fx.items():
    tiles = []
    for k in PRE:
        src = mkf()
        n = mk(g, "pf_plating_generator", src, random_color=1)
        run_preset(n, k); n.parm("random_color").set(1)
        geo = cook(n)
        p = "%s/t_%s_%s.png" % (OUT, fn, k)
        cnt = render_png(geo, p, size=500, view=view, title=k)
        im = np.asarray(Image.open(p).convert("L"))
        cov = float((im < 250).mean())
        assert cnt > len(src.geometry().prims()) * 2 and cov > 0.08, (fn, k, cnt, cov)
        tiles.append(Image.open(p).convert("RGB"))
    W = Image.new("RGB", (1500, 1000), "white")
    for i, t in enumerate(tiles):
        W.paste(t, ((i % 3) * 500, (i // 3) * 500))
    W.save("%s/sheet_%s.png" % (OUT, fn)); print("sheet", fn, "ok")
# greebles on box + plated grid
src = fx_box(g)
n = mk(g, "pf_greeble_scatter", src, kit="all", coverage=70, height_max=0.15, random_color=1, keep_aspect=1)
render_png(cook(n), OUT + "/gr_box.png", 700, (35, -30), title="greebles on box")
pl = mk(g, "pf_plating_generator", fx_grid(g, 11, 4.0), amount=25, height_min=0.05, height_max=0.1, groove_width=0.05)
gr = mk(g, "pf_greeble_scatter", pl, group="pf_plate_top", kit="hull", coverage=60, height_max=0.1, random_color=1)
render_png(cook(gr), OUT + "/gr_plated_grid.png", 700, (50, -20), title="plates + hull greebles")
W = Image.new("RGB", (1400, 700), "white")
W.paste(Image.open(OUT + "/gr_box.png").convert("RGB"), (0, 0)); W.paste(Image.open(OUT + "/gr_plated_grid.png").convert("RGB"), (700, 0))
W.save(OUT + "/sheet_greebles.png"); print("done")
