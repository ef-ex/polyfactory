# Best Practices for a DCC MCP — Making an LLM Actually Operate Houdini

**Date:** 2026-06-24
**Status:** Research synthesis / design reference
**Scope:** How to design the polyfactory Houdini MCP so an LLM agent has full freedom **and** — more importantly — actually understands how to operate Houdini and generate useful content (not just flail against a raw API).

This distills how three mature DCC/engine integrations solve the problem:

- **Unreal Engine** — community MCPs (`chongdashu/unreal-mcp`, `flopperam`, `runreal`, `kvick-games`, `remiphilippe/mcp-unreal`) + **Epic's official UE 5.8 embedded MCP**.
- **Blender** — `ahujasid/blender-mcp` (community "creative copilot") and **Blender Lab's `blender_mcp`** (official, docs-grounded).
- **Godot** — the live `godot-mcp` server connected to this workspace (studied via its own `get_guide` resources).

Companion doc: [`ideas/native_houdini_ai_agent.md`](../ideas/native_houdini_ai_agent.md) (the alternative *native in-Houdini panel* architecture). This doc is about the **MCP/bridge** path, which is what we are already building (`polyfactory/scripts/python/polyfactory/houdini_bridge/`).

---

## TL;DR — the 9 things that make a DCC-MCP work

1. **In-DCC server + external bridge**, with all DCC API calls **marshaled to the main thread**. (We already do this.)
2. **Structured tools for the common 80% + a `run_python` escape hatch for the long tail.** Don't wrap a 1000-node API as 1000 flat tools.
3. **A doc-lookup / reflection tool is the single highest-value anti-hallucination lever.** Let the agent check *real* signatures before writing code.
4. **Pair every mutating tool with an `inspect`/read tool** so the model grounds itself before and verifies after.
5. **A visual feedback loop** — render a flipbook/viewport to PNG and feed it back. This is the primary self-correction mechanism.
6. **Return rich, structured errors, not empty results.** The model only self-corrects from signal.
7. **Encode engine grounding at connection time** (coordinate system, units, the SOP/OBJ/LOP context model) — but **enforce the dangerous bits in code, not prose** (prompt rules fall out of context).
8. **Ship goal-oriented "recipe" guides as MCP resources** ("I want to do X → use these tools in this order").
9. **Your HDAs *are* the skill library.** The MCP's job is to make them discoverable and drivable — not to reimplement modeling/texturing logic in Python. (Proven below with the Copernicus guide.)

---

## 1. Architecture & transport

### The proven shape (all three ecosystems converge here)

```
LLM client  ⇄ stdio/HTTP ⇄  MCP server (FastMCP, outside the DCC)  ⇄ socket ⇄  in-DCC listener  ⇄  native API
```

- **Inside the DCC:** a socket server on a worker thread that **marshals real work onto the main thread**. Blender uses `bpy.app.timers.register`; Unreal's `chongdashu` plugin uses `AsyncTask(ENamedThreads::GameThread, …) + TPromise`. **Houdini's HOM is not thread-safe either** — our bridge already runs the work this way; keep that invariant.
- **Outside the DCC:** a thin **FastMCP** server that speaks MCP to the client (Claude Code/Cursor/etc.) and forwards to the in-DCC socket. This is exactly the **shim** we scoped — wrap our existing WebSocket+msgpack server (`houdini_bridge/server.py`, port 9876) as MCP tools.

### Transport lessons

| Pattern | Who | Takeaway for us |
|---|---|---|
| Raw TCP + JSON, *parse-to-detect* framing | `chongdashu` (Unreal) | **Fragile for large payloads.** We already do better: msgpack with explicit framing (`message_handler.py`). Keep it. |
| Null-byte-framed JSON | Blender Lab | Simple, robust. Validate our msgpack framing handles big `read_network` payloads. |
| **Editor-embedded HTTP + SSE server** | **Epic UE 5.8 (official)**, Godot-style | **The future direction.** No separate process; the MCP server lives *inside* the DCC. Houdini ships an embedded Python interpreter and HTTP capability — a v2 option is to host the MCP/HTTP server *inside* Houdini and drop the external bridge entirely. |
| Native Python remote execution, **no custom plugin** | `runreal` (Unreal) | "By far the easiest to install." Our `execute_python` command is the Houdini equivalent — lean on it. |

