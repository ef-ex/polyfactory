"""Create `pf_edge_damage` - a 1:1 port of Quentin King's "Paintable
Stylized Edge Damage" (quentinking.com/houdini/edgedamage/, free download)
as a polyfactory SOP HDA.

    hython devScripts/create_pf_edge_damage_hda.py

THIS IS A REPLICA, NOT A REDESIGN. The network, every parameter (name,
label, default, range, hidden state), the attribpaint links and the viewer
state module are taken verbatim from the reference asset
`Quentin::paint_edge_damage::1.0`, read node-for-node off a live session
(the dump is embedded below as SPEC). Three deviations, all naming, none
behavioural:
  * the asset is `pf_edge_damage`, TAB label "PF Edge Damage", under
    Poly Factory/Modeling (polyfactory's TAB law);
  * the chip prim group is `pf_chipped`, not `chipped` (conventions.md 1);
  * the embedded `paint.pic` icon section is not copied - the state binds
    the asset icon, `SOP_attribpaint`, which is the same picture;
  * ONE guard in the viewer-state module: the reference looks up a scene
    visualizer for the mask attribute and assumes it exists (Quentin's
    .hiplc carries it; a fresh scene does not, and onEnter crashed with
    "'NoneType' object has no attribute 'setIsActive'"). The port creates
    it with SideFX's own mask-visualizer defaults when it is missing.
    Three lines, marked "pf port" in the module; the parity check holds the
    module to reference-plus-exactly-those-lines;
  * IMPROVEMENTS Hannes asked for AFTER the faithful port (2026-09-16):
    a `damage_depth` parm ("Damage Depth") and the mask-bias wrangle
    `@P += @N * ((1 - mask) * 0.1 - mask * damage_depth)`, so a stroke cuts
    anywhere, not only at the edges the blur pulls in; the HUD's
    strength bar reads the strength (the reference fed it the radius);
    and the hidden `stroke_float` is shown as "Damage Strength" after
    Damage Depth (the reference exposed strength only via Ctrl+wheel);
  * the stroke cache lives on the ASSET: the inner attribpaint's bakedgeo /
    unsavedbakedgeo / strokegeo reference the asset's hidden Cache folder
    (the reference interface carries it), so the module's writes through
    `paint_node.parm(...)` follow the reference and succeed on a LOCKED
    instance. Without this a locked instance refused the write, the module
    zeroed the stroke count, and the last stroke was lost.
`tests/hda/run_edge_damage_checks.py` asserts parity against SPEC.

How it works (Quentin's design, restated so nobody "improves" it again):
matchsize into the unit cube -> brick divide (paint canvas) -> attribpaint
`mask` -> attribblur on P (pulls edges in) -> remesh -> attribnoise along
N -> peak -> `@P += @N * (1 - mask) * 0.1` (mask 0 clears the surface,
mask past 1 dips INTO it, negative erases) -> VDB -> polygons ->
polyreduce | remesh -> hard normals -> boolean INTERSECT with the original
-> restore transform. The viewer state (sidefx_stroke.StrokeState) paints
the asset's own stroke multiparm; Ctrl+wheel changes strength, the HUD
shows radius and strength, hotkeys 1-4 switch the viz.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_edge_damage.hda").replace("\\", "/")

NAME = "pf_edge_damage"
TAB_LABEL = "PF Edge Damage"
ICON = "SOP_attribpaint"

TOOLS_SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Poly Factory/Modeling</toolSubmenu>
    <script scriptType="python"><![CDATA[import soptoolutils

soptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""

# --------------------------------------------------------------------------
# SPEC - the reference asset, as read off the live session.
# --------------------------------------------------------------------------
PARMS = [{'default': [0],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Viz Mode',
  'max': 10,
  'maxlock': False,
  'min': 0,
  'minlock': False,
  'name': 'visual_mode',
  'size': 1,
  'type': 'Int'},
 {'depth': 0, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm4', 'type': 'Separator'},
 {'default': [0.05],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Painting Resolution',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'paint_resolution',
  'size': 1,
  'type': 'Float'},
 {'default': [0.2],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Damage Resolution Size',
  'max': 1.0,
  'maxlock': False,
  'min': 0.001,
  'minlock': True,
  'name': 'damage_resolution',
  'size': 1,
  'type': 'Float'},
 {'default': [13.0],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Blurring Iterations',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'blur_iterations',
  'size': 1,
  'type': 'Float'},
 {'default': [0.04],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Damage Bias',
  'max': 0.1,
  'maxlock': False,
  'min': -0.1,
  'minlock': False,
  'name': 'dist',
  'size': 1,
  'type': 'Float'},
 {'default': [0.1],
  'depth': 0,
  'help': 'How deep a full-strength stroke cuts into the surface, as a fraction of the object. 0 '
          'is the original tool: edges only, faces need a strength past 1.',
  'hidden': False,
  'label': 'Damage Depth',
  'max': 0.5,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'damage_depth',
  'size': 1,
  'type': 'Float'},
 {'default': [2.0],
  'depth': 0,
  'help': 'How much a stroke paints: 1 cuts Damage Depth deep, past 1 carves deeper, negative '
          'erases. Ctrl + wheel in the viewport changes it too.',
  'hidden': False,
  'label': 'Damage Strength',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'stroke_float',
  'size': 1,
  'type': 'Float'},
 {'depth': 0, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm6', 'type': 'Separator'},
 {'default': 1,
  'depth': 0,
  'help': '',
  'hidden': False,
  'items': ['0', '1'],
  'label': 'Damage Meshing Method',
  'labels': ['Remesh', 'PolyReduce'],
  'name': 'damage_meshing',
  'type': 'Menu'},
 {'default': [0.25],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Target Mesh Size',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'target_mesh_size',
  'size': 1,
  'type': 'Float'},
 {'default': [10.0],
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Target Mesh Percentage',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'target_mesh_percentage',
  'size': 1,
  'type': 'Float'},
 {'depth': 0, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm2', 'type': 'Separator'},
 {'depth': 0,
  'foldertype': 'folderType.Simple',
  'help': '',
  'hidden': False,
  'label': 'Noise Settings',
  'name': 'noise_folder',
  'type': 'Folder'},
 {'default': 5,
  'depth': 1,
  'help': '',
  'hidden': False,
  'items': ['value_fast',
            'sparse',
            'alligator',
            'perlin',
            'flow',
            'simplex',
            'worleyFA',
            'worleyFB',
            'mworleyFA',
            'mworleyFB',
            'cworleyFA',
            'cworleyFB',
            'pcloud',
            'scloud',
            'fscloud'],
  'label': 'Noise Type',
  'labels': ['Fast',
             'Sparse Convolution',
             'Alligator',
             'Perlin',
             'Perlin Flow',
             'Simplex',
             'Worley Cellular F1',
             'Worley Cellular F2-F1',
             'Manhattan Cellular F1',
             'Manhattan Cellular F2-F1',
             'Chebyshev Cellular F1',
             'Chebyshev Cellular F2-F1',
             'Perlin Cloud',
             'Simplex Cloud',
             'Fast Simplex Cloud'],
  'name': 'basis',
  'type': 'Menu'},
 {'default': [0.07],
  'depth': 1,
  'help': '',
  'hidden': False,
  'label': 'Amplitude',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'amplitude',
  'size': 1,
  'type': 'Float'},
 {'default': [0.1],
  'depth': 1,
  'help': '',
  'hidden': False,
  'label': 'Element Size',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'elementsize',
  'size': 1,
  'type': 'Float'},
 {'depth': 1, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm3', 'type': 'Separator'},
 {'depth': 1,
  'foldertype': 'folderType.Simple',
  'help': '',
  'hidden': False,
  'label': 'Fractal',
  'name': 'fractal_settings',
  'type': 'Folder'},
 {'default': 1,
  'depth': 2,
  'help': '',
  'hidden': False,
  'items': ['none', 'fBm', 'mfT', 'hmfT'],
  'label': 'Fractal Type',
  'labels': ['None', 'Standard (fBm)', 'Terrain', 'Hybrid Terrain'],
  'name': 'fractal',
  'type': 'Menu'},
 {'default': [1.0],
  'depth': 2,
  'help': '',
  'hidden': False,
  'label': 'Max Octaves',
  'max': 16.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'oct',
  'size': 1,
  'type': 'Float'},
 {'default': [2.01234],
  'depth': 2,
  'help': '',
  'hidden': False,
  'label': 'Lacunarity',
  'max': 4.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'lac',
  'size': 1,
  'type': 'Float'},
 {'default': [1.0],
  'depth': 2,
  'help': '',
  'hidden': False,
  'label': 'Roughness',
  'max': 1.0,
  'maxlock': True,
  'min': 0.0,
  'minlock': True,
  'name': 'rough',
  'size': 1,
  'type': 'Float'},
 {'depth': 0, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm5', 'type': 'Separator'},
 {'callback': "kwargs['node'].hdaViewerStateModule().reset(hou.pwd())",
  'depth': 0,
  'help': '',
  'hidden': False,
  'label': 'Reset',
  'lang': 'scriptLanguage.Python',
  'name': 'reset_button',
  'type': 'Button'},
 {'depth': 0, 'help': '', 'hidden': False, 'label': '', 'name': 'sepparm', 'type': 'Separator'},
 {'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'all the stroke stuff',
  'name': 'labelparm',
  'type': 'Label'},
 {'depth': 0,
  'foldertype': 'folderType.Tabs',
  'help': '',
  'hidden': True,
  'label': 'Cache',
  'name': 'folder0',
  'type': 'Folder'},
 {'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Baked Geometry',
  'name': 'bakedgeo',
  'type': 'Data'},
 {'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Unsaved Baked Geometry',
  'name': 'unsavedbakedgeo',
  'type': 'Data'},
 {'depth': 1, 'help': '', 'hidden': True, 'label': 'Strokes', 'name': 'strokegeo', 'type': 'Data'},
 {'default': [4],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Stroke Projection',
  'max': 10,
  'maxlock': False,
  'min': 0,
  'minlock': False,
  'name': 'stroke_projtype',
  'size': 1,
  'type': 'Int'},
 {'default': [0.5],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Soft Edge',
  'max': 1.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'stroke_softedge',
  'size': 1,
  'type': 'Float'},
 {'default': ['mask'],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Paint Attribute',
  'name': 'stroke_attrib',
  'type': 'String'},
 {'default': [1],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Stroke Attrib Type',
  'max': 10,
  'maxlock': False,
  'min': 0,
  'minlock': False,
  'name': 'stroke_attribtype',
  'size': 1,
  'type': 'Int'},
 {'default': [0.2],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Radius',
  'max': 1.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'stroke_radius',
  'size': 1,
  'type': 'Float'},
 {'default': [1.0],
  'depth': 0,
  'help': '',
  'hidden': True,
  'label': 'Opacity',
  'max': 1.0,
  'maxlock': True,
  'min': 0.0,
  'minlock': True,
  'name': 'stroke_opacity',
  'size': 1,
  'type': 'Float'},
 {'depth': 0,
  'foldertype': 'folderType.TabbedMultiparmBlock',
  'help': '',
  'hidden': True,
  'label': 'Number of Strokes',
  'name': 'stroke_numstrokes',
  'type': 'Folder'},
 {'default': True,
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Enable Stroke',
  'name': 'stroke#_enable',
  'type': 'Toggle'},
 {'default': [0.1],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Radius',
  'max': 1.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': True,
  'name': 'stroke#_radius',
  'size': 1,
  'type': 'Float'},
 {'default': [0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Tool',
  'max': 10,
  'maxlock': False,
  'min': 0,
  'minlock': False,
  'name': 'stroke#_tool',
  'size': 1,
  'type': 'Int'},
 {'default': [1.0, 1.0, 1.0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Stroke Color',
  'max': 1.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'stroke#_color',
  'size': 3,
  'type': 'Float'},
 {'default': [1.0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Opacity',
  'max': 10.0,
  'maxlock': False,
  'min': 0.0,
  'minlock': False,
  'name': 'stroke#_opacity',
  'size': 1,
  'type': 'Float'},
 {'default': [0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Projection',
  'max': 10,
  'maxlock': False,
  'min': 0,
  'minlock': False,
  'name': 'stroke#_projtype',
  'size': 1,
  'type': 'Int'},
 {'default': [0.0, 0.0, 0.0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Projection Center',
  'max': 1.0,
  'maxlock': False,
  'min': -1.0,
  'minlock': False,
  'name': 'stroke#_projcenter',
  'size': 3,
  'type': 'Float'},
 {'default': [0.0, 0.0, 0.0],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Projection Direction',
  'max': 1.0,
  'maxlock': False,
  'min': -1.0,
  'minlock': False,
  'name': 'stroke#_projdir',
  'size': 3,
  'type': 'Float'},
 {'default': [''],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Raw Data',
  'name': 'stroke#_data',
  'type': 'String'},
 {'default': [''],
  'depth': 1,
  'help': '',
  'hidden': True,
  'label': 'Meta Data',
  'name': 'stroke#_metadata',
  'type': 'String'}]

NODES = [{'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['divide4'],
  'name': 'attribpaint1',
  'parms': {'attribname1': 'mask',
            'bakedgeo': 'ch("../bakedgeo")',
            'folder0': 1,
            'folder0_11': 4,
            'stroke_float': 1.0,
            'stroke_int': 1,
            'stroke_numstrokes': 'ch("../stroke_numstrokes")',
            'stroke_opacity': 'ch("../stroke_opacity")',
            'stroke_radius': 0.09999999999999999,
            'strokegeo': 'ch("../strokegeo")',
            'unsavedbakedgeo': 'ch("../unsavedbakedgeo")'},
  'pos': [2.70884, 8.82948],
  'type': 'attribpaint'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['box1'],
  'name': 'IN',
  'parms': {},
  'pos': [1.11759e-08, 12.786],
  'type': 'null'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['peak1'],
  'name': 'apply_mask_bias',
  'parms': {'snippet': 'float mask = 1.0-@mask;\n'
                       '@P += @N * (mask * 0.1 - @mask * chf("../damage_depth"));'},
  'pos': [2.70584, 3.49821],
  'type': 'attribwrangle'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['remesh3'],
  'name': 'mountain2',
  'parms': {'amplitude': 'ch("../amplitude")',
            'attribs': 'P',
            'basis': 'ch("../basis")',
            'displace': 1,
            'elementsize': 'ch("../elementsize")',
            'folder1': 1,
            'folder2': 1,
            'folder4': 1,
            'folder5': 1,
            'folder7': 1,
            'fractal': 'ch("../fractal")',
            'lac': 'ch("../lac")',
            'oct': 'ch("../oct")',
            'remapramp2pos': 1.0,
            'remapramp2value': 1.0,
            'rough': 'ch("../rough")'},
  'pos': [2.70884, 6.20456],
  'type': 'attribnoise::2.0'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['IN'],
  'name': 'matchsize2',
  'parms': {'doscale': 1, 'stashxform': 1},
  'pos': [1.11759e-08, 11.7047],
  'type': 'matchsize'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['matchsize2'],
  'name': 'divide3',
  'parms': {'brick': 1,
            'convex': 0,
            'sizex': 'ch("../paint_resolution")',
            'sizey': 'ch("../paint_resolution")',
            'sizez': 'ch("../paint_resolution")',
            'usemaxsides': 0},
  'pos': [2.70884, 10.6855],
  'type': 'divide'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['divide3'],
  'name': 'divide4',
  'parms': {},
  'pos': [2.70884, 9.72401],
  'type': 'divide'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['attribpaint1'],
  'name': 'attribblur2',
  'parms': {'iterations': 'ch("../blur_iterations")'},
  'pos': [2.70884, 7.83588],
  'type': 'attribblur'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['attribblur2'],
  'name': 'remesh3',
  'parms': {'targetsize': 'ch("../damage_resolution")*0.5'},
  'pos': [2.70884, 6.96988],
  'type': 'remesh::2.0'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['matchsize2', 'normal4'],
  'name': 'boolean2',
  'parms': {'binsidea': 'pf_chipped', 'booleanop': 1, 'usebinsidea': 1},
  'pos': [0.1417, -2.96608],
  'type': 'boolean::2.0'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['switch1'],
  'name': 'normal4',
  'parms': {'cuspangle': 0.0},
  'pos': [2.70884, -1.87126],
  'type': 'normal'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['apply_mask_bias'],
  'name': 'vdbfrompolygons2',
  'parms': {'exteriorbandvoxels': 1,
            'interiorbandvoxels': 5,
            'voxelsize': 'ch("../damage_resolution")*0.25'},
  'pos': [2.70759, 2.67162],
  'type': 'vdbfrompolygons'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['vdbfrompolygons2'],
  'name': 'convertvdb2',
  'parms': {'conversion': 2},
  'pos': [2.70759, 1.86662],
  'type': 'convertvdb'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['convertvdb2'],
  'name': 'polyreduce1',
  'parms': {'percentage': 'ch("../target_mesh_percentage")'},
  'pos': [4.06597, 0.57932],
  'type': 'polyreduce::2.0'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['convertvdb2'],
  'name': 'remesh4',
  'parms': {'targetsize': 'ch("../target_mesh_size")'},
  'pos': [1.39823, 0.57932],
  'type': 'remesh::2.0'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['mountain2'],
  'name': 'peak1',
  'parms': {'dist': 'ch("../dist")'},
  'pos': [2.70884, 4.92121],
  'type': 'peak'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['remesh4', 'polyreduce1'],
  'name': 'switch1',
  'parms': {'input': 'ch("../damage_meshing")'},
  'pos': [2.70884, -0.585466],
  'type': 'switch'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['boolean2'],
  'name': 'matchsize1',
  'parms': {'restorexform': 1},
  'pos': [-2.52668, -5.66201],
  'type': 'matchsize'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['matchsize1', 'boolean2', 'MASK_MERGE', 'BOOLEAN_GEO_MERGE'],
  'name': 'VisualizationMode',
  'parms': {'input': 'ch("../visual_mode")'},
  'pos': [0.1417, -7.49501],
  'type': 'switch'},
 {'flags': {'bypass': False, 'display': True, 'render': True},
  'in': ['VisualizationMode'],
  'name': 'output0',
  'parms': {'outputidx': 0},
  'pos': [0.1417, -8.44203],
  'type': 'output'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': ['switch1'],
  'name': 'BOOLEAN_GEO',
  'parms': {},
  'pos': [6.40568, -1.87626],
  'type': 'null'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': [],
  'name': 'MASK_MERGE',
  'parms': {'objpath1': '../MASK'},
  'pos': [1.69757, -5.16204],
  'type': 'object_merge'},
 {'flags': {'bypass': False, 'display': False, 'render': False},
  'in': [],
  'name': 'BOOLEAN_GEO_MERGE',
  'parms': {'objpath1': '../BOOLEAN_GEO'},
  'pos': [3.18168, -6.3722],
  'type': 'object_merge'}]

# attribpaint1's per-stroke instance links (hscript `opmultiparm` pairs).
STROKE_LINKS = "'stroke#_enable' '../stroke#_enable' 'stroke#_radius' '../stroke#_radius' 'stroke#_tool' '../stroke#_tool' 'stroke#_opacity' '../stroke#_opacity' 'stroke#_projtype' '../stroke#_projtype' 'stroke#_projcenterx' '../stroke#_projcenterx' 'stroke#_projcentery' '../stroke#_projcentery' 'stroke#_projcenterz' '../stroke#_projcenterz' 'stroke#_projdirx' '../stroke#_projdirx' 'stroke#_projdiry' '../stroke#_projdiry' 'stroke#_projdirz' '../stroke#_projdirz' 'stroke#_data' '../stroke#_data' 'stroke#_metadata' '../stroke#_metadata'"

VIEWER_STATE = '"""\nState:          Edge Damage Paint Viewer\nState type:     Quentin::paint_edge_damage::1.0\nDescription:    Quentin::paint edge damage::1.0\nAuthor:         Quentin\nDate Created:   February 24, 2024 - 13:44:18\n"""\n\nimport hou\nimport viewerstate.utils as su\nfrom sidefx_stroke import StrokeState, StrokeCursor\nfrom sidefx_stroke import createStrokeStateTemplate\nimport toolutils\nimport soputils\nfrom enum import Enum\n\nclass VISUAL_MODES(Enum):\n    OUTPUT = 0\n    PAINTABLE = 1\n    MASK = 2\n    BOOLEAN = 3\n\nclass State(StrokeState):\n    DEFAULT_CURSOR_PROMPT = "MMB to resize cursor. CTRL+MMB to adjust damage strength"\n\n    HUD_TEMPLATE = {\n        "title": "Edge Damage Paint", "desc": "tool", "icon": "SOP_attribpaint",\n        "rows": [\n            {"id": "radius", "label": "Brush Radius", "value": "1.0", "key": "mousewheel"},\n            {"id": "radius_g", "type": "bargraph"},\n            {"id": "strength", "label": "Damage Strength", "value": "1.0"},\n            {"id": "strength_g", "type": "bargraph"},\n        ]\n    }\n    \n    def __init__(self, **kwargs):\n        super(State, self).__init__(**kwargs)\n\n        self.cursor.prompt = State.DEFAULT_CURSOR_PROMPT\n        \n        self.cursor.brushes = []\n        self.cursor.init_brushlist([(\'sphere\', {})])\n\n        self.root_node = None               # Our HDA node\n        self.paint_node = None              # The attribute paint node that we\'re leveraging\n\n        self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)\n\n    def get_paint_node(self, parentNode):\n        """\n            Finds the attribute paint node within the HDA\n        """\n        return toolutils.findChildNodeOfType(parentNode, \'attribpaint\', True)\n    \n    def resize_strength(self, node, dist):\n        """\n            Adjusts painting strength\n        """\n        scale = dist * 0.05\n        stroke_strength = self.root_node.parm("stroke_float")\n        if stroke_strength is None:\n            return\n        strength = stroke_strength.evalAsFloat()\n        strength += scale\n        stroke_strength.set(strength)\n\n    def get_paint_attribute(self):\n        """\n            Gets the attribute name and type we are painting on to\n        """\n        attrib_idx = self.paint_node.evalParm("attribute")\n        attrib_name = self.paint_node.evalParm("attribname" + str(attrib_idx + 1))\n        attrib_type = self.paint_node.evalParm("attribtype" + str(attrib_idx + 1))\n        return (attrib_name, attrib_type)\n\n    def set_visualizer_active(self, scene_viewer, is_active):\n        """\n            Enables / disables the attribute visualizer to the viewport, for the mask display mode\n        """\n        viewports = scene_viewer.viewports()\n        cur_viewport = scene_viewer.curViewport()\n\n        if len(viewports) == 0 or cur_viewport is None:\n            return False\n        \n        for viewport in viewports:\n            soputils.turnOffVisualizers(hou.viewportVisualizers.type(\'vis_color\'), hou.viewportVisualizerCategory.Scene, None, viewport)\n        \n        attribname, attribtype = self.get_paint_attribute()\n        viz = soputils.findVisualizer(attribname, hou.viewportVisualizerCategory.Scene, None)\n        if viz is None:  # pf port: the reference scene carried this visualizer; a fresh scene does not\n            viz = hou.viewportVisualizers.createVisualizer(hou.viewportVisualizers.type(\'vis_color\'), hou.viewportVisualizerCategory.Scene)\n            soputils.setupVisualizer(viz, attribname, soputils.getMaskVisualizerDefaults())\n        \n        for viewport in viewports:\n            viz.setIsActive(is_active, viewport)\n\n            if isinstance(viewport, hou.GeometryViewport):\n                if is_active:\n                    bbox = self.paint_node.geometry().boundingBox()\n                    viewport.frameBoundingBox(bbox)\n                else:\n                    bbox = self.root_node.geometry().boundingBox()\n                    viewport.frameBoundingBox(bbox)\n\n    def update_hint_panel(self):\n        """\n            Updates viewport UI\n        """\n        radius = self.root_node.parm("stroke_radius").evalAsFloat()\n        strength = self.root_node.parm("stroke_float").evalAsFloat()\n\n        rows = {\n            "radius": "%0.2f" % radius,\n            "radius_g": radius,\n            "strength": "%0.2f" % strength,\n            "strength_g": strength,\n        }\n\n        self.scene_viewer.hudInfo(values=rows)\n\n    def set_visualization(self, mode):\n        """\n            Sets display mode\n        """\n        self.set_visualizer_active(self.scene_viewer, False)\n        if mode == VISUAL_MODES.OUTPUT:\n            self.root_node.parm("visual_mode").set(0)\n        elif mode == VISUAL_MODES.PAINTABLE:\n            self.root_node.parm("visual_mode").set(1)\n        elif mode == VISUAL_MODES.MASK:\n            self.set_visualizer_active(self.scene_viewer, True)\n            self.root_node.parm("visual_mode").set(2)\n        elif mode == VISUAL_MODES.BOOLEAN:\n            self.root_node.parm("visual_mode").set(3)\n\n    def onParmChanged(self, **kwargs):\n        """\n            Custom callback whenever a parameter changes\n        """\n        self.update_hint_panel()\n\n    def onEnter(self, kwargs):\n        super(State, self).onEnter(kwargs)\n        \n        node = kwargs[\'node\']\n        self.root_node = node\n        self.paint_node = self.get_paint_node(node)\n\n        self.set_visualization(VISUAL_MODES.PAINTABLE)\n        self.scene_viewer.hudInfo(show=True)\n        self.update_hint_panel()\n        \n        node.addEventCallback([hou.nodeEventType.ParmTupleChanged],\n                        self.onParmChanged)\n        \n        # Force focus on the paintable geometry\n        self.root_node.cook(force=True)\n        for v in self.scene_viewer.viewports():\n            v.frameBoundingBox(self.root_node.geometry().boundingBox())\n            v.draw()\n\n    def onExit(self, kwargs):\n        super(State, self).onExit(kwargs)\n\n        self.set_visualization(VISUAL_MODES.OUTPUT)\n\n        node = kwargs.get("node")\n        if node:\n            node.removeEventCallback([hou.nodeEventType.ParmTupleChanged],\n                                        self.onParmChanged)\n            \n        # Force focus back on the output geometry\n        self.root_node.cook(force=True)\n        for v in self.scene_viewer.viewports():\n            v.frameBoundingBox(self.root_node.geometry().boundingBox())\n            v.draw()\n\n    def intersectGeometry(self, node):\n        """\n            Returns the geometry the stroke uses for intersection tests\n        """\n        if self.intersect_geometry is None:\n            self.intersect_geometry = self.paint_node.geometry()\n        else:\n            if self.intersect_geometry.sopNode() != self.paint_node:\n                self.intersect_geometry = self.paint_node.geometry()\n\n        return self.intersect_geometry\n    \n    def onPostApplyStroke(self, node, ui_event, captured_parms):\n        """\n            Cache strokes for better performance\n        """\n        if self.root_node.parm(\'stroke_numstrokes\').eval():\n            post_geometry = self.paint_node.node(\'POST_APPLY_EACH_STROKE\').geometry()\n            if post_geometry is not None:\n                post_geometry = post_geometry.freeze(True, True)\n\n            self.paint_node.parm(\'bakedgeo\').set(post_geometry)\n            self.paint_node.parm(\'unsavedbakedgeo\').set(None)\n\n            strokes_parm = self.paint_node.parm(\'strokegeo\') \n            stroke_geo = self.paint_node.node(\'all_strokes\').geometry().freeze(True, True)\n            strokes_parm.set(stroke_geo)\n            self.root_node.parm(\'stroke_numstrokes\').set(0)\n        \n    def onMouseWheelEvent(self, kwargs):\n        """ \n            Either resize cursor or change damage intensity\n        """\n        ui_event = kwargs[\'ui_event\']\n        node = kwargs[\'node\']\n        dist = ui_event.device().mouseWheel()\n        dist *= 10.0\n\n        if ui_event.device().isShiftKey():\n            dist *= StrokeState.CURSOR_DRAG_FACTOR\n\n        if ui_event.device().isCtrlKey():\n            self.resize_strength(node, dist)\n        else:\n            self.resize_cursor(node, dist) # Defined in base stroke class\n\n    def onMenuAction(self, kwargs):\n        """\n            Menu actions\n        """\n        menu_item = kwargs[\'menu_item\']\n        node = kwargs[\'node\']\n        if menu_item == \'display_mode\':\n            mode = kwargs[\'display_mode\']\n            self.log(mode)\n            if mode == "paint_display":\n                self.set_visualization(VISUAL_MODES.PAINTABLE)\n            elif mode == "output_display":\n                self.set_visualization(VISUAL_MODES.OUTPUT)\n            elif mode == "mask_display":\n                self.set_visualization(VISUAL_MODES.MASK)\n            elif mode == "boolean_display":\n                self.set_visualization(VISUAL_MODES.BOOLEAN)\n\ndef reset(node):\n    """\n        Zero\'s out current strokes\n    """\n    paint_node = toolutils.findChildNodeOfType(node, \'attribpaint\', True)\n    paint_node.parm(\'bakedgeo\').set(None)\n    paint_node.parm(\'unsavedbakedgeo\').set(None)\n    paint_node.parm(\'strokegeo\').set(None)\n    node.parm(\'stroke_numstrokes\').set(0)\n\ndef createViewerStateTemplate():\n    state_typename = kwargs["type"].definition().sections()["DefaultState"].contents()\n    state_label = "Edge Damage Paint"\n    state_cat = hou.sopNodeTypeCategory()\n\n    t = hou.ViewerStateTemplate(state_typename, state_label, state_cat)\n    t.bindFactory(State)    \n    t.bindIcon(kwargs["type"].icon())\n\n    hotkey_definitions = hou.PluginHotkeyDefinitions()\n    realtime = su.defineHotkey(hotkey_definitions,\n        state_typename, \'realtime_mode\', \'0\', \'realtime\', \'Enable realtime mode\')\n    set_paint_display = su.defineHotkey(hotkey_definitions,\n        state_typename, \'set_paint_display\', \'1\', \'View paintable geometry\')\n    set_output_display = su.defineHotkey(hotkey_definitions,\n        state_typename, \'set_output_display\', \'2\', \'View output geometry\')\n    set_mask_display = su.defineHotkey(hotkey_definitions,\n        state_typename, \'set_mask_display\', \'3\', \'View mask geometry\')\n    set_boolean_display = su.defineHotkey(hotkey_definitions,\n        state_typename, \'set_boolean_display\', \'4\', \'View boolean geometry\')\n    t.bindHotkeyDefinitions(hotkey_definitions)\n\n    m = hou.ViewerStateMenu(\'paint_damage_menu\', \'Paint Edge Damage\')\n    m.addToggleItem(\'realtime_mode\', \'Draw realtime\', True, hotkey=realtime)\n    m.addSeparator()\n    m.addRadioStrip(\'display_mode\', \'Display mode\', \'paint_display\')\n    m.addRadioStripItem(\'display_mode\', \'paint_display\', \'Paintable Geometry\', hotkey=set_paint_display)\n    m.addRadioStripItem(\'display_mode\', \'output_display\', \'Output Geometry\', hotkey=set_output_display)\n    m.addRadioStripItem(\'display_mode\', \'mask_display\', \'Mask Geometry\', hotkey=set_mask_display)\n    m.addRadioStripItem(\'display_mode\', \'boolean_display\', \'Boolean Geometry\', hotkey=set_boolean_display)\n    m.addSeparator()\n\n    t.bindMenu(m)\n\n    return t'


