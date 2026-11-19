# spacetools — five Blender/other space-art tools recreated in Houdini (+ Shape Generator, tool #6 below)

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
- Tool 3 nebula + shared space_direction: look fixed and author-checked after the independent audit (`F:\cache\spacetoolsudit_sky\REPORT.md`); re-audit pending = "implemented, unverified"; resume = read the two sections below, run `hython tests/spacetools/run_space_direction.py` and `run_nebula.py`.

## Shared: space_direction / cubemap
Status: implemented, unverified (no independent audit yet). Owner: nebula agent. Other tools (spacescape, custom planet) consume this.

**HDA** `pf_space_direction` (COP, `polyfactory/otls/pf_space_direction.hda`, built by `devScripts/create_pf_space_direction_hda.py`; type name uses the existing `pf_` COP convention, not `pf::`). No inputs. Parms: `layout` (0 equirect 4N x 2N, 1 cube cross 4N x 3N horizontal cross, 2 single face N x N), `face` (0..5 = +X -X +Y -Y +Z -Z), `res` = face size N, `convention` (0 Houdini/Karma, 1 Godot: same mapping), `outres` (read-only result size). Outputs: `dir` (RGB float32 unit direction of the pixel centre; 0,0,0 in the empty cross corners) and `mask` (1 inside layout). Size is set by an inner constant -> resample driven by `outres` and fed to the OpenCL node as a metadata input (the copnet default 1024 is ignored).

