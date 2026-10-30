# pf_sprite_sheet — play, extract and make sprite sheets in Copernicus

**Status:** built 2026-10-30, checked by `tests/hda/run_sprite_sheet_checks.py` (baseline + 8 mutations, all red).
Independent audit: see the resume pointer at the bottom. **Owner of:** the `pf_sprite_sheet` COP HDA
(`polyfactory/otls/pf_sprite_sheet.hda`, built by `devScripts/create_pf_sprite_sheet_hda.py`).

## What it is

One Copernicus node, three jobs, picked with *Mode*:

| Mode | Does | Pixels moved by |
|---|---|---|
| Play | a sheet (file, or a layer wired in) plays on the timeline: Start Frame, Sheet Speed (cells/s), Loop / Ping-Pong / Hold, optional blend of neighbouring cells | File → Crop ×2 → Blend |
| Extract Frame | one cell as its own layer, the size of one cell | File → Crop |
| Make Sprite Sheet | the wired-in layer sampled at every frame of a range, packed into one sheet (columns auto or set, optional cell resize) | Time Pack → Contact Sheet (Resample) |

Grid input is Columns / Rows / Frames Used (0 = all cells); *Read Grid from Sheet JSON* fills them (and the
speed) from `<sheet>.atlas.json` or the sheet's entry in a `manifest.json` in the same folder — the format the
Artbeats flipbook atlases and EffectCraft's sprite sheets use (`{file, cols, rows, frames, duration_s}`).

## Facts measured on Houdini 22.0.442 (not assumed)

* Copernicus RGBA layers are **premultiplied**. The File COP's *Pre-Multiply if Necessary* multiplies straight
  formats (PNG, TGA) by alpha on load, so a file that is already premultiplied (flipbook textures shot on black)
  needs it OFF. The HDA's *Colour In File* menu maps to that (Premultiplied → off, Straight → on).
  Make therefore emits a normal premultiplied layer; the **Image ROP** (`rop_image`, parm
  `pngtga_alpha_multiplication`) decides the alpha convention of the written PNG. The node has no premultiply toggle of its own.
* File COP needs an AOV entry (`aovs`=1, `aov1`=`C`) or it has no output when built from a script.
* Crop in *texture* units needs no resolution, so a cell is `(col/cols, (rows-1-row)/rows)`, size `(1/cols, 1/rows)`.
  Origin is bottom-left, so row 0 of the picture is the top row.
* Time Pack (new in 22) → Contact Sheet (`stride` = columns, `limitlines` off) lays frames out top-left first, reading order.
* Constant COP signatures are `f1…f4` (`f4` = RGBA), not names.
* File COP default colour management is OCIO (sRGB → scene linear); we keep it, so values round-trip through
  an Image ROP; the checks read the file as Raw to compare exact numbers and one check pins the default decode.

## Decision log — every Python use, named

1. **`PythonModule` (`hou.phm()` on the HDA):** `index()` / `cell()` / `mix()` / `make_count()` / `make_cols()` —
   turn (sheet frames elapsed, loop mode, grid) into a cell index and Crop box. Parameter marshalling: no native node
   computes "ping-pong index of a float time". `_t` (a hidden Hscript parm, `$FF` based) carries the time so Houdini
   knows the node is time dependent. Cost: a few arithmetic ops per cook.
2. **`read_grid` button callback:** reads a JSON file and sets parms. File IO; nothing native reads a sidecar.
3. **`makeinfo`:** a read-only label ("6 frames in 3 columns x 2 rows") from `make_info`.
Everything touching pixels is native. No VEX, no OpenCL.

## What the checks cannot see

The viewer's colour management; the Image ROP and the written PNG (the Make → ROP → file → Extract round trip is
**not** tested yet — Make → Extract through the layer is); the Read Grid button and the GUI parameter layout;
sheets whose size is not a multiple of the grid (Crop rounds); cook speed on large sheets; Play at fractional
Start Frame with Blend off beyond the cases listed in the file.

## Not done / next

* Round-trip test through `rop_image` with each `pngtga_alpha_multiplication` option, and a documented recommended setting.
* A *Save* convenience (ROP + `.atlas.json` sidecar) so a made sheet carries its grid.
* Grid guess from pixels (EffectCraft has it: `guess_grid` in `crates/engine/src/cmd/atlas.rs`; 164/164 right on real sheets).
* Preview in the node's own UI is the COP viewer itself (the sheet is visible in Play mode when Sheet From is Input and Mode is Extract).

## Resume pointer

Branch `main`. Next: independent audit round (dev-loop Rule 0), then the items above.
