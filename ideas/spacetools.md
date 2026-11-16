# spacetools — five Blender/other space-art tools recreated in Houdini

Branch `spacetools` (worktree `F:\projects\polyfactory-spacetools`). Owner doc for this work; each tool has a section below.
Requested by Hannes 2026-11-16: understand the five tools, recreate them in Houdini, in polyfactory.

| # | Source | Becomes | Output |
|---|---|---|---|
| 1 | Starship Generator 1.1.0 (Blender geo-nodes) | SOP HDA `pf::starship_generator` | mesh |
| 2 | Plating Generator + Greebles 2.0 (Blender python) | SOP HDA(s) `pf::plating_generator`, `pf::greeble_scatter` | mesh |
| 3 | Nebula Generator 3.0.3 (Blender shader/volume) | Copernicus/SOP mix, `pf::nebula_generator` | HDR equirect + cubemap EXR |
| 4 | Spacescape (github.com/petrocket/spacescape, C++) | `pf::spacescape` | HDR skybox cubemap EXR |
| 5 | Custom Planet 1.0 (Blender, EXR layer library) | `pf::custom_planet` | planet textures (cubemap/equirect EXR) |

Sources unpacked in `F:\cache\spacetools` (`starship/`, `plating/`, `greebles/`, `planet_addon/`, `planet_img/`).
Blender 4.5.16 portable installed at `F:\ai\blender\blender-4.5.16-windows-x64\blender.exe` (2026-11-16).
Node-graph dumps (JSON) of the .blend files: `F:\cache\spacetools\dump\*.json`; dumper `dump_nodes.py`, reader `summ.py <json> [group-name-substring...]`.

## Conventions
`ideas/conventions.md` (pf_ prefix, `_*` internals deleted before output), `ideas/artist_ui.md`, HDAs built by a `devScripts/create_pf_<name>_hda.py` script run in hython; HDA files in `polyfactory/otls/`.
Dev loop: headless hython, never save a .hip; independent audit before "done" (until then: "implemented, unverified").

## Status / resume pointer
(each tool's agent appends its section below: design, decisions, what is verified, known gaps)

## Shared: space_direction / cubemap
Status: implemented, unverified (no independent audit yet). Owner: nebula agent. Other tools (spacescape, custom planet) consume this.

**HDA** `pf_space_direction` (COP, `polyfactory/otls/pf_space_direction.hda`, built by `devScripts/create_pf_space_direction_hda.py`; type name uses the existing `pf_` COP convention, not `pf::`). No inputs. Parms: `layout` (0 equirect 4N x 2N, 1 cube cross 4N x 3N horizontal cross, 2 single face N x N), `face` (0..5 = +X -X +Y -Y +Z -Z), `res` = face size N, `convention` (0 Houdini, 1 Godot), `outres` (read-only result size). Outputs: `dir` (RGB float32 unit direction of the pixel centre; 0,0,0 in the empty cross corners) and `mask` (1 inside layout). Size is set by an inner constant -> resample driven by `outres` and fed to the OpenCL node as a metadata input (the copnet default 1024 is ignored).

**Conventions.** Y-up, right-handed. Cube faces use the OpenGL cube-face orientation (b runs downward in the image), cross layout: row0 `_ +Y _ _`, row1 `-X +Z +X -Z`, row2 `_ -Y _ _`. Equirect: v = acos(y)/pi, row 0 = top; Godot: u = atan2(x,-z)/2pi (verified in Godot `sky.glsl`, so +Z is the image centre); Houdini: same shifted half a turn, so -Z is the centre (ASSUMED, not verified in a Houdini viewer - only the yaw differs between the two). COP buffers start at the bottom row; `bake.layer_array` flips to EXR top-first.

**How a consumer uses it** (pick one):
1. Inline: `import pf_space_common as sc` (devScripts), prepend `sc.PF_SPACE_DIR_CL` to the kernel and call `float4 r = pf_space_dir(@ix,@iy,@xres,@yres,@layout,@face,@convention)` (xyz direction, w valid). The consumer kernel needs a metadata/size input (see create_pf_space_direction_hda.py: constant -> resample -> input 1 `!size_ref?`, type 7, optional) or an upstream layer to set the size.
2. Layer: put the sub-parm folder `sc.layout_parm_folder()` on the HDA, build the inner `sc.add_direction_node(subnet, ocl, input_index)` and bind `#bind layer dir float3` in the kernel.
`sc.make_cop_hda(...)` builds a COP subnet HDA headless (outputs multiparm must be set before `createDigitalAsset`; the asset then has no `outputs` parm).

**Baking** (hython): `from polyfactory.spacetools import bake` (add `polyfactory/scripts/python` to sys.path). `bake.bake_set(node, outdir, name, res, layouts=("equirect","faces","cross"), layer_index=0, half=False)` needs the node to expose int parms `layout`, `face`, `res`; writes `<name>_equirect.exr`, `_cross.exr`, `_px/_nx/_py/_ny/_pz/_nz.exr` (float32 ZIP, `half=True` for 16-bit) and restores the parms. `bake.check_set(paths)` = seam check: equirect resampled at every face pixel vs the face, 12 cube-edge continuity ratios (edge pixel vs neighbour-face pixel over own gradient; ~1 good), cross == faces, finite. `polyfactory.spacetools.sky` is a numpy reference of the layouts (independent oracle), samplers and the seam maths.

**Check**: `hython tests/spacetools/run_space_direction.py` (kernel == numpy reference for all layouts/faces/conventions, unit length, bake+seams, centre direction per convention). Mutation seen red: flipping one sign in the +X face. Cannot see: viewer-side orientation of the Houdini convention; a consumer's own content.
