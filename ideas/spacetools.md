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

## Spacescape
Status: **implemented, unverified by audit** (own check `hython tests/spacetools/run_spacescape_checks.py` ALL PASS). HDA `pf_spacescape` (COP, `polyfactory/otls/pf_spacescape.hda`; `pf_` type name like the other COP HDAs, not `pf::`), built by `devScripts/create_pf_spacescape_hda.py` from `pf_spacescape_kernel.py` (OpenCL) and `pf_spacescape_module.py` (PythonModule: presets, bake). Source studied: github.com/petrocket/spacescape (MIT) in `F:\cache\spacetools\spacescape`.

### How Spacescape works (read from `SpacescapePlugin/src`)
- A profile is an XML list of layers (`save/*.xml`, 5 shipped examples), drawn bottom to top into 6 cube faces (90 deg FOV render targets), each layer blended with Ogre scene-blend factors `sourceBlendFactor`/`destBlendFactor` (one, zero, dest/src colour, one-minus-..., dest/src alpha, one-minus-...). Export = 6 images `_RT _LF _UP _DN _FT _BK` (png, or float32 exr/dds when HDR is on).
- **Noise layer** (GLSL in `SpacescapeNoiseMaterial.cpp`): 3D Perlin noise evaluated on the *normalised cube-direction* (that is why faces match). `fbm`: sum of octaves, amplitude *= gain, frequency *= lacunarity, divided by the amplitude sum. `ridged`: `ridge(n)=(offset-|n|)^2`, each octave weighted by the previous one. Then `n=n*.5+.5`; `shelf`: `max(0,n-shelf)/(1-shelf)`; `power`: `n^(1/power)`; dither = a 2-octave fbm at direction*10000 times `ditherAmount`; colour = `mix(outerColor,innerColor,n)*hdrMultiplier` (after `n^hdrPower`), alpha = `n*hdrMultiplier`. Params: noiseType, seed, scale, octaves, lacunarity, gain, offset, powerAmount, shelfAmount, ditherAmount, innerColor, outerColor, hdrPower, hdrMultiplier, blend factors.
- **Point stars**: `numPoints` random directions (uniform on the sphere), colour = lerp(nearColor, farColor, random distance^hdrPower)*hdrMultiplier, GL point sprites of `pointSize` pixels. Optional mask (`maskEnabled` + a noise cube map with maskNoiseType/Seed/Scale/Octaves/Lacunarity/Gain/Offset/Power/Threshold): a candidate star is kept when `rand < mask^2`.
- **Billboard stars**: same placement/colour/mask, a textured quad per star (flare PNG/EXR textures in `media/materials/textures`), size = minSize + (maxSize-minSize)*(1-distance). `dataFile` can load a real star catalogue (`stars.csv`: x,y,z,absmag,distance).
- No separate sun or gradient layer: the sun is a billboard with `sun.png`.

### Mapping to the HDA
| Spacescape | `pf_spacescape` |
|---|---|
| noise layer fbm / ridged | layer type Noise, identical formulas (own gradient-noise hash instead of the permutation textures; seeds are not bit-compatible with Spacescape) |
| inner/outer colour | colour in/out + optional middle colour and position (3-stop ramp; a native ramp parm cannot be bound per multiparm instance) |
| point stars | Point Stars; evaluated procedurally per pixel (cube-face cell grids, up to 5x5 cells searched, density compensated for the gnomonic grid), Gaussian dot sized in real pixels (Star Size Reference 0) or in pixels of a reference face width |
| billboard stars + flare textures | Billboard Stars with a procedural flare (core, glow, optional 4 spikes); size in degrees; textures/`dataFile` catalogue not ported (gap) |
| sun billboard | Sun / Flare layer (direction, angular radius, core/halo colours, HDR brightness, spikes) |
| (none) | Gradient / Band layer (galactic plane along an axis; masks give dust lanes) - an addition requested in the brief |
| blend factors, masks | same 10 Ogre factors per layer; mask = noise multiplier (noise/sun/gradient) or star acceptance (stars, mask^2) |
| profile xml | presets in `pf_spacescape_module.PRESETS` (Purple Nebula after `purple-nebula-complex.xml`, Green Nebula, Sun and Starfield); XML import not ported (gap) |
| 6 skybox faces | shared `pf_space_direction` layouts: equirect 4N x 2N, cross 4N x 3N, single face; EXR via `polyfactory.spacetools.bake` (`_px _nx _py _ny _pz _nz _cross _equirect`, float32) |

Everything is a function of the 3D direction, so faces, cross and equirect agree and nothing seams. The direction maths is the shared `pf_space_dir` (`pf_space_common.PF_SPACE_DIR_CL`, prepended to the kernel; convention parm Houdini/Godot).

### Design decisions
- One OpenCL COP, not a chain: layers are a multiparm (max 12, `MAXL` in the kernel script) bound to the kernel as 11 float4 constants per layer by per-component Python expressions (`create_pf_spacescape_hda.py`). Python expressions, not hscript `ch()`, so unused slots read 0 without "bad parameter reference" warnings. A cook of 8 layers at 2048x1024 takes about 1 s on the test machine's OpenCL device (not measured on Hannes' GPU).
- Native COP nodes were not used for the layers: stacking one Noise/Blend COP per layer would need a dynamic node count (Python/loop) and cannot place stars per direction.
- **Python is used for exactly two things** (justified): (1) presets/`on_created` fill the multiparm (a multiparm instance cannot carry per-instance defaults; a new node therefore cooks the Purple Nebula preset), (2) `bake()`: a loop over layout/face/resolution plus file writes, via the shared baker. The kernel, direction maths, blending, size chain are native/OpenCL.
- Star amplitude conserves energy below one pixel (`sigma=max(size, 0.5 px)`), so a 1 px star is ~0.64 peak: stars neither vanish nor flicker with resolution.

### Verified (own check, not an audit)
`tests/spacetools/run_spacescape_checks.py`: 3 stacks baked (6 faces + cross + equirect, N=192) - finite and >= 0, HDR max 31/61/124, median 0.04-0.26; cross == faces exactly; 12 cube-edge continuity ratio max 1.1-1.4 (median ~1); equirect vs faces rel. diff 0.03-0.13; bit-identical re-bake, other seeds differ (rel. 0.47), disabling star layers removes the peaks, 4x point count -> 4.00x energy. Checker self-tests (MUT, all seen red): shifted face raises the edge ratio (1.1 -> 2.4), NaN flagged, wrong equirect convention 4-8x worse. Looked at tonemapped equirect and cross PNGs (`F:\cache\spacetools\spacescape_work`). Cannot see: whether it is beautiful, stars below 1-2 px at edges vs equirect, GPU vs CPU OpenCL differences, anything in the GUI (parameter layout, TAB menu entry, help rendering are built but not looked at in a live Houdini).

### Known gaps / later
- Flare textures and `dataFile` star catalogue; XML profile import; true colour *ramp* parm (3-stop used); layer count capped at 12; seeds not compatible with Spacescape; no GUI review of the parameter panel; no independent audit yet.
