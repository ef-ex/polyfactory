"""pf_spacescape PythonModule (embedded in the HDA by create_pf_spacescape_hda.py; also importable by tests).

Python is used ONLY for what Houdini cannot express natively (decision log in ideas/spacetools.md, "## Spacescape"):
  * apply_preset(): fills the layer multiparm (a multiparm instance cannot carry per-instance defaults)
  * bake(): a loop over output targets (6 faces + cross + equirect) via the shared polyfactory.spacetools.bake
    (sets layout/face/res, cooks, writes EXR); no native node loops over parameter values and files.
"""
import os

TYPES = ["noise", "points", "billboards", "sun", "gradient"]
BLEND = ["one", "zero", "dest_colour", "src_colour", "one_minus_dest_colour", "one_minus_src_colour",
         "dest_alpha", "src_alpha", "one_minus_dest_alpha", "one_minus_src_alpha"]

DEFAULT = dict(
    enable=1, name="Layer", type=0, seed=0, noisetype=0, scale=1.0, octaves=8, lacunarity=2.0, gain=0.5,
    offset=1.0, power=1.0, shelf=0.0, dither=0.03,
    colorin=(1.0, 1.0, 1.0), colormid=(0.5, 0.5, 0.5), usemid=0, midpos=0.5, colorout=(0.0, 0.0, 0.0),
    hdrmult=1.0, hdrpower=1.0, count=10000, size=1.0, sizemax=4.0, spikes=0.0,
    srcblend=0, dstblend=0,
    maskon=0, mask_type=1, mask_seed=1, mask_scale=1.0, mask_oct=8, mask_lac=2.0, mask_gain=0.7,
    mask_offset=1.0, mask_power=1.25, mask_thresh=0.4, axis=(0.0, 1.0, 0.0),
)
TUPLES = ("colorin", "colormid", "colorout", "axis")


def L(**kw):
    d = dict(DEFAULT)
    bad = set(kw) - set(d)
    assert not bad, bad
    d.update(kw)
    return d


def _stars(name, seed, count, size, near, far=(0, 0, 0), mask=None, hdr=1.0, **kw):
    d = dict(name=name, type=1, seed=seed, count=count, size=size, colorin=near, colorout=far, hdrmult=hdr)
    if mask:
        d.update(maskon=1, **mask)
    d.update(kw)
    return L(**d)


def _bb(name, seed, count, smin, smax, near, far, mask=None, hdr=1.0, spikes=0.0):
    d = dict(name=name, type=2, seed=seed, count=count, size=smin, sizemax=smax, colorin=near, colorout=far,
             hdrmult=hdr, spikes=spikes)
    if mask:
        d.update(maskon=1, **mask)
    return L(**d)


_DUST = dict(mask_type=1, mask_seed=1, mask_scale=1.0, mask_oct=10, mask_gain=0.7, mask_power=1.25, mask_thresh=0.4)

