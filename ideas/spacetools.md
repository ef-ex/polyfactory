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

## Starship generator

**Status: implemented, unverified** (no independent audit yet). Asset `polyfactory/otls/pf_starship_generator.hda`
(op `pf::starship_generator`, TAB: Poly Factory/Modeling, no inputs), built by
`devScripts/create_pf_starship_generator_hda.py`, checks `tests/spacetools/run_starship_checks.py`
(`hython tests/spacetools/run_starship_checks.py [nseeds]`). Renders: `F:/cache/spacetools/starship_work/*.png`.

### How the Blender tool works (read from the .blend dump)
The `Starship` object is only a cube; everything is modifiers. One seed drives everything.
1. **A "part" (Main Object, 5 Medium, 5 Small objects, all the same recipe)**: Random Extrusion Nodes = cube, Subdivide Mesh level 2
   (4x4 per side), Jiggle Y/X/Z (each axis coordinate scaled by `2 * noise(that coordinate, seed)`), random per-axis scale
   (default x 0.5-1.2, y(length) 4-8, z 0.5 on a 2 m cube), Random Extrude (noise ramp mask picks faces, `< Amount 0.5`; each extruded
   individually by rand(0..1) along the normal, top scaled rand(0.8..1.2)).
   Then Remesh modifier (SMOOTH, octree depth 4, scale 0.9), Mirror (bisect X), Cleanup (delete mesh islands != 0),
   Center (bbox centre to origin), Creased Subdivide (noise -> ramp 0.389-0.615 -> edge crease 0.2-0.8, level 3/2/1 for
   main/medium/small), Auto Smooth 30 deg.
2. **Starship** object: Big Object (instance the Main Object) -> Scatter Object x2 (medium, then small): Shape Distribution
   = Mesh to Volume/Volume to Mesh shell of the geometry so far, Distribute Points on Faces (density 0.1), snap to the surface
   (Geometry Proximity), instance a random collection member, translate along the normal by rand(offset 0.1-0.4 / 0-0.2), rotate in
   whole steps of (0,90,0) deg, scale rand(0.4-0.6 / 0.1-0.2); the 2nd scatter sees the first's result (small on medium) ->
   Panelling (Subdivide, then 3 layers [large 0.03 / small 0.01 / micro 0.003] of face extrusion on Voronoi cells with
   Randomness 0 = a plain grid, cell picked by a noise ramp) -> Booster (raycast along the length axis from +/-100 to the hull,
   instance "Booster Variable": 16-gon cylinder, end cap scaled .8 / pushed in .5 / scaled .8 / out .1; scale 0.5) -> Materials ->
   Mirror (bisect + merge) -> Resize (uniform, length 15) -> UV Project -> Auto Smooth.
3. Text objects (Get/Link/Seed Text), cameras, materials (MAT: nodes) are presentation, not geometry: not recreated.

### Mapping to Houdini (all native nodes + VEX; the only Python is the builder script / parameter interface)
| Blender | Houdini |
|---|---|
| Cube + Subdivide Mesh 2 | `box` polymesh, divrate 5 (4x4, 96 quads) |
| Jiggle XYZ + Random Vector | wrangle `*_shape` (noise of the coordinate itself, `1 + Jiggle*(2n-1)`, then lerp scale) |
| Random Extrude | wrangle `*_extsel` (noise ramp mask, `zscale`, `_tap`) + `polyextrude::2.0` individual (`zscale` attr) + wrangle `*_taper` on `extrudeFront` |
| Remesh smooth octree depth d | `vdbfrompolygons` voxel = longest side / (0.9 * 2^d) + `convertvdb` to polygons |
| Mirror bisect X (hull only) | `mirror` (clip, keep original, consolidate 0.001) behind a switch |
| Cleanup (islands) | `connectivity` + detail wrangle (biggest island) + prim wrangle `removeprim`; (Blender keeps island 0) |
| Center | `matchsize` to origin |
| Creased Subdivide | vertex wrangle (`creaseweight` per edge from noise at the edge midpoint, `* level * 3`) + `subdivide` OSD cc |
| For each of N variants | `block_begin`(input) / `block_begin`(metadata) / `block_end`(count, merge) |
| Distribute + Instance on Points | `scatter::2.0` by density + wrangle (variant, scale, normal offset, orient steps) + `copytopoints::2.0` by `_variant` |
| Panelling | `subdivide` (osdbilinear) + 3 x (prim wrangle grid-cell hash -> group `_pnl`, `polyextrude::2.0` components along POINT normals) |
| Booster raycast | detail wrangle makes the ray origin, point wrangle `intersect()` onto the ship, `copytopoints` of a `tube` + 2 `polyextrude` nozzle |
| Mirror + Resize | `mirror`(clip) behind switch, `matchsize` uniform by Z = Length |
| Auto Smooth | `normal` vertex, cusp = Smooth Angle |