def _template(p):
    t = p["type"]
    if t == "Separator":
        return hou.SeparatorParmTemplate(p["name"])
    if t == "Label":
        return hou.LabelParmTemplate(p["name"], p["label"])
    if t == "Data":
        return hou.DataParmTemplate(p["name"], p["label"], 1,
                                    data_parm_type=hou.dataParmType.Geometry)
    if t == "Button":
        b = hou.ButtonParmTemplate(p["name"], p["label"])
        b.setScriptCallback(p["callback"])
        b.setScriptCallbackLanguage(hou.scriptLanguage.Python)
        return b
    if t == "Toggle":
        return hou.ToggleParmTemplate(p["name"], p["label"], bool(p["default"]))
    if t == "String":
        return hou.StringParmTemplate(p["name"], p["label"], 1,
                                      default_value=tuple(p["default"]))
    if t == "Menu":
        return hou.MenuParmTemplate(p["name"], p["label"], tuple(p["items"]),
                                    menu_labels=tuple(p["labels"]),
                                    default_value=p["default"])
    if t == "Int":
        return hou.IntParmTemplate(p["name"], p["label"], p["size"],
                                   tuple(p["default"]), min=p["min"], max=p["max"],
                                   min_is_strict=p["minlock"], max_is_strict=p["maxlock"])
    if t == "Float":
        return hou.FloatParmTemplate(p["name"], p["label"], p["size"],
                                     tuple(p["default"]), min=p["min"], max=p["max"],
                                     min_is_strict=p["minlock"], max_is_strict=p["maxlock"])
    if t == "Folder":
        ft = {"Simple": hou.folderType.Simple, "Collapsible": hou.folderType.Collapsible,
              "Tabs": hou.folderType.Tabs, "MultiparmBlock": hou.folderType.MultiparmBlock,
              "TabbedMultiparmBlock": hou.folderType.TabbedMultiparmBlock,
              "ScrollingMultiparmBlock": hou.folderType.ScrollingMultiparmBlock,
              "ImportBlock": hou.folderType.ImportBlock}[p["foldertype"].split(".")[-1]]
        return hou.FolderParmTemplate(p["name"], p["label"], folder_type=ft)
    raise ValueError(p)


