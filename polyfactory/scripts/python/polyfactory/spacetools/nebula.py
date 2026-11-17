"""pf_nebula_generator helpers: apply Blender-derived presets to the HDA (parm marshalling, the only python in the tool:
ramps and vectors cannot be a plain menu action). Presets: nebula_presets.json (built by devScripts/nebula_blender_to_presets.py)."""
import json
import os

_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nebula_presets.json")
_VEC = {"vec3": "xyz", "color": "rgb"}


def load():
    with open(_FILE) as f:
        return json.load(f)


def preset_names():
    return load()["order"]


def apply_preset(node, name, data=None):
    """Set every parm in preset `name` on `node` (a pf_nebula_generator). Parms the preset lacks keep their value."""
    import hou
    data = data or load()
    if isinstance(name, int):                                         # menu callback passes parm.eval() = index
        name = data["order"][name]
    d = data["presets"]
    # always start from the 'default' preset so a partial preset (e.g. missing Sun) does not inherit the previous look
    for key in ("default", name) if name != "default" else ("default",):
        for k, v in d[key].items():
            parm = node.parm(k)
            if isinstance(v, dict):                                   # ramp
                basis = hou.rampBasis.Constant if v["interp"] == "constant" else hou.rampBasis.Linear
                pos = v["pos"]
                if node.parm(k).parmTemplate().type() == hou.parmTemplateType.Ramp:
                    parm.set(hou.Ramp([basis] * len(pos), pos, v["val"]))
            elif isinstance(v, list):
                t = node.parmTuple(k)
                if t is None:
                    continue
                t.set(v)
            elif parm is not None:
                parm.set(v)