Output (conventions): `pf_part` prim int (0 hull, 1 medium, 2 small, 3 booster), `pf_panel` prim int (0 plain, 1/2/3 layer),
`pf_material` prim string (`hull`/`booster`), vertex `N`. Nothing else, no groups; `_*` swept (see "Decisions").

### Decisions (with reasons)
- **Axes**: length along Z, ship symmetric in X, nose -Z, engine +Z (Houdini forward = -Z). Blender's length axis is Y.
- **Jiggle** = `1 + Jiggle*(2*noise-1)`; Blender is `2*noise`. Houdini `noise` is not Blender's normalised FBM; the shape of the range is similar, not equal.
- **Remesh**: VDB SDF -> polygons instead of Blender's smooth remesh; same voxel size rule. Not the same surface, same character.
- **Hull/part default subdivision**: hull 2 (Blender's object modifier 3, but the Starship Controls say 2), medium/small 1, for cook time (see below).
- **Crease sharpness** = `crease * level * 3`. Blender crease 1 = sharp for ever; the x3 was LOOKED AT against the reference render (boxy parts); it is a guess, not read from the file.
- **Scatter**: points are scattered on the surface itself, not on the Mesh-to-Volume shell snapped back (the shell only smooths the distribution). Normal = scatter normal.
- **Booster count**: one (Blender: one, doubled by the mirror when Projection X != 0).
- **Panels**: Blender's per-layer cell sizes/noise thresholds could not be read from the dump; cell = Panel Size, /2, /4 with a hash `< Panel Amount`.
  Panels extrude along POINT normals: `components` mode with the default face normal moved a whole region along ONE average normal (measured: bbox 57x138x40 instead of 9.6x3.7x17).
- **`_*` hygiene**: a `sweep` (scaffold wrangles create one `_s` of each class, then `attribdelete _*`) so the delete never warns "no match"; node-required leftovers `creaseweight`/`name` removed there too.
- **Zero-area faces** (2-6 per 250k from the mirror seam / extrusions) are removed at the end rather than traced; unfixed root cause.
- Python is used for nothing but the HDA builder (nodes, parms, help). Nothing inexpressible in native nodes/VEX turned up.

### Not done / gaps
No UVs (Blender's UV Project), no materials/shader, no text objects, no multiple boosters or booster variants, no interactive "Blueprint"/displacement example setups
(`example_starship_*.blend` use displacement/window lights on top of the same geometry), no Mesh-to-Volume shell for scatter,
no `Seed Add` per-part fine control (variants derive from one seed), no custom collections (Blender lets you drop in your own parts).
Cook: default ~10 s and ~90-170k faces (Panel Subdivision defaults to 0; 1 quadruples it) (varies by seed); Detail 5 takes over a minute. Not benchmarked beyond that.
Mirror seam of the booster at x=0 and the welding of parts crossing x=0 were not inspected closely.

### Verification (current build)
`tests/spacetools/run_starship_checks.py`: c1 clean cook for 10 seeds (every node, no error/warning), c2 non-empty/finite/Length exact/zero-area, c3 deterministic,
c4 10 different ships, c5 no `_*` + exact attribute whitelist + storage + no groups, c6 each parm branch with its expected effect.
Mutations seen red (`PF_MUTATE=<name> hython ...`): boost_off (5 checks), panels_off (3), mirror_off (the "points balanced in X" check; the bbox-symmetry check alone stayed green, so it was added), no_cleanup (attribute whitelist), no_zero_removal (zero-area). Last full run: 10 seeds, 0 fails.
CANNOT SEE: whether it looks like the original (compare images by eye), self-intersections, mirror-seam watertightness.
**Next**: independent audit (coordinator), then the interface pass (presets/help screenshots).
