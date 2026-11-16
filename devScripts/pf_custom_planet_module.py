"""pf_custom_planet_module.py - PythonModule of the pf_custom_planet HDA (also imported by tests).

Python is used for exactly two things (justified in ideas/spacetools.md "Custom planet"):
 1. library file marshalling: which EXR a menu pick means, does it exist, flags for the kernel (a File COP cannot
    test for a missing file and a ch() expression cannot build a path);
 2. bake(): a loop over maps/faces/resolution plus file writes, through the shared spacetools baker.
"""
import os

DEFAULT_DIR = "F:/cache/spacetools/planet_img/CustomPlanetImages"

# kind -> (parm, folder, file pattern, library count, menu offset: library number = pick - offset, wired to light variant)
KINDS = {
    "surf": ("surface", "Surface", "Surface_{n:02d}_{res}_LS00.exr", 30, 0, False),
    "watr": ("water", "Water", "water_{n:02d}_{res}_LS00.exr", 17, 1, False),
    "emis": ("emission", "Emission", "emission_{n:02d}_{res}_LS00.exr", 18, 1, False),
    "clds": ("clouds", "Clouds", "clouds_{n:02d}_{res}_LS{ls:02d}.exr", 18, 1, True),
    "atmo": ("atmosphere", "Atmosphere", "Atmosphere_{n:02d}_{res}_LS{ls:02d}.exr", 4, 1, True),
}
SURFACE_NAMES = ["Ice Blue", "Grey Earth", "Green Forest", "Green Rivers", "Desert Orange", "Rust Mars", "Orange Dunes",
                 "Pale Sand", "Green Craters", "Mauve Plains", "Blue Dunes", "Green Swirl", "Orange Haze", "Dark Rock",
                 "Tan Canyons", "Dark Green", "Teal Moss", "Psychedelic", "Brown Mottled", "Blue Grey", "Orange Purple",
                 "Banded Blue Gas", "Island World 1", "Island World 2", "Island World 3", "Island World 4", "Island World 5",
                 "Jupiter", "Saturn", "Venus"]
LIGHT_NAMES = ["Procedural sun (Sun Azimuth/Elevation)", "00 Flat / unlit", "01 Thin crescent", "02 Crescent", "03 Half", "04 Gibbous"]
ATM_NAMES = ["Big", "Medium", "Small", "Very small"]


def imagedir(node):
    import hou
    d = hou.text.expandString(node.evalParm("imagedir")).strip().replace("\\", "/")
    if not d or "$" in d or not os.path.isdir(d):
        d = DEFAULT_DIR
    return d


def light_index(node):
    """Library light setup 0..4 (clouds/atmosphere/rim variants); sphere maps are unlit -> 0."""
    lp = node.evalParm("lightsetup")
    return 0 if (node.evalParm("mode") == 1 or lp == 0) else lp - 1


def path(node, kind):
    """Absolute path of the library file for a layer kind, '' when the pick is None/Procedural."""
    res = node.parm("libres").evalAsString()
    base = imagedir(node)
    if kind == "wrim":
        return "%s/%s/Atmosphere/WhiteRim/atmosphere_whiteRim_%s_LS00.exr" % (base, res, res)
    if kind == "mask":
        return "%s/%s/Mask/surface_Mask_4k.exr" % (base, res)
    if kind == "lset":
        lp = node.evalParm("lightsetup")
        return "" if lp == 0 else "%s/%s/LightSetup/LightSetup_%02d_%s_LS%02d.exr" % (base, res, lp - 1, res, lp - 1)
    parm, folder, pat, count, off, lsv = KINDS[kind]
    n = node.evalParm(parm) - off
    if n < 1:
        return ""
    return "%s/%s/%s/%s" % (base, res, folder, pat.format(n=n, res=res, ls=light_index(node) if lsv else 0))


def filepath(node, kind):
    """path() for the File COPs: never empty (an empty name is an error); the sentinel does not exist -> missing colour."""
    return path(node, kind) or "F:/pf_planet_none.exr"


def have(node, kind):
    """1 when the layer is read from a library file that exists."""
    p = path(node, kind)
    if kind in ("wrim", "mask"):
        return int(node.evalParm("mode") == 0 and os.path.isfile(p))
    if kind == "lset":
        return int(node.evalParm("mode") == 0 and bool(p) and os.path.isfile(p))
    return int(bool(p) and os.path.isfile(p))


def proc(node, kind):
    """1 when the procedural generator drives the layer: picked 'Procedural', or a library pick whose file is missing."""
    parm, folder, pat, count, off, lsv = KINDS[kind]
    pick = node.evalParm(parm)
    if kind == "surf":
        return 0
    if pick == 0:
        return 0
    return int(pick == 1 or not have(node, kind))


def menu_items(kind):
    """(labels) for the layer pick menus."""
    if kind == "surf":
        return ["Procedural"] + ["%02d %s" % (i + 1, n) for i, n in enumerate(SURFACE_NAMES)]
    names = {"watr": "Water", "emis": "Emission", "clds": "Clouds"}
    if kind == "atmo":
        return ["None", "Procedural"] + ["%02d %s" % (i + 1, n) for i, n in enumerate(ATM_NAMES)]
    return ["None", "Procedural"] + ["%s %02d" % (names[kind], i + 1) for i in range(KINDS[kind][3])]


MAPS = ["beauty", "surface", "clouds", "emission", "atmosphere", "water", "height", "normal"]   # = output index


def _bake_mod():
    import sys
    try:                                   # tests/dev: devScripts/ -> polyfactory/scripts/python
        pyd = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polyfactory", "scripts", "python"))
        if os.path.isdir(pyd) and pyd not in sys.path:
            sys.path.append(pyd)
    except NameError:                      # embedded as the HDA PythonModule: the polyfactory package is on the path
        pass
    from polyfactory.spacetools import bake
    return bake


def bake(node, folder, basename="planet", res=512, maps=None, layouts=("equirect", "faces", "cross"), half=False):
    """Float32 EXRs. Sphere mode: per map the shared set (<base>_<map>_equirect/_cross/_px.. ). Billboard: <base>_<map>.exr."""
    b = _bake_mod()
    maps = maps or (["beauty", "surface", "clouds", "emission", "water", "height", "normal"] if node.evalParm("mode") == 1 else MAPS)
    out = {}
    if node.evalParm("mode") == 1:
        for m in maps:
            out[m] = b.bake_set(node, folder, "%s_%s" % (basename, m), res, layouts=layouts, layer_index=MAPS.index(m), half=half)
    else:
        for m in maps:
            p = os.path.join(folder, "%s_%s.exr" % (basename, m)).replace("\\", "/")
            b.write_exr(p, b.layer_array(node, MAPS.index(m)), half)
            out[m] = p
    return out