**Recommendation:** ship the **external FastMCP shim now** (fastest path to a working agent loop against the bridge we have). Keep **embedded HTTP/SSE** (Epic's model) as the v2 target once the tool surface stabilizes.

---

## 2. Tool surface — structured tools **and** a code hatch

The single clearest finding across every project: **do both, deliberately.**

- **`chongdashu` (Unreal):** ~25 purely-structured tools, **zero** arbitrary Python — proves structured-only is viable for a *curated* scope.
- **`flopperam` (Unreal):** 50+ structured tools on a consistent **`*_inspect` / `*_edit`** convention across 9 domains **plus** a gated `python_execution` hatch.
- **`ahujasid` (Blender):** a handful of introspection + asset tools, with `execute_blender_code` as the catch-all for all geometry/material creation.
- **Blender Lab:** the *elegant extreme* — the **only** privileged primitive inside Blender is "run this Python," and every "structured" tool is a **curated, version-controlled server-side script** shipped into Blender as a string. `get_objects_summary` = "send this canned introspection script, return its `result` dict."
- **Godot:** richly structured, with **tiered granularity** for the same operation (see below).

### Two design axes worth copying

**(a) Tiered granularity — give the model the right-sized tool.** Godot exposes the same conceptual action at several scopes and *tells the model when to use which* (from its `scene-editing` guide):

| Goal | Godot tool |
|---|---|
| Build a whole subtree in one shot | `create_scene` with a `nodes` tree |
| Add one node | `add_node` |
| Change one value | `modify_node_property` |
| Change many values on one node | `set_node_properties` |
| Replace a whole resource | `set_mesh` / `set_material` / … |

Houdini analogue: `write_network` (whole subgraph — **we already have this via the Recipe API**) / `create_node` (one) / `set_parameter` (one parm) / a `set_parameters` (many parms) / `run_python` (long tail).

**(b) Typed, discriminated value formats — don't make the model guess JSON shapes.** Godot accepts discriminated unions for Variant values: `{type:"Vector3", x,y,z}`, `{type:"Color", r,g,b,a}`, `{type:"Transform3D", …}`. For Houdini, parms are mostly float/int/string/toggle/ramp/menu — expose **typed parm setters** (and a ramp/keyframe-aware variant) rather than a stringly-typed blob.

### Don't fight the API surface with tool sprawl

Houdini has thousands of node types and parameters. Wrapping them as flat tools is hopeless. The winning combination is **a few generic node-graph tools (`create_node`, `set_parameter`, `cook`/`read_network`/`write_network`) + introspection + a `run_python` hatch.** Houdini's node-graph nature means a small generic toolset covers enormous surface area — this is a structural advantage over Unreal/Blender.

---

## 3. The core problem: making the LLM **understand** the DCC

This is the part that separates competent integrations from flailing ones. Ranked by how load-bearing each mechanism is:

### 3.1 Reflection / API doc-lookup before acting — **the highest-value lever**

The model's #1 failure mode is **inventing API calls from stale training data.** Every serious project attacks this directly:

- **Unreal `remiphilippe`:** `lookup_class` (structured class reference) + `lookup_docs` (NL search over UE API docs), with a hard rule: *"Look up docs before writing UE code."*
- **Unreal `flopperam`:** a `unreal_api` tool backing **15,000+ API lookups**.
- **Unreal `runreal`:** a meta-tool `list_actions` that returns available actions **with params and docs at runtime** — the agent learns parameter shapes dynamically.
- **Blender Lab:** ships the **entire Blender Python API (RST) + user manual** with the server. `get_python_api_docs(identifier)` resolves real signatures with glob discovery (`bpy.*`), "did you mean" typo suggestions, runnable examples, and a 32 KB response cap tuned to the MCP transport ceiling. `search_api_docs` / `search_manual_docs` do full-text search.
- **Godot:** `classdb_query` exposes the engine ClassDB; `get_node_properties` returns class-level property metadata.

**For Houdini:** give the agent a `lookup_node_type` / `lookup_hom` tool over the **HOM reference and node/parm documentation** (and ideally VEX function signatures). This is the single most important thing to build after the basic loop. Houdini's `hou.nodeType(...).parmTemplates()` and the node-type help give us a *live, version-correct* source — far better than the model's memory.

### 3.2 Live scene/state introspection — ground the model in reality

Every project ships read tools so the model reasons about the *actual* scene, not an assumed one: `get_actors_in_level`/`get_actor_properties` (Unreal), `get_scene_info`/`get_object_info` (Blender ahujasid), `get_objects_summary`/`get_object_detail_summary` (Blender Lab), `get_scene_hierarchy`/`get_node_properties` (Godot).

**We already have the strong version of this:** `read_network` (the Recipe API) returns a full node graph as structured data, and `get_node_info` returns parms. Lean on it — have the agent `read_network` before editing and again after, to verify.

### 3.3 Visual feedback loop — the primary self-correction mechanism

- **Blender ahujasid:** `get_viewport_screenshot` returns a real image; its system prompt says *"Always take a screenshot after completing a task to verify the visual result"* — reportedly the biggest reason it produces usable scenes.
- **Godot:** `take_screenshot` is a first-class part of the documented testing loop.
- **Unreal:** `take_screenshot` / `window_capture`.

**This is the gap in our bridge.** We have no "see the result" command. Add a **`render_view` tool** that writes a viewport flipbook or an OpenGL/Karma ROP render to a temp PNG, which the agent reads back. Cheap to build via `execute_python` (`hou.SceneViewer.flipbook` or an `opengl`/`karma` ROP). Without this, the agent is modeling blind.

### 3.4 Error feedback & self-correction

- **`kvick` (Unreal)** is the purest case: *"Claude makes a lot of errors with Unreal Python… but let it run and it will usually figure things out."* Command → execute → return logs/result → next action.
- **`remiphilippe`** has the most robust loop: structured JSON from `build_project`/`run_tests`/`get_output_log` enables edit→build→test→read-error→fix.
- **Documented anti-pattern (`chongdashu`):** introspection returns **empty lists/dicts on failure** instead of error detail — the model has nothing to self-correct from.

**For us:** our `execute_python` already captures stdout + returns tracebacks (`commands.py`). Keep returning **full tracebacks and structured errors**, never silent empties.

### 3.5 Connection-time engine grounding — but enforce danger in code

- **Unreal `chongdashu`** encodes grounding as Cursor `.mdc` rules: pins **coordinate system and units** (Z-up, left-handed, X=forward, SI units) — directly targeting the classic axes/handedness/units failure mode. Tool params must avoid `Any`/`Optional`/`Union` to keep JSON schemas clean.
- **Blender Lab's `prompts.yml`** is a dense *correctness* briefing sent at connection: *"NEVER assume missing values — inspect first"*; mode matters (object/edit/sculpt fail silently in the wrong mode); active-object vs selection are distinct; **update the dependency graph before reading computed properties**; return structured dicts not print output; *"Don't dump entire scenes — inspect progressively."*
- **Critical lesson:** Blender Lab enforces catastrophic-op blocking in a **runtime denylist** (`weak_sandbox.py`), *not* a prompt rule — explicitly because **"prompt instructions fall out of the context window and get ignored."*

**For Houdini, the connection-time briefing should pin:**
- Coordinate system (**Y-up**, right-handed) and units.
- The **context model**: OBJ vs **SOP** vs **LOP/Solaris (USD)** vs DOP vs ROP — and that node creation must target the right context.
- The procedural paradigm: you build a **network that cooks**, you don't imperatively mutate geometry; edits are parms/nodes, not vertex pokes.
- Parm-eval vs raw value, `node.cook()` before reading geometry stats, `with hou.undos.group(...)` around agent edits.
- Enforce the genuinely destructive bits (e.g. `hou.hipFile.clear()`, deleting `/obj`) in **code guards**, not just the prompt.

### 3.6 Recipe guides as MCP resources

**Godot's `get_guide`** ships goal-oriented markdown as MCP resources: `testing-loop`, `scene-editing`, `asset-generation`, `troubleshooting`, **`tool-index`** ("I want to do X → which tool"). The model pulls the right workflow on demand instead of guessing tool ordering.

**Copy this directly.** Ship `houdini-mcp://guide/...` resources: `kitbash-placement`, `procedural-asset`, `lighting-setup`, `solaris-usd-basics`, `render-feedback-loop`, `tool-index`. We already have rich source material in `documentation/kitbash_*` to seed these.

### 3.7 Capability gating & tool annotations (cheap safety wins)

- **ahujasid:** `*_status` tools (`get_polyhaven_status`, `get_hyper3d_status`) let the model check availability before use.
- **Blender Lab:** MCP `ToolAnnotations` — `readOnlyHint=True` on introspection/docs, `destructiveHint=True` on code execution — so clients can gate.
- **Godot:** destructive ops require explicit confirmation (`delete_file` needs `confirm:true`).

Annotate our read tools `readOnly` and gate destructive ones (`delete_node`, `load_scene`, `save_scene`) behind a confirm flag or the existing `approval.py` manager.

---

## 4. The skills layer — tools vs recipes vs HDAs (proven by the Copernicus guide)

A recurring confusion: "shouldn't the MCP contain *skills*?" Yes — but skills are **not one thing**, and most of them should **not** live inside the MCP server as code. Separate three layers:

| Layer | What it is | Where it lives | Houdini example |
|---|---|---|---|
| **Tools** | Generic verbs | The **MCP** | `create_node`, `set_parameter`, `run_python`, `render_view`, `lookup_node_type` |
| **Recipes / guides** | How to *sequence* tools + the hard-won gotchas for a task | **MCP resources** (Godot `get_guide` pattern) | "build an OpenCL COP HDA" |
| **Skills proper** | Encoded domain expertise / repeatable procedures | **HDAs** (in Houdini) + **agent `SKILL.md`** (harness side) | `pf_kitbash`, `pf_gyroid_noise`, MaterialX setups |

**The key insight for Houdini:** a "skill" is most naturally an **HDA** — procedural expertise baked into a parametric asset. polyfactory is *already* a skill library (`pf_kitbash`, `pf_hull_panels`, `pf_mesh_to_quad`, the `pf_*_noise` family, MaterialX wiring). The MCP should not re-implement these; it should let the LLM **discover them and drive their parms** — the exact same move as driving an Unreal SunSky actor by lat/long (§5): *language → typed parameters, the asset does the work.* This aligns with [[no-throwaway-data-driven-code]].

### Worked proof: `documentation/copernicus_opencl_hda_guide.md`

[`copernicus_opencl_hda_guide.md`](copernicus_opencl_hda_guide.md) is the canonical example of the **recipe layer** done right, and the best evidence the model works. It was distilled over several rounds of driving the bridge with Sonnet 4.6, and it banks the exact non-obvious traps no model knows from training data:

- the Copernicus **output-type index off-by-one** (OpenCL signature index vs subnet `outputtypeN` differ by 1);
- **`defn.setParmTemplateGroup()` NOT `hda_node.setParmTemplateGroup()`** (the instance version silently fails to persist);
- **re-wire after `createDigitalAsset()`** (it inserts a passthrough);
- **`for slot in range(20): try/except`** (COP nodes have no `nInputs()`);
- GLSL→OpenCL gotchas (`fract` needs a pointer arg, `abs`→`fabs` for floats).

This is the Blender Lab `prompts.yml` lesson made concrete for Houdini: **a hard-won list of exactly how naive LLM code breaks.** A complete "skill" here is **guide + devScript template + existing `create_pf_*.py` exemplars + the resulting HDAs** — and *none of it lives as code inside the MCP server.*

**One-shot validation (2026-06-24):** as a test of whether the recipe holds without back-and-forth, a brand-new `pf_worley_noise` (cellular/Voronoi F1) HDA was authored from *only* the guide + template + one exemplar (`create_pf_gyroid_noise_hda.py`), with a fresh kernel. Built headless via `hython`, it passed **build → structural verify (all parms + `ch()` bindings correct) → cook (OpenCL compiled clean, zero errors)** on the **first attempt, no deviations.** That is the test of a working skill layer — and it passed. The artifacts were then **deleted**: Houdini ships Worley natively, so keeping a custom one would itself violate §7's "don't reimplement what the DCC provides." The test validated the *recipe*, not a needed asset.

**Takeaway:** the MCP's skill responsibilities reduce to two tools — **discovery** ("what HDAs/recipes exist and what are their parameters?") and **driving** (instantiate + parameterize + run the build/verify/render loop). Serve guides like the Copernicus one as `get_guide` resources; keep the procedures in HDAs and exemplars.

---

## 5. The "natural-language → real-world-accurate setup" capability

The motivating example was *"set up the lighting like Vienna at 5pm"* and the engine matching real-world sun position.

**Honest accuracy note:** I could **not** verify that exact demo wording. The verified UE 5.8 keynote demo (Unreal Fest, June 17 2026) showed Claude Code over MCP furnishing an apartment → city, with *"lighting and time of day adjusted using simple text commands and even a static photograph as reference."* So the real demo is closer to **reference-photo lighting + time-of-day text commands**. Treat any "pulls data from a geolocation/solar API" claim as **unsupported** — no such API was found cited.

**How it actually works (verified mechanism):** Unreal's **Sun Position Calculator plugin** + **SunSky actor** (bundles Directional Light + Sky Light + SkyAtmosphere). Its inputs are **latitude, longitude, time zone, north offset, month/day, and solar time** (e.g. `17.0` = 5 PM); the engine computes solar azimuth/elevation and rotates the directional light.

**The LLM bridge (the transferable insight):** the model does **not** hand-compute the sun vector. It supplies **lat/long/timezone/date/time from its own world knowledge** ("Vienna" → ~48.2°N, 16.4°E, CET; "5 PM" → 17.0) and sets the **typed SunSky parameters**, letting the DCC's built-in solar math do the rest.

**This is a general pattern, and Houdini has the equivalent:** a **Physical Sun/Sky / Environment Light** with a **sun-direction-from-coordinates** setup (and HDA wiring). The recipe for us:

1. Author a `lighting_setup` recipe guide + a thin HDA/parameter interface (sun direction, time, sky).
2. The agent maps language → numbers from world knowledge ("golden hour in Vienna in June" → date/time/lat-long).
3. The agent sets **typed parms**; Houdini's sun model computes the angle.

The lesson generalizes far past lighting: **the LLM's job is language → typed parameters; the DCC's built-in solvers do the domain math.** Don't ask the model to compute what a node already computes — expose the node and let the model drive its inputs. (This aligns with our [[no-throwaway-data-driven-code]] principle: tunables live in data/parms, not hardcoded.)

---

## 6. Concrete recommendations for the polyfactory Houdini bridge

In priority order. Items marked ✅ already exist in `houdini_bridge/`.

1. ✅ **In-DCC server + main-thread execution** — keep the invariant.
2. ✅ **Recipe API (`read_network` / `write_network`)** — strong structured graph I/O; this is ahead of most community MCPs. Use it as the backbone for "inspect before/after."
3. **Build the external FastMCP shim** wrapping the existing port-9876 protocol (the v1 unblock). Map each command (`execute_python`, `create_node`, `set_parameter`, `read_network`, `write_network`, `get_node_info`) to an MCP tool.
4. **Add `render_view`** (flipbook / OpenGL / Karma ROP → temp PNG) for the visual feedback loop — the biggest current gap.
5. **Add `lookup_node_type` / `lookup_hom`** over HOM + node/parm docs — the biggest anti-hallucination win.
6. **Add typed parm setters** (`set_parameters` many-at-once; ramp/keyframe-aware) instead of stringly-typed values.
7. **Ship `get_guide` resources** seeded from `documentation/kitbash_*` + [`copernicus_opencl_hda_guide.md`](copernicus_opencl_hda_guide.md) (the first proven recipe) + new lighting/Solaris/render guides, including a `tool-index`. Pair each recipe with its devScript template + exemplars so the agent can one-shot the task (validated 2026-06-24 — see §4).
8. **Connection-time grounding briefing** (Y-up, context model, procedural paradigm, cook-before-read) — and **code-level guards** on destructive ops via `approval.py`.
9. **Tool annotations** (`readOnlyHint` / `destructiveHint`) + `*_status`-style capability checks.
10. **Async generate→poll→import triad** for slow ops (sims, bakes, Karma renders, and any external 3D-gen like Tripo/Meshy/Rodin) — copy ahujasid's Rodin/Hunyuan job pattern.
11. **v2:** evaluate the **embedded HTTP/SSE server** (Epic UE 5.8 model) to drop the external bridge.

---

## 7. Anti-patterns to avoid

- ❌ Wrapping the whole API as hundreds of flat tools. Use generic node tools + reflection + a `run_python` hatch.
- ❌ Returning empty results on failure (`chongdashu`'s documented mistake). Always return tracebacks/structured errors.
- ❌ Relying on prompt rules for safety. Enforce destructive-op guards in code (Blender Lab's explicit finding).
- ❌ Fragile parse-to-detect framing for large payloads. Keep explicit msgpack framing; validate big `read_network` responses.
- ❌ Modeling blind. Without `render_view`, the agent can't verify and will confidently produce garbage.
- ❌ Asking the model to compute what a node computes (sun angles, noise, solvers). Expose the node; drive its inputs.

---

## Sources

**Unreal:** `github.com/chongdashu/unreal-mcp` (incl. `UnrealMCPBridge.cpp`, `.cursor/rules/*.mdc`), `github.com/flopperam/unreal-engine-mcp`, `github.com/runreal/unreal-mcp`, `github.com/kvick-games/UnrealMCP`, `github.com/remiphilippe/mcp-unreal`, `dev.epicgames.com` (Unreal MCP plugin; Sun and Sky / Sun Position Calculator), State of Unreal 2026 keynote coverage.
**Blender:** `github.com/ahujasid/blender-mcp` (+ `server.py`, `addon.py`), `projects.blender.org/lab/blender_mcp` (read first-hand: `prompts.yml`, `tools/*.py`, `weak_sandbox.py`, `tools_helpers/connection.py`), `blender.org/lab/mcp-server`.
**Godot:** the live `godot-mcp` server in this workspace — guides `scene-editing`, `testing-loop`, `tool-index`, `asset-generation`, `troubleshooting`.

**Verification caveats:** the exact "Vienna at 5pm" demo wording and any solar/geolocation API are **unverified** — the verified demo is reference-photo + time-of-day text commands driving the SunSky actor. Unreal community tool lists are from repo docs/source; Blender Lab details are first-hand from a repo clone; Godot details are first-hand from the live server.