def build_ptg():
    """PARMS is a flat pre-order list with depths; rebuild the tree."""
    ptg = hou.ParmTemplateGroup()
    stack = []                       # (depth, folder template)
    made = []
    for p in PARMS:
        t = _template(p)
        if p["help"]:
            t.setHelp(p["help"])
        if p["hidden"]:
            t.hide(True)
        while stack and stack[-1][0] >= p["depth"]:
            stack.pop()
        made.append((p["depth"], t, stack[-1][1] if stack else None))
        if p["type"] == "Folder":
            stack.append((p["depth"], t))
    # attach children to folders bottom-up, then roots to the group
    for depth, t, parent in reversed(made):
        if parent is not None:
            parent.addParmTemplate(t)
    for depth, t, parent in made:
        if parent is None:
            ptg.append(t)
    return ptg


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_" + NAME)
subnet = build_geo.createNode("subnet", NAME)
hda_node = subnet.createDigitalAsset(
    name=NAME, hda_file_name=HDA_PATH, description=TAB_LABEL,
    min_num_inputs=1, max_num_inputs=1, version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(1)
defn.setMaxNumInputs(1)
defn.setIcon(ICON)
net = hda_node
for c in list(net.children()):
    c.destroy()

# nodes first, wiring second (inputs reference nodes by name)
made = {}
for n in NODES:
    node = net.createNode(n["type"], n["name"])
    node.setPosition(hou.Vector2(*n["pos"]))
    made[n["name"]] = node
for n in NODES:
    node = made[n["name"]]
    for i, src in enumerate(n["in"]):
        if src is None:
            continue
        if src in made:
            node.setInput(i, made[src])
        else:                        # the reference's "box1" = the asset input
            node.setInput(i, net.indirectInputs()[0])
    for pname, val in n["parms"].items():
        parm = node.parm(pname)
        if isinstance(val, str) and val.startswith("ch("):
            parm.setExpression(val)
        else:
            parm.set(val)
    if n["flags"]["display"]:
        node.setDisplayFlag(True)
    if n["flags"]["render"]:
        node.setRenderFlag(True)
    if n["flags"]["bypass"]:
        node.bypass(True)

_err = hou.hscript("opmultiparm %s %s" % (made["attribpaint1"].path(), STROKE_LINKS))[1]
assert not _err, "opmultiparm: " + _err

# the reference's multiparm is attribpaint's own; copy its template so the
# instance parms match the native node exactly
_tp = obj.createNode("geo", "_tmpl").createNode("attribpaint")
_strokes = _tp.parmTemplateGroup().find("stroke_numstrokes")
_tp.parent().destroy()

ptg = build_ptg()
ptg.replace("stroke_numstrokes", _strokes)
_sn = ptg.find("stroke_numstrokes")
_sn.hide(True)
ptg.replace("stroke_numstrokes", _sn)
defn.setParmTemplateGroup(ptg)

hda_node.setUserData("nodeshape", "chevron_down")
defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

defn = hou.hda.definitionsInFile(HDA_PATH)[0]
defn.addSection("Tools.shelf", TOOLS_SHELF)
typename = defn.nodeTypeName()
defn.addSection("DefaultState", typename)
defn.addSection("ViewerStateName.orig", typename)
defn.addSection("ViewerStateModule", VIEWER_STATE)
defn.addSection("ViewerStateInstall",
                "__import__('viewerstate.utils', fromlist=[None])"
                ".register_pystate_embedded(kwargs['type'])")
defn.addSection("ViewerStateUninstall",
                "__import__('viewerstate.utils', fromlist=[None])"
                ".unregister_pystate_embedded(kwargs['type'])")
for _sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule",
             "ViewerStateName.orig"):
    defn.setExtraFileOption(_sec + "/IsPython", True)
    defn.setExtraFileOption(_sec + "/IsScript", True)
for _sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule"):
    defn.setExtraFileOption(_sec + "/IsViewerState", True)

hda_node.destroy()
build_geo.destroy()

back = hou.hda.definitionsInFile(HDA_PATH)[0]
assert back.sections()["ViewerStateModule"].contents() == VIEWER_STATE
assert back.sections()["DefaultState"].contents() == back.nodeTypeName()
assert back.extraFileOptions().get("ViewerStateInstall/IsPython")
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents()
print("wrote " + HDA_PATH)
