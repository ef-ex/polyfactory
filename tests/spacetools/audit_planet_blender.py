"""Audit: extra Blender-vs-HDA billboard configs the author's check does not cover (other LS variants, flat LS,
cloud/atm variants, emission hue/sat, cloud thickness/brightness, atm sat, contrast). hython tests/spacetools/audit_planet_blender.py"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
import run_planet_checks as R
from planet_common import *
from PIL import Image
R.SCRATCH = "F:/cache/spacetools/audit_planet"
import planet_common; planet_common.SCRATCH = R.SCRATCH
CFG = {
 "X_flatLS0": ({"surface": 14, "water": 2, "water_blend": 0.7, "emission": 6, "emit": 1.0, "ls": 0, "clouds": 9, "atm": 4, "res": "2k"},
               {"surface": 14, "water": 3, "w_blend": 0.7, "emission": 7, "lightsetup": 1, "clouds": 10, "atmosphere": 5}),
 "Y_LS4_cloudthick": ({"surface": 2, "clouds": 12, "cloud_thick": 0.6, "cloud_bright": 1.4, "atm": 2, "atm_sat": 1.7, "ls": 4, "contrast": 0.8,
                       "emission": 10, "emit_hue": 0.7, "emit_sat": 0.5, "emit_strength_overall": 3.0, "res": "2k"},
                      {"surface": 2, "clouds": 13, "c_thick": 0.6, "c_bright": 1.4, "atmosphere": 3, "a_sat": 1.7, "lightsetup": 5, "s_contrast": 0.8,
                       "emission": 11, "e_hue": 0.2, "e_sat": 0.5, "emission_overall": 3.0}),
 "Z_LS1_ramp_shadow": ({"surface": 21, "clouds": 3, "atm": 1, "ls": 1, "shadow_bright": 0.8, "emit": 2, "emission": 2, "shadow_vis": 0, "res": "2k"},
                       {"surface": 21, "clouds": 4, "atmosphere": 2, "lightsetup": 2, "shadow_bright": 0.8, "emission": 3, "e_strength": 2, "e_shadowvis": 0}),
}
for tag, (b, h) in CFG.items():
    ref = R.blender_ref(tag, b)
    n = make_node(dict(h, mode=0, libres=1)); bad = R.cook_clean(n); a = layer(n, 0)
    rel = R.reldiff(a, ref); full = float(np.abs(a[..., :3] - ref[..., :3]).mean() / ref[..., :3].mean())
    print("%-20s cook_bad=%s  blockrel=%.4f fullrel=%.4f alpha %.4f/%.4f  maxdiff %.3f refmax %.2f" % (tag, bool(bad), rel, full, a[..., 3].mean(), ref[..., 3].mean(), np.abs(a-ref).max(), ref.max()))
    Image.fromarray(np.concatenate([tonemap(ref), tonemap(a)], 1)).resize((1000, 500)).save("%s/%s_side.png" % (R.SCRATCH, tag))