**Conventions.** Y-up, right-handed. Cube faces use the OpenGL cube-face orientation (b runs downward in the image), cross layout: row0 `_ +Y _ _`, row1 `-X +Z +X -Z`, row2 `_ -Y _ _`. Equirect: v = acos(y)/pi, row 0 = top, u = atan2(x,-z)/2pi: **the image centre is +Z and +X is at u = 0.25 for both conventions** (Godot per `sky.glsl`; Houdini/Karma per the OpenEXR/USD lat-long spec, which SideFX's own Karma dome light help (`lop/domelight`, in the local help `nodes.zip`) quotes: "latitude 0, longitude 0 points into positive z, longitude pi/2 into positive x"; the legacy Mantra `envlight` help only says the top pole is +Y). The first version put -Z in the centre for Houdini (a guess) - the audit showed it contradicts the dome light, so `convention` 0 was changed (both menu entries are identical now; `sky.sample_equirect(conv=2)` is the old yaw, used only as a wrong-yaw mutant). Consumers that kept their own copy of the old formula (e.g. `pf::planet_preview` VEX, `u = atan2(x,-z)/2pi + 0.5`) or a compiled `pf_space_dir` (pf_custom_planet) must be rebuilt/edited by their owner. Not verified in a Karma viewer (husk has no licence in hython). COP buffers start at the bottom row; `bake.layer_array` flips to EXR top-first.

**Face size cap.** The `res` parm is strict, max 4096 (equirect 16384 x 8192, cross 16384 x 12288): measured on the RTX 5060 Ti, N = 4096 cooks and reads back for pf_space_direction, pf_nebula_generator and pf_spacescape, a cross at N = 5792 and an equirect at 8192 fail with CL_INVALID_BUFFER_SIZE. **TAB menu:** the three HDAs carry a `Tools.shelf` section with `Poly Factory/Space` (`pf_space_common.add_tab_submenu`, same mechanism as pf_starship_generator's Poly Factory/Modeling; COP context, `coptoolutils.genericTool`); present in the saved definition, not looked at in the GUI.

**How a consumer uses it** (pick one):
1. Inline: `import pf_space_common as sc` (devScripts), prepend `sc.PF_SPACE_DIR_CL` to the kernel and call `float4 r = pf_space_dir(@ix,@iy,@xres,@yres,@layout,@face,@convention)` (xyz direction, w valid). The consumer kernel needs a metadata/size input (see create_pf_space_direction_hda.py: constant -> resample -> input 1 `!size_ref?`, type 7, optional) or an upstream layer to set the size.
2. Layer: put the sub-parm folder `sc.layout_parm_folder()` on the HDA, build the inner `sc.add_direction_node(subnet, ocl, input_index)` and bind `#bind layer dir float3` in the kernel.
`sc.make_cop_hda(...)` builds a COP subnet HDA headless (outputs multiparm must be set before `createDigitalAsset`; the asset then has no `outputs` parm).

**Baking** (hython): `from polyfactory.spacetools import bake` (add `polyfactory/scripts/python` to sys.path). `bake.bake_set(node, outdir, name, res, layouts=("equirect","faces","cross"), layer_index=0, half=False)` needs the node to expose int parms `layout`, `face`, `res`; writes `<name>_equirect.exr`, `_cross.exr`, `_px/_nx/_py/_ny/_pz/_nz.exr` (float32 ZIP, `half=True` for 16-bit) and restores the parms. `bake.check_set(paths)` = seam check: equirect resampled at every face pixel vs the face, 12 cube-edge continuity ratios (edge pixel vs neighbour-face pixel over own gradient; ~1 good), cross == faces, finite. `polyfactory.spacetools.sky` is a numpy reference of the layouts (independent oracle), samplers and the seam maths.

**Check**: `hython tests/spacetools/run_space_direction.py` (kernel == numpy reference for all layouts/faces/conventions, unit length, bake+seams, centre +Z / u=0.25 = +X / top = +Y for both conventions). Mutation seen red: flipping one sign in the +X face. Cannot see: a Karma viewer showing the dome (the doc evidence above stands in); a consumer's own content.

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

## Nebula generator
Status: look fixed against EEVEE renders and re-checked by the author (`run_nebula.py`, numbers below); **the independent re-audit of the fix is still pending** ("implemented, unverified" until then). `pf_nebula_generator` (COP, `polyfactory/otls/pf_nebula_generator.hda`), built by `devScripts/create_pf_nebula_generator_hda.py` from `polyfactory/ocl/pf_nebula_generator.cl`; 19 presets in `polyfactory/scripts/python/polyfactory/spacetools/nebula_presets.json` (built by `devScripts/nebula_blender_to_presets.py`). Uses the shared layout parms (equirect / cross / face, face size N, max 4096) from "Shared: space_direction / cubemap". Outputs `color` (RGB linear HDR radiance) and `alpha` (1 - transmittance). Bake: `bake.bake_set(node, outdir, name, res)`. TAB menu: Poly Factory/Space.

**How the Blender tool works** (3.0.3, dumps in `F:\cache\spacetools\dump`, parameter dumps `F:\cache\spacetools\nebula_work\presets*`). The reference PNGs `nebula_ref` are EEVEE Next + compositor (Bloom/Glare 4, lens distortion) + AgX, so they are *not* linear radiance; the numbers below compare against linear EEVEE EXRs (`nebula_work/lin`, scripts `render_var.py` / `render_eevee_exr.py`: Standard view, compositor off). The look is a *volume shader on a box object* (scale 122.73) seen by a camera inside it:
- **Noise coordinates come from the object `Empty` (scale 85.545), not from the box (122.73)** (`Texture Coordinate.001` -> Object = Empty): the noise position is `p_box * 122.73 / 85.545`, parm `noise_unit`. Missing this made the cloud 1.43x too small and uncorrelated with the reference (structure r 0.05-0.6); fixed: **r = 1.000 against a Cycles render of the gas, 0.84-0.999 against EEVEE** for the four compared presets. The falloff (`Texture Coordinate`, object None) uses the box.
- Position = Mapping(rotate(p*scale)+location); `n9` FBM (scale 0.11..1.11) is the scale of the cloud noise, `n8` FBM (scale 20) x 0.5 its distortion; density = `main_ramp(t) * main_mult` (constant-step ramp: hard DUST lanes) + `gas_ramp(t) * 0.015`, in world units (x volume_unit per box unit). The gas colour ramp is looked up with the GAS DENSITY, then two Hue/Sat/Val groups; dust blends the colour to black (absorbs, never scatters). Principled Volume albedo = colour, extinction = density (measured in a test cube: radiance = sigma_s * E / (4 pi), G/R of the albedo kept).
- **Lights: the gas is lit by the sun lamp (`Main Light`, strength 40, shadows) and by the large stars, NOT by a point lamp at the centre.** The `Sun` point lamp (2e6 W) lives in the `Large Sun` collection together with the `Large Star` plane; the geometry-nodes group `Large Stars` instances that whole collection, so each large star carries a 2e6 W point lamp (no shadows, 1/r^2) and the original at the origin is not rendered (hiding the large stars drops the gas to ~0). The previous port put one lamp at the centre: that was the "dim grey gas". The exact large-star positions are in the preset (`large_pos0..2`, volume units; 0 = hashed). The haze therefore takes the colour of the `sun_color` lamps times the gas ramp, e.g. red_lobster = orange star lamps on teal/orange gas; its blue sun is weak (self-shadowed by the dust).
- EEVEE units, measured with a one-voxel test cube: sun irradiance = strength (gain 1; the old `PF_LIGHT_GAIN = 2` was a guess); point lamp intensity = P/(4 pi) W/sr = P/(4 pi^2) x pi (gain pi).
- **EEVEE drops weakly scattering colour channels**: with grey gas colours k the radiance is linear above 0.1 but 0.45x at 0.01 and 0 at 0.005 (the G of a dark purple, 0.0088, keeps 0.2). Modelled per channel as a table (`pf_weak_colour`, parm `albedo_floor` = 0.0105, 0 = off). Without it dark gas is too grey/pale (purple_haze G was 4x too high).
- Transparency falloff: opacity = ramp(|p| / 1.39), a fuzzy ball of radius ~1.26 box units (the distorted box shape is not reproduced).
- Stars are instances of a 2x2 plane with a texture (`small_star.exr`, external, not in the files): ~2300 small ones (point-in-volume distribution; coverage mask = stars where the noise is BELOW the coverage; instance scale 0.01-0.5 = half-size in world units), 3 large ones (scale 1-5, brightness 19.4 x star colour ramp, a ~1 px core on screen), plus a world shader with two voronoi star dusts. The world dust renders far fainter in EEVEE than its node maths says (mean 3.7e-4 vs 1.8e-2: a low-res world probe, sparse 1 px dots).

**What we built.** One OpenCL kernel per output pixel: direction -> ray from the viewer (`view` x `view_dist`) through the falloff ball, N jittered steps, analytic extinction per step, in-scatter of the sun lamp (24-step shadow march through the same density at 4 octaves; 8 steps let too much light through, the sun was 2x too bright) and of the large-star lamps, then stars and the voronoi background. Decisions:
- **Noise is an exact port of Cycles' perlin/fbm/hash/voronoi** (`hash.h`, `noise.h`, `fractal_noise.h` of Blender 4.5), so a preset's Mapping location gives the *same pattern* as the .blend.
- **Small stars are a 3D cloud** (parm `star_radius` 1.2): per cube-face cell, probability = density along that direction x cell solid angle; the density grows with the ray length inside the ball cubed (a viewer near the edge sees many stars toward the far side and few outward, like the .blend); the star sits at a random depth, the coverage noise is read at that 3D point, the size is `0.18 * size / (distance * unit)`, brightness `star_strength` x ramp colour, dimmed by the transmittance at its depth. `star_count` per preset = `Density * unit^3 * 4.19 * 2.8` (the 2.8 is calibrated: visible peaks 323/340/785 vs EEVEE 264/348/661; the exact Blender point count is not reproducible, our stars never land where Blender's do, except the three large ones). Small-star energy equals the analytic value (check below).
- Large stars: exact preset positions, the same sprite as the small ones (strength 19.4); glare default 0 (it is a compositor effect; the 6-point streak stays as an option).
- Background voronoi stars: radius x0.25 (`PF_BG_R`) so the mean matches the EEVEE world probe.
- `view_dist` (default 0.4) scales the viewer position: 1 = the sample camera, which sits near the edge of the volume and fills one side of the sky only (the audit's "lopsided cloud, rest black"); 0.4 fills the whole sphere (`tests/spacetools/nebula_sky_sheet.py`). `nebula_vs_blender.py` sets 1.
- Python is used only for preset marshalling (`polyfactory.spacetools.nebula.apply_preset`) and baking. Ramps use the OpenCL node's raw ramp bindings (256 samples), so a constant-step ramp softens over 1/256 (dust edges are slightly soft).
- Ramp parm defaults are applied by the HDA `OnCreated` event (GUI only; hython tests call `apply_preset`).

**Look check (author, vs linear EEVEE, same camera and lights, 4 presets, `run_nebula.py` section 6; tonemapped side by side in `nebula_work/cmp/cmp_<preset>.png`):** mean luminance 0.92 / 1.41 / 0.96 / 1.33 (red_lobster, purple_haze, blue_sulaco, green_nemesis), per-channel medians within 0.63-1.78x, hue (channel shares) within 0.09, structure r 0.96 / 0.97 / 1.00 / 0.84, star peaks 323 / 340 / 785 vs 264 / 348 / 661 (green_nemesis has no small stars), no glare. red_lobster is now orange/green like the reference, purple_haze magenta, blue_sulaco blue, green_nemesis green. **Known remaining differences:** (1) ours shows thin bright filaments / dust-edge grain where EEVEE's froxel grid blurs them (purple_haze 1.4x too bright, its bright-pixel fraction 3x the reference); more `samples` helps, 2-4 recommended for finals; (2) no bloom/AgX (tonemap and glare belong to the consumer; the reference PNGs have bloom); (3) box-shaped boundary; (4) star positions; (5) the weak-colour table is an empirical fit of grey-gas renders (+-15%).

**Performance** (RTX 5060 Ti, OpenCL GPU): 1k x 512 equirect 0.4 s (samples 1, 96 steps); the 24 shadow steps cost ~1.5x of the old 8; N=4096 (16384x8192 equirect, 2.7 GB) cooks and reads back in ~5 s at 16 steps (measured limit; the face-size parm is capped at 4096, N=8192 gave CL_INVALID_BUFFER_SIZE).

**Verification** (author, `hython tests/spacetools/run_nebula.py`; `NEB_FAST=1` runs only the section-5 subset): finite / HDR, bit-identical re-cook, seed, 19 presets cook, bake seams (equirect vs faces with a swapped-face mutant 2x+ worse, cube-edge ratio median ~1 / max ~2, cross == faces, wrap, poles), Cycles oracle r = 1.000 (shifted noise location drops it to 0.4), section 5 (one check per surviving audit mutation: exposure, alpha = 1-T, dust never scatters, sun shadow march, global value / saturation, background stars present and faint, small-star energy against the analytic value, star colour per star) and section 6 (the look proxy above). Mutation driver `tests/spacetools/audit_sky_mutate.py` (nb_* entries; `NEB_FAST=1 python tests/spacetools/audit_sky_mutate.py nb_dustmix ...`):
All 16 mutants seen red: audit survivors nb_dustmix, nb_starcount, nb_starramp, nb_exposure, nb_alpha, nb_bg, nb_shadow, nb_hue (global hue/sat/val), nb_starstrength (each by its section-5 check, NEB_FAST) plus nb_pointlamp, nb_sungain (sun gain 2x), nb_lampgain (lamp gain 1 instead of pi), nb_weak (no weak-colour table), nb_noiseunit (Cycles oracle + look), nb_stardepth (size independent of distance), nb_bgsize (bg radius x4); sd_yaw in the space_direction suite. Not re-run: the earlier-red nb_gasramp, nb_seed, nb_largecount, nb_octmod (their checks are unchanged).
Cannot see: GUI behaviour (OnCreated, parameter layout, TAB entry), Houdini/Karma viewer orientation, anything beyond the 4 compared presets (the other 15 presets only cook finite).

## Custom planet
Status: **implemented, unverified by independent audit** (own check `hython tests/spacetools/run_planet_checks.py` ALL PASS). HDAs `pf_custom_planet` (COP, `polyfactory/otls/pf_custom_planet.hda`) and `pf::planet_preview` (SOP, `pf_planet_preview.hda`); COP type name `pf_` like the other COP HDAs. Built by `devScripts/create_pf_custom_planet_hda.py` (kernel `pf_planet_kernel.py`, PythonModule `pf_custom_planet_module.py`) and `create_pf_planet_preview_hda.py`. Source: addon `F:\cache\spacetools\planet_addon\CustomPlanetAddon`, library `planet_img\CustomPlanetImages` (~4 GB, not in git; `$PF_PLANET_IMAGES` or the *Image Library* parm, default `F:/cache/spacetools/planet_img/CustomPlanetImages`).

### How the addon works (read from `__init__.py`, `CP_functions.py` and the node graph of `Library.blend`)
- **It is a sprite, not a sphere.** `create_planet` adds a 1x1 plane (scaled 5000, 20000 away) that a Damped-Track constraint keeps facing an empty; the material `MATERIAL_PREFAB` is an emission shader that composites ready-made 2D EXR images in the plane's UV space. The "planet" is a picture.
- **Library** (`1k/2k/4k`, 4k = 2.8 GB): every image is a 1:1 square holding an *orthographic disc* of radius 0.3857 (alpha edge 0.1143..0.8857) and is read per layer: `Surface` 30 (colour+alpha, `_LS00`), `Water` 17 (a mask), `Emission` 18 (city lights / lava veins), `Clouds` 18 and `Atmosphere` 4 (big..very small), each in 5 pre-lit variants `LS00..LS04`, `Atmosphere/WhiteRim` (one ring), `LightSetup_00..04` (the shading disc itself: LS00 flat, 01 thin crescent, 02 crescent, 03 half, 04 gibbous, HDR up to 3.8), `Mask` (a disc). **LS = Light Setup**: choosing one swaps clouds/atmosphere/lightsetup to that variant; surface, water, emission always use LS00.
- **The shader** (traced node by node and checked against Blender renders): surface -> Bright/Contrast (contrast*0.25) -> HSV -> *Tint* (multiply) -> optional colour ramp on luminance (+ second HSV/contrast) -> mixed with a desaturated copy by `clamp(lightLuma/0.011)` (night side keeps half the saturation) -> water: `mix(surface, waterColour, lum(waterMask)*blend)`, then `mix(waterColour, ., surfaceAlpha)` -> x LightSetup (lighten with `shadowBrightness*0.01`) -> x mask disc -> **+ emission** (HSV with value = strength; hidden on the lit side by `1 - lum(light)*(1-shadowVisibility)`; hidden over water) -> **clouds** `mix(., gamma(rgb, 1.23-shadowBrightness)*brightness, alpha*thickness*blend)` -> **+ atmosphere** (gamma, saturation, *hue replaced by the picked colour*, factor = `alpha*strength*(1-c+c*(1-5.14*g))` with `c` = Center Strength and `g` a quadratic-sphere gradient scaled 1.03 around the plane centre) -> **+ white rim** (`lum(rim)*strength`, x lightSetup) -> x Emission shader strength (2). Outside a circle of ~0.39 the shader adds on top of transparency, so the alpha of the sprite is the disc mask.
- Blender quirk reproduced: an image node returns the *un-premultiplied* colour only when its Alpha output is linked, so surface, clouds and atmosphere are divided by alpha and water, emission and white rim are read raw.
- Panel: Transformation (planet scale, location, rotation: object transforms, not in the picture), Overall (emission strength, shadow brightness, resolution), Surface, LightSetup, Water, Emission, Clouds, Atmosphere, Starfield Background (a world shader with noise/voronoi stars, not ported: `pf_spacescape` is that tool).

### Mapping to the HDAs
| Addon | `pf_custom_planet` |
|---|---|
| picks per layer (icon views) | Library folder: Surface (Procedural + 30 named), Water/Emission/Clouds (None, Procedural, n), Atmosphere (None, Procedural, 4), Light Setup (procedural sun + 5), Library Resolution |
| Surface/Water/Emission/Clouds/Atmosphere sliders | folders of the same names with the same maths; Hue is shown as a shift (addon 0.5 = neutral), rotation in degrees (addon: radians) |
| picture of a lit sprite | **Output = Billboard** (N x N, outputs `beauty` RGBA premult-additive, alpha = disc) |
| (none: the addon has no maps) | **Output = Sphere maps**: `surface`, `clouds` (rgb + opacity), `emission`, `water`, `height`, `normal` (object space 0..1) and `beauty` (unlit composite) as equirect / cube faces / cross through the shared `pf_space_dir` layouts and `bake.bake_set` |
| missing images | per layer fallback to the procedural generator (6 planet types: Terran, Desert, Ice, Lava, Gas giant, Moon), seed/scale/roughness/sea level/polar ice/cloud coverage |
| Planet Scale / Location / Rotation | Longitude / Latitude / Spin of the disc on the sphere (sphere maps) and of the procedural planet (billboard); scale is the Billboard Size |

**Sphere maps from the discs.** A library image is an orthographic view of one hemisphere. In sphere mode the direction is rotated into the view frame (z = longitude/latitude, up = +Y), `uv = 0.5 + 0.3857*(x, y)` and the disc is sampled; the back hemisphere uses the same uv (**mirrored**, continuous at the limb by symmetry; the radius is clamped to 0.985 to stay off the soft limb pixels). Height for library surfaces is the surface luminance; the normal map is a per-direction finite difference of the height (3 taps), so it has no seams. Procedural layers need none of this and cover the whole sphere seam-free. `pf::planet_preview` (native sphere + one point wrangle) wears the baked equirects (albedo, clouds, emission, height displacement, light, rim).

### Decisions
- One OpenCL COP, 8 outputs, parms packed as float4 slots (`PARMS` table); library images through 8 File COPs (`missingdata = Use Color`, aov `C`); the kernel gets `have_*`/`*_proc` flags from the PythonModule.
- **Python (justified):** (1) library file marshalling - which EXR a menu pick means and whether it exists (an expression cannot test a file; an empty File COP name is an error); (2) `bake()` - loop over maps/layouts/faces plus file writes via the shared baker. Everything else (all maths, sampling, procedural planets, the preview colouring) is OpenCL / VEX.
- Emission is clamped at `>= 0` where the water mask exceeds 1 (Blender goes negative there; a map must not).
- The preview is point colour, not a shader, so it works in any viewport; the rim uses a fixed View Direction parm.
- The procedural planets are my own (the addon has none): the look is a first guess, tuned by eye on equirect + sphere views only.

### Verified (own check, not an audit)
`hython tests/spacetools/run_planet_checks.py` ALL PASS (about 3 min incl. Blender renders; references cached in `F:\cache\spacetools\planet_work\ref`): billboard vs **real Blender renders of the addon's own shader** (3 configs: default, water+emission+rotations+light 1, grade/tint/contrast/rotation/atmosphere colour/white rim): 8x8-block mean|diff|/mean 0.003 / 0.036 / 0.003 (full-res 0.01-0.02 except thin emission lines), alpha mean identical to 4 digits; mutations (hue 0.2 off, emission strength cut) 6-80x worse. Sphere maps of 3 planets x 7 maps x (6 faces + cross + equirect) at N=128: finite and >= 0, cross == faces exactly, cube-edge ratio max 1.27 / 1.99 / 1.26, equirect-vs-faces 0.2-6 %, bit-identical re-bake, other seed differs by 10 %, normals unit length; **library orientation oracle** (baked equirect at front-hemisphere directions vs the disc image at the independently derived uv, 0.087 vs 0.25 mirrored / 0.25 rolled 20 degrees); missing library cooks clean and is not black; `pf::planet_preview` Cd equals the equirect at the point direction to 4e-7 (mirrored lookup 0.18). Looked at: side-by-side PNGs vs Blender (`planet_work/ref/*_side.png`), equirect + sphere views (`planet_work/checks/*_equirect.png`, `*_sphere.png`).
Cannot see: beauty of the procedural planets, GPU-vs-CPU OpenCL differences, GUI (parm layout, TAB entry, help rendering built but not looked at in a live Houdini), the colour ramp against Blender, library layers other than those in the configs, the Blender view transform.

### Known gaps / later
- Sphere maps of library surfaces show the **mirrored back hemisphere** and stretched streaks where the disc limb is compressed (the addon has only one hemisphere); a second disc from another view could be blended in. No sphere-mode atmosphere map (the glow is view dependent; the preview SOP has a Fresnel rim).
- The colour ramp is a 3-stop ramp (a native ramp parm cannot be bound); the procedural looks are first guesses; the addon's icon-view thumbnails are not shown (picks are named menus).
- `Starfield Background` world shader of the addon: not ported (see Spacescape / Nebula).
- No independent audit yet; the preview SOP has no GUI check.

**Update (convention + audit fixes):** planet maps and `pf::planet_preview` use the shared `pf_space_dir` (Houdini equirect = Karma/USD lat-long, centre +Z, +X at u = 0.25, same as Godot); the preview VEX is `u = fract(atan2(x, -z) / 2pi)`. `run_planet_checks.py` has a marker check (points around +Z / +X show the equirect at u 0.5 / 0.25) next to the full re-projection check. Both HDAs have the TAB entry `Poly Factory/Space`. Cloud `Brightness` is 0..1 (measured against Blender: 1.4 renders exactly like 1.0, error 0.36 -> 0.05); the kernel clamps it too. Cloud `Thickness` stays 0..3 on purpose (alpha x thickness is clamped after the multiply, so >1 thickens the soft edges). Lava/city emission is clamped to 0..1 before the strength HSV and the x2 overall, as in the addon (mutation-tested), so it is left as is.

## Plating + greebles (tool #2: `pf::plating_generator`, `pf::greeble_scatter`)

Status: independent audit done (`F:\cache\spacetoolsudit_plating\REPORT.md`); its findings are fixed as listed under *Audit fixes* below, **implemented, not re-audited** by an independent agent. Own checks: `hython tests/spacetools/run_plating_checks.py` (35 pass) and `--mutate` (24 mutations, all red). Looked at renders in `F:\cache\spacetools\plating_work\` (`m1.png` layouts, `m2.png` sphere/box/L/tri, `m3.png` greebles). Build: `devScripts/create_pf_plating_generator_hda.py`, `create_pf_greeble_scatter_hda.py` (VEX in `devScripts/vex/pf_plating_*.vfl`, `pf_greeble_*.vfl`) -> `polyfactory/otls/pf_plating_generator.hda`, `pf_greeble_scatter.hda`. (`pf_hull_panels.hda` is a COP texture tool; not related.)

### How the Blender tool works
- **Plating** (`plating_gen/plating_functions.py create_plates`): subdivide, pick *groove edges* (pattern: random edge loops walked through valence-4 vertices that stop at an existing groove, optional diagonal "triangle" cuts, rectangle outlines, "Ruby Dragon" random-walk blobs, or selected/seam edges, plus cuts at sharp face angles), split faces into plate groups, sink the grooves (custom shrink/fatten), give each plate group a random height in [min,max], taper, bevel, corner bevel, rivets. Presets (`presets/panel/*.json`) are lists of *levels*; a later level plates the faces chosen from the earlier one (tops / grooves).
- **Greebles** (`greeble_gen/greeble_functions.py`): *overlapping* = N random rectangles (width/length fractions) on random faces; *non-overlapping* = every quad recursively `__quadsect`-ed into 4 cells with deviation, each cell gets a greeble with probability `coverage`. A greeble is "grafted" into the rectangle (footprint from the rectangle, height from range or kept aspect). Kits: 34 `.blend` pieces (Defaults, Hull Details, Panels, Custom Greebles).

### Mapping
- Layout: Criss-Cross, +Triangles, Rectangles, Rectangles+Criss-Cross, Irregular Blobs, From Edge Group. Plates = union-find over non-groove half-edges (halfedge VEX, one detail wrangle each for cut / plates). Groove ring + sink and raise/taper = `polyextrude::2.0` (split by connected component, per-plate distance through `_zs`); the plate split needed `edgecusp` on the `_split` edge group (polyextrude's own split-group parm did not separate plates in H22). Rim + vertical corner bevels = `polybevel::3.0`; rivets = copytopoints on convex top corners; `Cd` per plate optional.
- Output contract: prim `pf_plate_id` (int, -1 = untouched face), `pf_plate_area`, `pf_plate_height` (float), prim groups `pf_plate_top/side/groove/bottom/rivet`; greebles: prim `pf_greeble_id`, `pf_kit`, `pf_host` (int), `pf_kit_name`, group `pf_greeble`, plate attrs inherited from the host face. No `_*` left (test-enforced).
- **Levels** = chain nodes: next Plating Generator with *Faces* = `pf_plate_top`; Greeble Scatter *Faces* = `pf_plate_top` (on plates) or `pf_plate_side` (plate edges). Ids of a later level start after the earlier ones.
- Presets: all 19 Blender panel presets become the Plating Preset menu (level 0 values; multi-level ones say so in the label); the greeble presets set the Greeble Scatter parms. Preset callback is Python (UI marshalling, sets parm values from a JSON section).
- Kit: the 34 Blender pieces exported with Blender (`F:\cache\spacetools\greeble_export.py`, OBJs in `greeble_kit/`) and embedded in the HDA as `kit_blender.bgeo.sc`; every piece is normalised to a unit footprint on z=0 (kit-prep wrangle), input 2 takes any user kit (islands or `pf_kit`). Placement is one point per greeble + `copytopoints` (piece attribute `pf_kit`), no per-piece loops.

### Decisions / differences
- Python only in the two preset callbacks. Everything else native + VEX; no OpenCL (cell counts are small).
- Non-quads (tris, concave ngons) are triangulated then bilinear-subdivided at least once so every cell is a quad.
- Rim bevel is capped at 0.45x plate thickness, NaN points that polybevel can still produce on pole-tight sphere facets are dropped (not shipped). Gaps: bevels are native polybevel, so very small plates with big bevel values just get none.
- Triangle layout is not a pixel-faithful port (cut-walk uses a diagonal across the next quad); rectangles use cell counts like Blender, not world sizes. Random streams differ from numpy, so seeds do not reproduce Blender layouts.
- Not ported: the add-on's seam/selected-edge workflow beyond the Edge Group parm, vertex-colour options other than random per plate/greeble, custom-library picking UI, the Animation Nodes variant, level-based UI (replaced by chaining).

### Audit fixes (2nd pass)
- Zero-height plates (height + groove depth = 0, Blender presets 6-8 "Big Medium Small") get no side walls (`flat_plates` -> group `_flat`): no zero-area faces or non-manifold edges any more. With *Groove Floor = Remove* such flat plates are open single faces (nothing to close). Check `c_plating_topology` runs every preset on box + grid.
- Empty input is passed through, packed input is unpacked and plated, uv on the input (prim/point/vertex) is copied to the greebles from their host face: no cook warnings (`c_plating_odd_input`).
- Presets: `pre_subdivisions` is mapped to *Grid Subdivisions* (Blender: 0, so presets now use your own faces as cells; raise it for finer layouts). Presets 11/12 (level 0 is a GreebleDecorator) only reset the Plating HDA to defaults. Multi-level presets still apply level 0 only on the single plating node; use `pf::plating_preset` (below) for the complete chained result.
- Sphere pole region: root cause is a groove wider than the pole cells (inset folds the cell over: sliver faces, a few non-manifold edges and inverted tops, all vanish with Groove Width <= ~0.3x the smallest cell, e.g. 0.002 on the 16x32 test sphere). A per-face inset cap (`localinsetscale`) was tried and made irregular layouts worse (zero-area faces), so it is **documented, not fixed**; the audit still reports <=13 non-manifold edges / <=5 inverted tops per sphere preset.
- Rivets: *Rivet Diameter* was used as a radius (balls twice as wide as the label); now a diameter. Default *Rivet Detail* 6 -> 4: Rivets preset on the test sphere 565k prims / 49 s -> ~10 s (look unchanged at normal viewing size).
- New checks that kill the former unfailable mutations: `c_plating_details` (taper, rim bevel, corner bevel, rivets, random colour, `pf_plate_side` / `pf_plate_bottom`), `c_greeble_kit_choice`; each one seen red under its mutation in `run_plating_checks.py --mutate`.

### Layout / corner / groove fixes after the side-by-side review (v3, branch spacetools)
Hannes found square corners (preset 18) and "grid-like" irregular layouts (3, 9, 17). Root causes and what changed:
- **Rounded corners were never beveled on Blender's presets.** The `_corner` edge group (vertical wall edges, `pf_plating_edgegroups.vfl`) dropped every edge shorter than 1.5 x radius; a wall edge is only as high as the plate (0.01 in the presets) while the radius is 0.037, so nothing was selected (`_ncorner` 0), and the offset was also capped at 0.3 x that height. Now there is no length filter; the bevel spreads over the wall *width*, so the offset is scaled per corner point (`_bs`, `useoffsetscale`) by `min(1, 0.3 x narrowest adjacent wall / radius)`. Measured: single 0.23 plates have top fill 0.97645 in both Blender and ours (sharp = 1.0), 24 outline points each; rim and corner bevels (preset 9, Bevelled) checked by eye.
- **"Irregular" = Blender's Ruby Dragon (pattern 6), not a kd-tree.** Read from `ruby_dragon()`: a blob grows face by face, but the per-step neighbour choice re-seeds `RandomState(seed + blob)` every step, so the shuffled edge order is the SAME for the whole blob: it heads one way until blocked, then turns (long strips, snakes, big panels with small leftovers). Our walk picked a uniformly random neighbour (round blobs). `pf_plating_cut.vfl` now uses a fixed per-blob slot permutation and one fixed jump fraction (same re-seed). Criss-cross/triangles already matched (the T-junction look comes from loops stopping at existing cuts).
- **Preset seeds**: the preset `master_seed` is added to the pattern's seed (Blender `decorators.py`), now mapped into `seed` / `height_seed`; before, presets 3, 9, 17 all used the same seed and therefore the same layout.
- **Groove Width is now Blender's number**: the cut is a bevel with offset = Groove Width on each side, so neighbouring plates are 2 x Groove Width apart and the mesh border is pulled in by 1 x (measured on the original OBJs: gap 0.02 and border 1.99 for width 0.01). We had used half of it (default 0.02 -> 0.01 so the default look is unchanged).
- Checks (`run_plating_checks.py`, 67 pass): `c_plating_corner_roundness` (plate outline rounding vs r x (sqrt2-1) on flat and tall plates), `c_plating_layout_vs_original` (12 seeds of presets 1/3/18 on a 16x16-cell plane vs `plating_layout_ref.json`, built from the original add-on in Blender by `plating_layout_orig.py` + `plating_layout.py`: plate count, biggest-panel share, share in panels >= 32 cells, aspect, nesting, small-panel share, corner fill; within 1.5 sd of the original's mean over seeds). Ruby Dragon, ours vs original (mean of 12 seeds): plates 7.9 vs 8.4, biggest panel 0.27 vs 0.28 of the area, share in big panels 0.82 vs 0.80, nesting 0.30 vs 0.33; the old random walk gave 21.8 plates, 0.60 big share, nesting 0.79. Crisscross presets 1 / 18: 63 / 119 plates vs 62 / 119. Mutations seen red: random neighbour per step, 1.5 x radius length filter, corner offset x0.1, groove inset x0.5.
- Not fixed / open: preset 2 (triangles) has slightly more nesting than the original (0.08 vs 0.02) and 72 vs 67 plates; the aspect of Ruby Dragon plates is a little higher (3.2 vs 2.5, within 1 sd); preset 16 (Shattered) plate heights look taller than Blender's in the render (not investigated); random streams are not numpy's, so a given seed does not reproduce Blender's layout.

### Preset menu with all levels: `pf::plating_preset` (added)
One SOP HDA (`devScripts/create_pf_plating_preset_hda.py` -> `polyfactory/otls/pf_plating_preset.hda`, VEX `vex/pf_plating_preset_select.vfl`, TAB `Poly Factory/Modeling`). The artist picks a *Preset* (the 19 Blender presets + 5 "Greeble only" ones) and gets the complete chained result from one input surface to one output. Design: a fixed network of 10 level slots reusing `pf_plating_generator` / `pf_greeble_scatter`; slot n = switch source (input or an earlier level) -> `select` detail wrangle (group `_sel`) -> blast -> plating or greeble -> result switch (hidden "Frame" levels and levels beyond the count output nothing; greeble levels on a plate source output only the greebles). A *Levels* multiparm holds every value per level (type, show-in-result, source level, tops/edges, take-from/to %, all plating or greeble parms), so after a preset every level is tweakable and levels can be added/removed (max 10). Python only in the Preset callback (fills the multiparm from section `presets.json`, which is resolved from the Blender JSONs at build time).
- Blender's selection amount / "select remaining" became a ranked slice: plates are ranked by a seeded hash of `pf_plate_id` (*Selection Seed*), a level takes `[from%, to%)`, "remaining" levels start where the previous level on the same source ended (preset 6: 0-50, 50-75, 75-100). Exact counts, stable, but not Blender's random picks.
- The hidden zero-width "Frame" level (no side walls) is resolved at build time: a later level that takes its edges is pointed at the frame's own source (presets 7, 8, 14).
- Output always has prim attrs `pf_plate_id/area/height`, `pf_host`, `pf_greeble_id`, `pf_kit`, `pf_kit_name` (defaults -1 / "" where the level does not produce them, so the merge has no warnings); `Cd` only when a visible level uses random colour. Greeble kit per level: the five built-in sets (no custom input kit).
- Checks: `c_plating_preset_hda` in `run_plating_checks.py`: every preset 1-19 and the 5 greeble ones cook without warnings on a 4 m 16x16 plane, prim/point counts and positions equal a chain of standalone nodes built from the Blender JSON (max diff 0; the share selection of presets 6-8 is taken from the HDA's own select slot, so only its disjointness/non-empty is checked separately). 6 mutations seen red (level 2 / 4 dropped, greeble keeps surface, type switch, source switch, share ignored).
- Renders: `F:\cache\spacetools\plating_compare2\` (`ours_v2.py` builds from the new HDA, same camera). Presets 10, 13, 14 are pixel-identical to the old harness (as designed); 6, 7, 8 differ only through the new selection. Status: implemented, not audited; no GUI look at the new node's panel/multiparm.

### Not verified
No GUI look (TAB menu, help, panel layout never opened in a live Houdini); no GUI look (TAB menu, help, panel layout never opened in a live Houdini); overlap measured with axis-aligned boxes (exact on grid/box, conservative on curved/rotated cases); layout beauty only by my eye on renders; performance on large meshes untested (halfedge loops are single-threaded detail wrangles).

## Sky preview (`pf::sky_preview`, SOP)
Status: **implemented, unverified by independent audit; never looked at in a live viewport** (Hannes asked 2026-11-17: nebula and spacescape should preview inside a large sphere by default). `polyfactory/otls/pf_sky_preview.hda`, built by `devScripts/create_pf_sky_preview_hda.py`: sphere (radius 100) + reverse + one vertex wrangle that reads the COP live with `texture("op:<cop path>")` (works for Copernicus nodes, no bake), equirect convention of `pf_space_dir`, parms COP Node / Radius / Exposure / Tonemap (c/(1+c)) / Rows / Columns. `pf_nebula_generator` and `pf_spacescape` call `polyfactory.spacetools.sky.ensure_preview(node)` from OnCreated: GUI only, makes `/obj/<cop name>_sky_preview` (idempotent). Python is justified there: creating nodes in another network. The COP must stay in Equirect layout. Point colour (Cd), so lit by the viewport headlight (full bright with the camera at the centre).
Check: `hython tests/spacetools/check_sky_preview.py` (400 vertices vs numpy sampling of the COP's own pixels: corr 1.000, rel diff 0.000 for both tools; `--mutate` flips x and goes red). Cannot see: how it looks in the viewport, tonemap taste, a COP not in /obj-reachable network, cube layouts.

## Shape Generator (tool #6: `pf_shape_generator`, SOP, no input)
Status: **implemented, checks green, NOT yet independently audited, never opened in a live GUI** (Hannes asked 2026-11-19 to port Blender add-on "Shape Generator 1.7.9" by Mark Kingsnorth). Branch `shapegen` (worktree `F:\projects\polyfactory-shapegen`). Add-on unpacked in `F:\cache\shapegen\Shape Generator\sg179`; scratch in `F:\cache\shapegen\work`.
Files: `devScripts/create_pf_shape_generator_hda.py` (builds `polyfactory/otls/pf_shape_generator.hda`), `devScripts/vex/pf_shapegen_{generate,bevel,ops}.vfl`, tests `tests/spacetools/run_shapegen_checks.py` (+ `shapegen_common.py`, oracle generators `shapegen_ref_blender*.py`, oracle data `shapegen_ref_full.json`).

### How the Blender tool works
A shape = random box, then `amount` times: pick a face (weighted by `favour`), extrude, taper (scale about bbox centre), tilt about a random tangent through the old face centre, slide; the attempt is repeated while an edge pierces a face (`prevent_ovelapping_faces`). Then scale/location/rotation (optionally random per shape), subdivide edges. Big / medium / small levels: big sets 2.. sit on random surface points of set 1, medium on big, small on big+medium. Modifiers on top: Mirror (bisect + clip), Bevel (limit angle 30), Subsurf, Booleans (set / medium / small). Presets are python files setting `op.<prop>`.

### Mapping
`generate` detail wrangle emits every shape of every level as quads in world space (one execution), then `bevel_edges` (edge group + per-point width) -> `polybevel::3.0` -> per axis `clip` + `mirror` -> `subdivide` -> booleans (ONE feedback loop over an operation list from `ops.vfl`, in the add-on's modifier order) -> groups `pf_big/medium/small`, `pf_cutter`, Cd, `shop_materialpath`, normals -> clean. Prim attrs `pf_obj pf_level pf_set pf_setid pf_shape` (int). Parameter names = the add-on's (presets map 1:1; rotations in degrees). Python only in the Preset menu callback (sets parameter values from `presets.json`, the 13 add-on presets).

### Decisions (with reasons)
- **Bit-exact random numbers**: VEX has no seeded Mersenne Twister, so MT19937 is written in VEX (Python `random` seeding, `uniform`, `choice`; numpy `RandomState`, `choice`), verified against Python/numpy. Same seeds give the add-on's meshes: per-seed volume/area within 0.4% for all non-bevel cases (check A). Not exact for negative extrusions in ~5% of seeds (degenerate thin boxes).
- Blender quirks kept: `orthogonal()` is not unit length (slide x1.22-1.41); `recalc_face_normals` flips an inside-out box; box sides are `abs()` (a negative extrusion minimum); the function default for overlap prevention is False but the operator's is True.
- **Winding**: Houdini winds outward faces clockwise, Blender counter-clockwise. The emit reverses the vertex order; with Blender's order the boolean SOP swapped union and intersect (found by measurement).
- Bevel: Blender's width methods mapped to the per-edge distance (Offset d=w, Width d=w/(2cos(a/2)), Depth d=w/sin(a/2), Percent = % of the neighbouring edge length, all in OBJECT space via `_os`). `polybevel` limit = "individually" and sliding = "always": limit "never" explodes on thin shapes (spaceship_1 grew to 2000 units), sliding "auto" left open edges. Build with `PF_SG_SLIDING=2` (never) for Blender-like triangle counts (spaceship_x exact) but the transformer preset then blew up (size 46 vs 19), so "always" ships (+4% triangles).
- Bevel profile: 0.5 = round, below flattens to chamfer; above 0.5 not possible in Houdini. Clamp Overlap parameter dropped (Houdini cannot overlap bevels).

### Verified (own checks; no independent audit yet)
`hython tests/spacetools/run_shapegen_checks.py` OK (29 cases x 20 seeds vs the original add-on run headless in Blender 4.5: A per-seed parity, B aggregate parity for bevel/subsurf/presets - mean volume 5% (depth bevel 15%), triangles 10%, C no warnings / no `_*` leaks / outward / manifold, D preset + attribute storage). `--mutations`: flipped winding (C), fixed taper (A), bevel limit never (B) all go red. Regenerate the oracle: `blender -b --python tests/spacetools/shapegen_ref_blender_full.py -- tests/spacetools/shapegen_ref_full.json 20`.
Cannot see: Blender's bevel is not Houdini's (corner topology, overlap, profile > 0.5); boolean result area (coplanar faces merge differently); Blender's own non-manifold boolean output (`bool_both`, excluded); the transformer preset can leave open bevel edges; look in a live viewport.

### Known gaps / later
UV unwrap (add-on's Smart UV Project) not ported; the add-on's iterator / bake / animation-nodes operators not ported (Houdini does that with a Seed parameter and the Cache SOP); Houdini material picker for `material_to_use` untested in the GUI; performance on large `big/medium/small` counts untested (the generator is one single-threaded detail wrangle).
