"""modelUI operation registry (framework layer 5, ideas/modelui.md): Houdini nodes with a little metadata, so the
Modify panel can list them. One entry per node; a later mode (texturing) lists its COPs under its own key.

Entry fields:
  key       stable id (used by code and checks)
  label     what the Modifier List shows
  type      the node type name in ``context`` (the real Houdini node is what the stack holds)
  context   node type category name ("Sop"; a texturing mode would use "Cop")
  icon      optional; default: the node type's own icon
  groups    group fields that get a "use selection" button and take the component selection when the entry is added:
            {"parm": group parm, "type_parm": its group-type menu (set from the selection's type), or
             "types": the element types the field accepts (a selection of another type is converted to the first)}
  inputs    {input index: {"label": pick button text, "set": {parm: value} applied when an object is picked}}
  defaults  {parm: value} set when the entry is added (only where Houdini's default shows nothing)
  build     optional helper network made with the entry (name of a function in stack.BUILDERS)
  state     optional: whose viewer state the stack shows for the entry (an input index; default the node itself)
"""
import hou

MODES = {
    "model": [
        {"key": "extrude", "label": "Extrude (PolyExtrude)", "type": "polyextrude::2.0", "context": "Sop",
         "groups": [{"parm": "group", "types": ("prims", "edges")}],
         "inputs": {1: {"label": "Spine curve", "set": {"spinetype": "external"}}},
         "defaults": {"dist": 0.1}},
        {"key": "subdivide", "label": "Subdivide", "type": "subdivide", "context": "Sop",
         "groups": [{"parm": "subdivide", "types": ("prims",)}]},
        {"key": "bevel", "label": "Bevel (PolyBevel)", "type": "polybevel::3.0", "context": "Sop",
         "groups": [{"parm": "group", "type_parm": "grouptype"}],
         "inputs": {1: {"label": "Profile curve", "set": {"profilesource": "external"}}},
         "defaults": {"offset": 0.05}},
        {"key": "lattice", "label": "Lattice (Lattice Deform)", "type": "lattice", "context": "Sop",
         "groups": [{"parm": "group", "types": ("points",)}],
         "inputs": {1: {"label": "Rest lattice"}, 2: {"label": "Deformed lattice"}},
         "build": "lattice_cage", "state": 2},
        {"key": "edit", "label": "Edit", "type": "edit", "context": "Sop",
         "groups": [{"parm": "group", "type_parm": "grouptype"}]},
        {"key": "polywire", "label": "PolyWire (Max's Lattice struts)", "type": "polywire", "context": "Sop",
         "groups": [{"parm": "group", "types": ("prims",)}]},
    ],
}


def ops(mode="model"):
    return MODES[mode]


def get(key, mode="model"):
    for op in MODES[mode]:
        if op["key"] == key:
            return op
    raise KeyError("no operation %r in mode %r" % (key, mode))


def for_node(node, mode="model"):
    """The registry entry of a node's type, or None (a node added in the network editor still shows in the stack)."""
    name = node.type().name()
    return next((op for op in MODES[mode] if op["type"] == name), None)


def icon(op):
    if op.get("icon"):
        return op["icon"]
    t = hou.nodeType(hou.nodeTypeCategories()[op["context"]], op["type"])
    return t.icon() if t is not None else "MISC_python"