PRESETS = {
    # after Spacescape/save/purple-nebula-complex.xml (inner/outer colours, shelf, scale and seeds taken from it)
    "Purple Nebula": [
        L(name="Pink Purple Nebula", noisetype=0, octaves=8, scale=1.0, gain=0.5, seed=0,
          colorin=(1.0, 0.0, 0.6), colorout=(0.004, 0.31, 0.357), hdrmult=1.0, dstblend=0, srcblend=0),
        L(name="Black Ridged Mask", noisetype=1, octaves=10, scale=1.0, gain=0.7, power=1.25, seed=1,
          colorin=(0, 0, 0), colorout=(0, 0, 0), srcblend=7, dstblend=9),
        L(name="Blue Nebula", noisetype=1, octaves=10, scale=0.5, gain=0.7, seed=2, shelf=0.8,
          colorin=(0.25, 0.35, 0.64), colorout=(0, 0, 0), hdrmult=1.0),
        _stars("Purple Point Stars", 0, 30000, 1, (0.28, 0.19, 0.32), hdr=1.5),
        _stars("Large Purple Point Stars", 5, 20000, 2, (0.2, 0.16, 0.26), mask=_DUST, hdr=2.0),
        _stars("Blue Point Stars", 3, 30000, 1, (0.4, 0.72, 0.84), mask=_DUST, hdr=1.5),
        _bb("Billboard Stars", 9, 120, 0.6, 1.8, (1, 1, 1), (0.956, 1.0, 0.894), mask=_DUST, hdr=5.0, spikes=0.12),
        _bb("Bright Stars", 15, 10, 1.5, 4.0, (0.87, 0.96, 1.0), (1.0, 0.85, 0.6), hdr=25.0, spikes=0.35),
    ],
    "Green Nebula": [
        L(name="Green Nebula", noisetype=1, octaves=9, scale=0.8, gain=0.8, seed=4, shelf=0.55,
          colorin=(0.55, 1.0, 0.45), colorout=(0.0, 0.1, 0.12), usemid=1, colormid=(0.1, 0.55, 0.35), midpos=0.5,
          hdrmult=0.7, power=1.0),
        L(name="Fuzzy Stars Cloud", noisetype=1, octaves=8, scale=10.0, gain=1.5, offset=0.94, seed=4, shelf=0.8,
          colorin=(0.09, 0.44, 0.91), colorout=(0, 0, 0), hdrmult=1.5),
        _stars("Stars", 1, 30000, 1, (0.9, 0.95, 1.0), hdr=1.8),
        _stars("Bigger Stars", 2, 2000, 2, (1.0, 0.9, 0.7), hdr=5.0),
        _bb("Bright Stars", 7, 18, 1.5, 4.0, (1, 1, 1), (0.7, 0.85, 1.0), hdr=40.0, spikes=0.5),
    ],
    "Sun and Starfield": [
        L(name="Galactic Band", type=4, noisetype=0, size=18.0, power=1.0, colorin=(0.35, 0.28, 0.5),
          colorout=(0.0, 0.0, 0.02), hdrmult=1.5, axis=(0.3, 1.0, 0.1), srcblend=0, dstblend=0),
        L(name="Dust Lanes", noisetype=1, octaves=9, scale=3.0, gain=0.7, seed=11, shelf=0.3, power=1.5,
          colorin=(0, 0, 0), colorout=(0, 0, 0), srcblend=7, dstblend=9),
        _stars("Stars", 21, 25000, 1, (0.85, 0.9, 1.0), (1.0, 0.8, 0.6), hdr=1.5),
        _stars("Stars Big", 22, 2500, 2, (0.9, 0.9, 1.0), (1.0, 0.7, 0.5), hdr=3.5),
        L(name="Sun", type=3, size=0.5, colorin=(1.0, 0.92, 0.75), colorout=(1.0, 0.55, 0.2), hdrmult=60.0,
          spikes=0.25, axis=(0.55, 0.25, -0.8)),
    ],
}
DEFAULT_PRESET = "Purple Nebula"


def apply_layers(node, layers):
    node.parm("layers").set(len(layers))
    for i, lay in enumerate(layers, 1):
        for k, v in lay.items():
            if k in TUPLES:
                node.parmTuple("%s%d" % (k, i)).set(v)
            else:
                node.parm("%s%d" % (k, i)).set(v)


def apply_preset(node, name=None):
    apply_layers(node, PRESETS[name or DEFAULT_PRESET])


def on_created(node):
    """OnCreated: first cook of a fresh node is a finished-looking space scene."""
    if node.parm("layers").eval() == 0 and not node.isInsideLockedHDA():
        apply_preset(node)
    from polyfactory.spacetools import sky
    sky.ensure_preview(node)               # a big sphere in /obj showing this sky (GUI only)


def _bake_mod():
    try:                                   # tests/dev: devScripts/ -> polyfactory/scripts/python
        import sys
        pyd = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "polyfactory", "scripts", "python"))
        if os.path.isdir(pyd) and pyd not in sys.path:
            sys.path.append(pyd)
    except NameError:                      # embedded as the HDA PythonModule: the polyfactory package is on the path
        pass
    from polyfactory.spacetools import bake
    return bake


def bake(node, folder, basename="sky", res=1024, **kw):
    """Float32 EXRs through the shared spacetools baker: <base>_px/_nx/_py/_ny/_pz/_nz, _cross, _equirect."""
    return _bake_mod().bake_set(node, folder, basename, res, **kw)
