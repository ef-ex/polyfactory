---
name: houdini-tool-design
description: Principles for building procedural tools artists will actually USE — art direction first, predictable canonical I/O, helper-vs-end-user. The "why a tool gets used or abandoned" layer above the technical how.
when_to_use: BEFORE designing any artist-facing procedural tool or HDA — and whenever deciding what controls to expose. Read alongside houdini-procedural-modeling (the technical constitution).
tags: hda, tool-design, art-direction, procedural, ux, principles
---

# Skill: Designing procedural tools artists will use

The technical "how" lives in [[houdini-procedural-modeling]]. This is the "will it
actually get used" layer — and that is where most tools fail.

## 1. Art direction is the cardinal rule
A procedural tool that is **not art-directable will not be used** — full stop.
Control over *what the tool does* is the single most important property, and lack of
it is the #1 reason tools are abandoned. "Clever automation the artist can't steer"
is a dead tool, no matter how impressive the result. **Expose meaningful controls,
not a black box.** When in doubt, give the artist the knob.

## 2. Helper tools vs end-user tools (know which you're building)
- **Helper / utility tools** feed bigger tools, used internally. Can be opinionated,
  minimal UI, fewer controls.
- **End-user tools** are driven directly by artists — these **must** be
  art-directable, with clear, meaningful controls.
The art-direction bar is highest on end-user tools. Misjudging which you're building
leads to either an over-engineered helper or an unusable end-user tool.

## 3. Predictable, canonical I/O (so tools compose)
- **Normalize inputs** into the tool's space (e.g. Match Size) so *any* input works.
- **Emit outputs in a canonical space** — known origin, orientation, and bounds.
  Example: a curve that always starts at world origin and runs +X for `width`, with
  defined height. Then *anything* downstream knows exactly what it's getting.
- Predictability is what lets tools chain reliably in a procedural graph. Surprising
  bounds/orientation is how a tool quietly breaks every graph it's dropped into.

## 4. Control & predictability beat cleverness
Prefer **explicit, controlled construction** over configuring black-box nodes when
predictability matters — you know exactly what the geometry does, which kills the
class of bugs that surface later from a node behaving differently than assumed. A
point or two is no performance concern. (See [[houdini-procedural-modeling]].)

## 5. Expose both shape AND cost controls
Give artists the **shape** controls (ramps, handles, profiles) *and* the **technical**
knobs (resolution / point count), so they can balance look against downstream cost
themselves. The [[ramp-driven-curve]] tool is the model: a ramp for the shape, one
`segs` knob for the cost.

## The test
Before shipping: *can an artist who didn't build this get the result they want by
turning the controls — without reading the source?* If not, it's a helper at best.
