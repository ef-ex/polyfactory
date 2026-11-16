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
- Tool 3 nebula + shared space_direction: implemented, unverified; resume = read the two sections below, run `hython tests/spacetools/run_space_direction.py` and `run_nebula.py`.

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

## Nebula generator
Status: implemented, unverified by an independent audit. `pf_nebula_generator` (COP, `polyfactory/otls/pf_nebula_generator.hda`), built by `devScripts/create_pf_nebula_generator_hda.py` from `polyfactory/ocl/pf_nebula_generator.cl`; 19 presets in `polyfactory/scripts/python/polyfactory/spacetools/nebula_presets.json`. Uses the shared layout parms (equirect / cross / face, face size N) from "Shared: space_direction / cubemap". Outputs `color` (RGB linear HDR radiance) and `alpha` (1 - transmittance). Bake: `bake.bake_set(node, outdir, name, res)`.

**How the Blender tool works** (3.0.3, dumps in `F:\cache\spacetools\dump`, parameter dumps `F:\cache\spacetools\nebula_work\presets*`, EEVEE reference PNGs `F:\cache\spacetools\nebula_ref`). The control panel addon only exposes node parameters. The look is a *volume shader on a box object* (scale 122.7) seen by a camera INSIDE it:
- Position p = Mapping(object coords: rotate(p*scale)+location). `n9` = FBM noise (scale 0.11) gives a slowly varying scale; `n8` = FBM (scale 20) x 0.5 gives a distortion amount; `t` = FBM(p * n9, distortion) is the cloud noise (16 octaves, normalised).
- Density = `main_ramp(t) * 50` (a constant-step ramp: hard-edged DUST lanes) + `gas_ramp(t) * 0.015`. Principled Volume, density in world units (so x122.7 per object unit): dust is opaque (tau ~5500/unit), gas translucent (~1.8/unit).
- Colour: gas colour ramp is looked up with the GAS DENSITY (not t), then Hue/Sat/Val, then overall Hue/Sat/Val (the "Color Controls" group); mixed to black by the dust density (dust absorbs, never scatters). No emission: everything is single scattering of two lights, an orange SUN lamp (40, shadows on) and a point lamp at the centre (2e6 W, 1/r^2, no shadows; custom cutoff off in all samples).
- Transparency falloff: opacity = ramp(|p| / 1.39), so the volume is a fuzzy ball of radius ~1.26 object units.
- Stars are mesh instances: 3 large ones (+ point light, glare added in the compositor), ~2300 small billboards (point-in-volume distribution, noise coverage mask, random colour from a ramp, emission 19.4), and a world shader with two voronoi star dusts (scale 44 and 200) masked by noise.
- The 18 samples differ only in: the two density ramps, gas colour ramp, noise params, Mapping, lights, star settings and star colour ramp (summarised by `devScripts/nebula_blender_to_presets.py`). `box distortion` (a geometry-nodes warp of the box mesh) only changes the box boundary and is not ported.

**What we built.** One OpenCL kernel per output pixel: direction -> ray from the viewer position (default = the sample camera, in object units) through the falloff ball, N jittered steps, analytic extinction per step, in-scatter with the sun lamp (+ a short shadow march through the same density at 4 octaves) and the point lamp, then stars (small stars on a cube-face cell grid with probability ~ cell solid angle so density is uniform; they are dimmed by the transmittance at a random depth, large stars with a 6-point glare, voronoi background). Decisions:
- **Noise is an exact port of Cycles' perlin/fbm/hash/voronoi** (`hash.h`, `noise.h`, `fractal_noise.h` from Blender 4.5; the distortion offsets from `random_float3_offset`), so a preset's Mapping location gives the *same pattern* as the .blend. Check: gas-only equirect vs a Cycles render of the same .blend: log-free blurred correlation r = 0.75 (0.03 when shifted 200 px). Octave caps on the modulation noises cost correlation (cap 8: 0.45), so they are not capped.
- The ball falloff replaces the box boundary; the box's distorted cube shape is not reproduced (the viewer sees a cube-ish cut in Blender, ours is spherical).
- Brightness: lights are in Blender units (sun 40, point 2e6 W). `PF_LIGHT_GAIN = 2`: measured against Cycles (equirect, same camera) our gas-only image wants gain ~0.8, with dust ~1.9; against an EEVEE render ~0.5. Cycles did not light the volume with the point lamp at all, EEVEE does (the sample PNGs are EEVEE). Treat absolute brightness as +-2x; use `exposure`. Not modelled: EEVEE bloom/glare/lens-distortion compositor, AgX tonemap (we output linear).
- Python is used only for preset marshalling (`polyfactory.spacetools.nebula.apply_preset`, ramps and vectors cannot be set from a menu) and baking (`bake.py`: read layer, write EXR). Everything pixel-level is OpenCL. Ramps use the OpenCL node's raw ramp bindings (`chrampraw`, 256 samples), so a constant-step ramp softens over 1/256.
- Ramp parm defaults are applied by the HDA `OnCreated` event (runs in the GUI; headless hython does not run it, tests call `apply_preset` themselves, so a node created in hython has 2-point default ramps until a preset is applied).
- Our stars do not land where Blender's do (point distribution is Blender-internal); counts/sizes/colours come from the presets, converted to angular radius assuming ~0.9 box radii distance. Sprite radius is widened to 0.7 pixel (energy kept) so sub-pixel stars do not flicker between resolutions. Large-star glare is our own function.
- Equirect Houdini-convention orientation unverified in a Houdini viewer (see shared section).

