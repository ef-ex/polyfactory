# pf_sprite_sheet — play, extract and make sprite sheets in Copernicus

**Status:** built 2026-10-30, checked by `tests/hda/run_sprite_sheet_checks.py` (baseline + 20 mutations, all red;
`--only a,b` runs just those). Audit round 1 found 7 defects, all fixed (see the log at the bottom); round 2: see the resume pointer. **Owner of:** the `pf_sprite_sheet` COP HDA
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
  `pngtga_alpha_multiplication`) decides the alpha convention of the written PNG: its menu is *Unpremultiply if needed*
  (straight on disk; read back with Colour In File = Straight) and *Raw* (premultiplied on disk; read back with
  Premultiplied). **Use Raw for flipbook sheets.** Measured: a (0.2, 0.1, 0.05, 0.5) pixel written with Raw and read back as
  Premultiplied returns within 0.004 (8-bit), and the check `Make -> Image ROP (Raw) -> Extract` pins it. The ROP and the File
  that reads it must use the same colour space. The node has no premultiply toggle of its own.
* File COP needs an AOV entry (`aovs`=1, `aov1`=`C`) or it has no output when built from a script.
* Crop in *texture* units needs no resolution, so a cell is `(col/cols, (rows-1-row)/rows)`, size `(1/cols, 1/rows)`.
  Origin is bottom-left, so row 0 of the picture is the top row.
* Time Pack keeps its range as float32 and floors `(end-start)/step`: 1..2 step 0.1 gave 10 frames, not 11. `make_end` nudges
  the end by a thousandth of a step (a 1e-6 nudge vanished in float32); `make_count` uses the same formula, and a check compares
  it with the real cell count for 8 range/step cases.
* A Crop box outside the sheet wraps (File COP border), so a wrong cell index past the last row silently shows another cell:
  checks that must see an out-of-range index use Hold, not Loop (`frames_used_not_clamped`).
* Sheets whose size is not a multiple of the grid: Crop is pixel-snapped, 100x70 at 3x3 gives 34x24 cells (true 33.3x23.3), cell 0
  includes one pixel column of cell 1. Known, unchanged: use sheets that divide evenly (all the Artbeats atlases do).
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

## Equivalent mutants (cannot go red, on purpose)

* Ping-pong at negative time with `abs(t)`: ping-pong is symmetric in time.
* Hold with `u` not clamped at 0: a second guard (`a = max(0, ...)`) catches it; the two are belt and braces.

## Not done / next

* Round-trip through `rop_image` for the *Unpremultiply if needed* option (only Raw is pinned).
* Range End defaults to the playback end (`$FEND`, 240 in a fresh scene): Make with defaults builds 240 cells. The help says to set it.
* A *Save* convenience (ROP + `.atlas.json` sidecar) so a made sheet carries its grid.
* Grid guess from pixels (EffectCraft has it: `guess_grid` in `crates/engine/src/cmd/atlas.rs`; 164/164 right on real sheets).
* The fresh-node errors (no file / nothing wired) still name internal child nodes; a hint line appears under Sheet File when it is empty.

## Resume pointer

Branch `main`. Audit round 1 done (7 defects fixed, 12 survivors killed or shown equivalent). Next: audit round 2 on the fixed build, then push.
