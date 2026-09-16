# Edge Damage — a 1:1 port of Quentin King's Paintable Stylized Edge Damage

**Status:** ported 2026-09-16 on branch `pf-edge-damage`. Parity checks
(`tests/hda/run_edge_damage_checks.py`) hold the shipped asset to a dump of the reference
asset — nodes, wires, parameters, viewer-state module — and are green with every mutation seen
red. Brush behaviour has only Hannes' viewport as its oracle.
**This file owns:** `pf_edge_damage` — what it is, the three naming deviations, and the record
of the failed first attempt. It does not own rock formation ([`rocks.md`](rocks.md)).
**Origin:** Hannes liked the tool while studying *8-bitBot*'s chipped low-poly props and asked
for it in polyfactory. It ships as an Indie `.hiplc` a Commercial session cannot load, so it
was read node-for-node off the Indie session over its bridge (port 9877) and rebuilt from that
dump. **Reference:** `Quentin::paint_edge_damage::1.0`, quentinking.com/houdini/edgedamage/,
free download. Credit is Quentin's; the port is his design verbatim.

---

## 1. The law of this file: it is a replica

Hannes, 2026-09-16: *"please do not invent or change things from provided material when I ask
you to port it over. I expect a 1 to 1 replica."*

The build script embeds the reference dump as `SPEC` and builds from it; nothing is authored by
hand. Deviations — exactly four: three naming, one three-line guard that only runs where the
reference would crash:

| what | reference | polyfactory | why |
|---|---|---|---|
| asset / TAB | `Quentin::paint_edge_damage`, *Digital Assets* | `pf_edge_damage`, *PF Edge Damage* under *Poly Factory/Modeling* | polyfactory's TAB law |
| chip group | `chipped` | `pf_chipped` | conventions.md §1 |
| icon | embedded `paint.pic` section | `SOP_attribpaint` (same picture) | nothing to embed |
| mask visualizer | assumed to exist in the scene | created with SideFX's mask defaults if missing (3 lines, marked `pf port`) | Quentin's `.hiplc` carries the visualizer; a fresh scene does not, and `onEnter` crashed on `None.setIsActive` — the reference has the same latent bug |

Anything else that differs from the reference is a defect; `run_edge_damage_checks.py` will
say so.

## 2. How it works (Quentin's design, restated so nobody "improves" it again)

`matchsize` into the unit cube → brick `divide` (the paint canvas) → `attribpaint` writes
`mask` → `attribblur` on **P** (pulls edges and corners in) → `remesh` → `attribnoise` along N
→ `peak` (the *Damage Bias*) → **`@P += @N * (1.0 - @mask) * 0.1`** → VDB → polygons →
`polyreduce` | `remesh` (*Damage Meshing Method*) → hard normals → `boolean` **intersect** with
the original → `matchsize` restores the transform.

That one wrangle is the whole mask semantics: mask 0 pushes the cutter 0.1 *out* (untouched
surface), mask 1 leaves the worn edges to cut, mask **past 1 pushes the cutter INTO the face**
(painting deeper carves), negative erases. The paint state is `sidefx_stroke.StrokeState`
subclassed: Ctrl+wheel changes strength, MMB the radius, a HUD shows both, hotkeys 1–4 switch
the viz (paintable / output / mask / boolean), strokes are baked into the paint node's Data
parms after each one. `attribpaint`'s paint mode is the default *paint* (over): a stroke drags
the mask toward the current strength, so repainting a deep dent with a lower strength lifts it
— that is the reference's behaviour, keep it.

## 3. The failed first attempt, kept as the warning it is

The first port (commits `0693df3`…`a08a7e3`, superseded) "improved" the reference: it replaced
the `(1 - mask) * 0.1` wrangle with a clamped rest-position push (so a mask past 1 could never
carve into a face), dropped the HUD/menu state for a bare template (which then crashed with
`KeyError: 'realtime_mode'`), re-derived *Blurring Iterations* as a distance, added mask
sources, an input contract, a polygon floor — two audits and ~1 400 lines of checks around a
tool that could not do what the original does. Every one of those changes was a regression
against the thing that was asked for. Ported material is replicated, then — separately, if
ever — proposed for change.

## 4. Checks, and what they cannot see

Four parity checks, each with a mutation seen red: every node/wire/non-default parm equals
the dump (mutation: rewire the boolean); every parameter template equals the dump (mutation:
move a default in the oracle — proves the field is read); the viewer-state module is the
reference's byte for byte, the state is the default state, the Python flags are set, the stroke
instance links are the reference's (mutation: edit the oracle module); no strokes returns the
input's volume (mutation: bypass the mask-bias wrangle).

Blind spots: a stroke landing under the cursor, the HUD and hotkeys, and anything the reference
itself gets wrong — the reference is the oracle. The old suite's audit findings (open meshes
cook to nothing, thin parts erode below the damage resolution) describe the reference too; they
are its behaviour, recorded here, not fixed in the port.