**Performance** (RTX 5060 Ti, OpenCL GPU): 1k x 512 equirect 0.4 s (samples 1, 96 steps, 4 shadow steps); 2048x1024 0.6 s; 4096x2048 1.6 s (octaves 12); samples=4 + 16 shadow steps at 2048x1024 about 5 s. 8-image bake (equirect + cross + 6 faces) at N=1024 (4096x2048): 22-37 s, mostly EXR writing (equirect 68 MB float32 ZIP).

**Verification so far** (author only, NOT an independent audit): `hython tests/spacetools/run_nebula.py` ALL PASS (finite/HDR range, bit-identical re-cook, seed changes image, 19 presets cook finite, bake seams: equirect vs faces at 4x4 block means with a swapped-face mutation >= 2x worse, 12 cube-edge continuity ratios < 3, cross == faces, wrap, poles, Cycles oracle r > 0.65 with a shifted-location mutation red). Bakes of default/blue_sulaco/green_nemesis at N=1024: no NaN/inf, max 66-139, deterministic, edge ratio max 1.25-1.70 (`tests/spacetools/bake_nebula_presets.py`, output `F:\cache\spacetools\nebula_work\bake\`). Looked at: equirect + cross PNGs, 19-preset contact sheet vs EEVEE references (`nebula_presets_sheet.py`): palettes and structure follow the references; ours is darker/starrier and has no bloom.
Cannot see: GUI behaviour (OnCreated, parm layout, TAB menu), viewer-side orientation, lighting accuracy beyond +-2x, preset parity beyond the default.

**Known gaps / next:** box-shape boundary; bloom/glare post; star placement parity; `green_purple`/`mutara`/`pea_soup` look different from their references (mutara is nearly dust-free in ours; its viewer sits where our falloff differs); tonemap helper; GUI check by the coordinator/Hannes.

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

## Plating + greebles (tool #2: `pf::plating_generator`, `pf::greeble_scatter`)

Status: **implemented, unverified** (no independent audit). Own checks: `hython tests/spacetools/run_plating_checks.py` (25 pass) and `--mutate` (10 mutations, all red). Looked at renders in `F:\cache\spacetools\plating_work\` (`m1.png` layouts, `m2.png` sphere/box/L/tri, `m3.png` greebles). Build: `devScripts/create_pf_plating_generator_hda.py`, `create_pf_greeble_scatter_hda.py` (VEX in `devScripts/vex/pf_plating_*.vfl`, `pf_greeble_*.vfl`) -> `polyfactory/otls/pf_plating_generator.hda`, `pf_greeble_scatter.hda`. (`pf_hull_panels.hda` is a COP texture tool; not related.)

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
- Rounded corners skip edges shorter than 1.5x the radius, rim bevel is capped at 0.45x plate thickness, NaN points that polybevel can still produce on pole-tight sphere facets are dropped (not shipped). Gaps: bevels are native polybevel, so very small plates with big bevel values just get none.
- Triangle layout is not a pixel-faithful port (cut-walk uses a diagonal across the next quad); rectangles use cell counts like Blender, not world sizes. Random streams differ from numpy, so seeds do not reproduce Blender layouts.
- Not ported: the add-on's seam/selected-edge workflow beyond the Edge Group parm, vertex-colour options other than random per plate/greeble, custom-library picking UI, the Animation Nodes variant, level-based UI (replaced by chaining).

### Not verified
No independent audit; no GUI look (TAB menu, help, panel layout never opened in a live Houdini); overlap measured with axis-aligned boxes (exact on grid/box, conservative on curved/rotated cases); layout beauty only by my eye on renders; performance on large meshes untested (halfedge loops are single-threaded detail wrangles).
