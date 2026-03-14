# Known Pitfalls Log

Tracks mistakes made during development -- wrong APIs, bad workflow choices,
incorrect assumptions, anything that required correction. When a recurring issue
gets a permanent fix in `copilot-instructions.md`, the entry is marked RESOLVED
with a reference to the rule.

---

## How to Use This File

- **New mistake** -- add an entry at the top of the relevant category.
- **Recurring mistake** (same root cause, 2+ times) -- add a rule to
  `copilot-instructions.md` and mark entries RESOLVED.
- **Never delete entries.** Resolved entries explain *why* a rule exists.

---

## Categories

- [Houdini / HDA Python API](#houdini--hda-python-api)
- [Copernicus COP](#copernicus-cop)
- [Workflow](#workflow)

---

## Houdini / HDA Python API

### RESOLVED -- HDA attribwrangle group parm not limiting affected prims
- **Date:** 2026-03-13
- **What happened:** Created `pf_asset_tag` HDA with an attribwrangle whose
  `group` parm was linked to the HDA's `basegroup` parm. Attributes were being
  written to ALL prims regardless of the group. User had to fix this manually.
- **Root cause:** Post-wrap expression `chs("../basegroup")` was set on the
  wrangles but the wrangle `group` parm may require a different relative path
  depending on depth, or the expression was not saved correctly with the
  `template_node`. Did not verify by testing the actual attribute write behavior
  before handing off.- **Fix:** User corrected the expression manually after testing with real geometry.- **Mitigation:** After building any HDA that limits operation via a group parm,
  always cook a test node in hython (with real geometry) and verify that prims
  outside the group are not affected before declaring done.

### OPEN -- menuType.Normal with item generator renders as full combobox, not text+arrow
- **Date:** 2026-03-13
- **What happened:** Set `menu_type=hou.menuType.Normal` on a StringParmTemplate
  with an item generator script, expecting a text field with a small arrow
  chooser. It rendered as a full non-editable combobox. User could not type a
  new category.
- **Root cause:** `Normal` with a generator locks the parm to menu values.
  The correct types for a free-text field with a chooser arrow are:
  - `menuType.StringReplace` — arrow replaces field content with selected item
  - `menuType.StringToggle` — arrow toggles (appends/removes) space-separated tokens
- **Fix:** Use `menuType.StringReplace` for single-value pick fields (category),
  `menuType.StringToggle` for multi-token fields (tags).


- **Date:** 2026-02-25
- **What happened:** Called `node.nInputs()` on a Copernicus COP node to clear
  passthrough connections -- AttributeError at runtime.
- **Root cause:** `nInputs()` does not exist on COP nodes (it exists on SOP/LOP
  nodes).
- **Fix:** Use `node.setInput(slot, None)` iterated over slots (break on
  exception) to clear all connections.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

### RESOLVED -- Wrong multiparm names for Copernicus subnet output labels/types
- **Date:** 2026-02-25
- **What happened:** Tried to set output labels/types via
  `subnet.parm("output1_label")` and `subnet.parm("output1_type")` -- both
  returned None. All outputs kept default names (dst, output2, ...) and all
  defaulted to RGBA.
- **Root cause:** Copernicus subnet uses `outputlabel1` / `outputtype1`
  (no underscore separator), not `output1_label` / `output1_type`.
- **Fix:** Use `subnet.parm("outputlabel" + str(i))` and
  `subnet.parm("outputtype" + str(i))`.
- **Diagnostic pattern:**
  ```python
  [p.name() for p in subnet.parms() if p.name().startswith("output")]
  ```
  Run this after setting `subnet.parm("outputs").set(N)` to see actual names.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

### RESOLVED -- Type index mismatch: opencl Signature tab vs subnet outputtype menu
- **Date:** 2026-02-25
- **What happened:** Used opencl Signature tab type indices (Mono=2, RGB=4,
  RGBA=5) for the subnet `outputtype` multiparm -- all output types were wrong.
- **Root cause:** The two menus have completely different orderings:
  - opencl Signature `outputN_type`: 0=Varying, 1=ID, 2=Mono, 3=UV,
    4=RGB, 5=RGBA
  - Copernicus subnet `outputtypeN`: 0=ID, 1=Mono, 2=UV, 3=RGB,
    4=RGBA, 5=Geometry, ...
- **Fix:** Track both indices separately -- use a 3-tuple:
  `(wire_name, opencl_type_idx, subnet_type_idx)`.
  Apply `opencl_type_idx` to the opencl node Signature parms, and
  `subnet_type_idx` to the subnet `outputtypeN` parms.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

---

## Copernicus COP

### RESOLVED -- Used COP2 context (`copnet`) instead of Copernicus (`cop`)
- **Date:** 2026-02-25
- **What happened:** Build script placed the HDA inside `img.createNode("copnet"
  ...)` and expected a single "layer stream" output wire (COP2 model). The HDA
  did not expose separate named output wires.
- **Root cause:** Assumed Copernicus was COP2. They are architecturally different:
  - COP2 (`copnet`): one output wire = a stream of named layers.
  - Copernicus (`cop`): each output is a separate independent wire/cable.
- **Fix:** Build the subnet inside a `copnet` container (that part is still
  correct for the hython build context), but the subnet node type belongs to the
  `cop` category. Declare how many wires exist via `subnet.parm("outputs").set(N)`.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

### RESOLVED -- `createDigitalAsset()` inserts a passthrough that disconnects inner nodes
- **Date:** 2026-02-25
- **What happened:** After wrapping a subnet with `createDigitalAsset()`, Houdini
  auto-created `inputs(input)` and `outputs(output)` routing nodes wired as a
  passthrough. The actual opencl node was left disconnected -- HDA produced no
  output.
- **Root cause:** `createDigitalAsset()` always inserts its own routing wiring
  and ignores pre-existing inner connections.
- **Fix:**
  1. Call `hda_node.allowEditingOfContents()` after wrapping.
  2. Break the auto-passthrough: `inner_outputs.setInput(slot, None)` in a loop.
  3. Wire opencl outputs -> inner output node inputs.
  4. Capture the corrected state: `definition.save(path, template_node=hda_node)`.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

### RESOLVED -- Copernicus Output COP: one node, i-th input = i-th output wire
- **Date:** 2026-02-25
- **What happened:** Attempted to create one Output COP node per named output
  (5 nodes for 5 outputs). Only ONE Output COP is allowed per subnet -- extras
  are ignored or cause errors.
- **Root cause:** Assumed "one output node per output wire". The actual rule is:
  the single Output COP's i-th INPUT becomes the subnet's i-th output WIRE,
  so a 5-output node needs ONE output COP wired to 5 inputs:
  `opencl.output(N) -> output_cop.input(N)` for N in 0..4.
- **Rule added:** See *Copernicus COP Development* in `copilot-instructions.md`.

---

## Workflow

### OPEN -- Asking questions already answered in Galaxia documentation
- **Date:** 2026-02-25
- **What happened:** Asked the user to explain what `OUT_chassis_S_H1_D_SCI_T2`
  meant (module type, variant segments, class, pattern, tier) and what the
  connection point naming convention was. All of this is fully documented in
  `d:\godotGames\galaxia\documentation\module_set_spec.md` (written Feb 23, 2026).
- **Root cause:** Did not check the Galaxia documentation before asking. When
  working on Polyfactory tools that produce content for Galaxia, both codebases
  are in the workspace and both sets of docs are accessible.
- **Rule:** Before asking the user ANY question about Galaxia naming conventions,
  module structure, connection points, class/tier rules, grid specs, or ship
  designer constraints — **read the relevant Galaxia documentation file first**.
  Key files to check:
  - `d:\godotGames\galaxia\documentation\module_set_spec.md` — module naming,
    CP naming, grid sizes, class separation, T2 module set
  - `d:\godotGames\galaxia\documentation\phases\phase8_designer.md` — ship
    designer constraints
  - `d:\godotGames\galaxia\documentation\standard_materials_module_ecosystem.md`
    — material/reactor specs
  Only ask the user if the docs do not contain the answer.

### RESOLVED (2026-07-18) -- ViewerStateTemplate.bindNodeType does not exist in Houdini 22
- **Date:** 2026-07-18
- **What happened:** Used `template.bindNodeType(hou.sopNodeTypeCategory(), ...)` in
  `createViewerStateTemplate()` in `asset_place_state.py`. This call crashes Houdini
  at startup with `'ViewerStateTemplate' object has no attribute 'bindNodeType'`.
- **Root cause:** `bindNodeType` was never a valid method on `ViewerStateTemplate` in
  Houdini 22 (and likely any version). The method list has no such entry.
- **Fix:** Removed the `bindNodeType` call entirely. For externally-registered states
  (via `123.py`), the `onCreated` HDA callback handles auto-activation on node
  creation. Re-entry after ESC uses the viewport state menu (standard Houdini UX).
- **Secondary fix:** `except hou.NotAvailable` in `123.py` did not catch
  `AttributeError` raised when `hou.ui` is absent in hython (headless) mode. Changed
  guard to `except (hou.NotAvailable, AttributeError)` to suppress noisy prints.

### OPEN -- Proceeding on a vague creative/design prompt without breaking it down first
- **Date:** 2026-02-25
- **What happened:** User asked to "create a node which creates hull panels".
  Agent immediately designed and implemented a full OpenCL kernel, parameter
  layout, and HDA from scratch -- without agreeing on what the node should
  actually look like, what outputs it should produce, what artistic style was
  intended, or what the key controls should be. Result did not match what the
  user had in mind.
- **Root cause:** The prompt described a *tool category*, not a design. Words
  like "create", "generate", "make a node that does X" are goals, not specs.
  Jumping straight to implementation on a creative task is always wrong.
- **Rule:** When a request involves creative or procedural content (shaders,
  textures, generators, visual tools), **stop before any implementation** and
  ask the user to break the design down:
  1. What does the output look like? (reference images, adjectives, comparisons)
  2. What are the key artistic controls the user wants to tweak?
  3. What channels / outputs are needed, and what do they drive?
  4. Are there reference nodes, games, or materials that capture the look?
  Only start coding once all four questions have concrete answers.
