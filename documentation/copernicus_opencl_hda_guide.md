# Copernicus OpenCL HDA Development Guide

How to create, build, and test procedural noise / texture generator HDAs for Houdini's Copernicus (COP) context using OpenCL kernels.

## Overview

Each HDA is a Copernicus COP node wrapping an OpenCL kernel. The HDA is built entirely from a Python devScript run via hython — no interactive Houdini session required for creation.

**Existing HDAs built with this pattern:**

| HDA | devScript | Description |
|-----|-----------|-------------|
| `pf_gyroid_noise` | `create_pf_gyroid_noise_hda.py` | Gyroid noise with feedback FBM |
| `pf_scape_noise` | `create_pf_scape_noise_hda.py` | 6 de Carpentier algorithms (FBM, Billowy, Ridged, IQ, Swiss, Jordan) |
| `pf_caustic_trig` | `create_pf_caustic_trig_hda.py` | Trig-feedback caustics (joltz0r) |
| `pf_caustic_fbm` | `create_pf_caustic_fbm_hda.py` | Ridged FBM + dual domain warp caustics |
| `pf_fractal_noise` | `create_pf_fractal_noise_hda.py` | AE Fractal Noise (parked — visual mismatch) |

## Architecture

```
Copernicus copnet
  └── HDA node (pf_my_node)
        └── opencl node (kernel)
              ├── kernel code (OpenCL C)
              ├── output bindings (#bind layer)
              └── constant bindings (#bind parm) → ch("../hda_parm") expressions
```

The HDA is a subnet with a single OpenCL node inside. HDA parameters are linked to OpenCL constant bindings via `ch("../parm_name")` channel references.

## OpenCL Kernel Structure

```c
// GLSL compatibility — OpenCL fract() requires pointer arg
#define pf_fract(x) ((x) - floor(x))

// Output layer binding — ! = write, & = reference
#bind layer !&my_output

// Parameter bindings — these become kernel constants
#bind parm frequency   float val=1.0
#bind parm octaves     int   val=6
#bind parm gain        float val=0.5

// Noise functions go here as inline functions
inline float my_noise(float2 p) {
    // ... implementation
    return value;
}

// Main entry point
@KERNEL
{
    // Get normalized UV coordinates
    float u = (float)@ix / (float)@xres;
    float v = (float)@iy / (float)@yres;

    // Compute noise
    float result = my_noise((float2)(u, v) * @frequency);

    // Write to output
    @my_output.set(result);
}
```

### Critical OpenCL vs GLSL Differences

| GLSL | OpenCL | Fix |
|------|--------|-----|
| `fract(x)` | `fract(x, &iptr)` (2-arg) | `#define pf_fract(x) ((x) - floor(x))` |
| `vec2(x, y)` | `(float2)(x, y)` | Cast syntax |
| `mix(a, b, t)` | `mix(a, b, t)` | Works in OpenCL (built-in) |
| `smoothstep(e0, e1, x)` | `smoothstep(e0, e1, x)` | Works in OpenCL |
| `abs(x)` for float | `fabs(x)` | Use `fabs` for float in OpenCL |

### Binding Types

**Output layers:**
- `#bind layer !&name` — write-only output (the `!` means write, `&` means by reference)

**Constant parameters:**
- `#bind parm name float val=default` — float constant
- `#bind parm name int val=default` — integer constant

**Copernicus output type indices:**

| Type | OpenCL Signature index | Subnet `outputtypeN` index |
|------|------------------------|---------------------------|
| ID | 1 | 0 |
| Mono (float) | 2 | 1 |
| UV (float2) | 3 | 2 |
| RGB (float3) | 4 | 3 |
| RGBA (float4) | 5 | 4 |

Track both indices separately — they differ by 1.

## devScript Structure

Every HDA has a corresponding `devScripts/create_pf_<name>_hda.py`. This is the source of truth — the `.hda` file is a build artifact.

### Template

```python
"""
create_pf_<name>_hda.py — Build pf_<name>.hda for Houdini Copernicus.
"""
import hou, os

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_<name>.hda").replace("\\", "/")

if os.path.exists(OUTPUT_HDA):
    os.remove(OUTPUT_HDA)

# 1. Define outputs: (wire_name, opencl_type_idx, subnet_type_idx)
OUTPUTS = [("noise", 2, 1)]  # Mono
N_OUTPUTS = len(OUTPUTS)

# 2. Define constant bindings: (kernel_name, hda_parm, type: 0=int 1=float, default)
CONST_BINDINGS = [
    ("frequency", "frequency", 1, 1.0),
    ("octaves",   "octaves",   0, 6),
]

# 3. Write kernel as raw string
KERNEL = r"""#define pf_fract(x) ((x) - floor(x))
#bind layer !&noise
#bind parm frequency float val=1.0
#bind parm octaves   int   val=6

@KERNEL
{
    float u = (float)@ix / (float)@xres;
    float v = (float)@iy / (float)@yres;
    // ... compute ...
    @noise.set(result);
}
"""

# 4. Configure opencl node (set kernel, outputs, bindings)
def _configure_opencl(ocl):
    ocl.parm("kernelcode").set(KERNEL)
    ocl.parm("outputs").set(N_OUTPUTS)
    for i, (wname, ocl_type, _) in enumerate(OUTPUTS, start=1):
        ocl.parm(f"output{i}_name").set(wname)
        ocl.parm(f"output{i}_type").set(ocl_type)
    ocl.parm("inputs").set(0)
    ocl.parm("bindings").set(len(CONST_BINDINGS))
    for i, (kname, _, btype, default) in enumerate(CONST_BINDINGS, start=1):
        ocl.parm(f"bindings{i}_name").set(kname)
        ocl.parm(f"bindings{i}_type").set(btype)
        vparm = f"bindings{i}_intval" if btype == 0 else f"bindings{i}_fval"
        ocl.parm(vparm).set(int(default) if btype == 0 else float(default))

# 5. Wire ch() expressions from opencl bindings → HDA parms
def _wire_channel_refs(ocl):
    for i, (_, hparm, btype, _) in enumerate(CONST_BINDINGS, start=1):
        vparm = f"bindings{i}_{'intval' if btype == 0 else 'fval'}"
        ocl.parm(vparm).setExpression(
            f'ch("../{hparm}")', language=hou.exprLanguage.Hscript)

# 6. Build HDA parameter template group
def _build_ptg():
    ptg = hou.ParmTemplateGroup()
    ptg.append(hou.FloatParmTemplate(
        "frequency", "Frequency", 1,
        default_value=(1.0,), min=0.1, max=10.0,
        min_is_strict=False, max_is_strict=False))
    ptg.append(hou.IntParmTemplate(
        "octaves", "Octaves", 1,
        default_value=(6,), min=1, max=12,
        min_is_strict=True, max_is_strict=False))
    return ptg

# 7. Main build function
def create():
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)

    img = hou.node("/img") or hou.node("/").createNode("img", "img")
    copnet = img.createNode("copnet", "_build_ctx")
    subnet = copnet.createNode("subnet", "_build")

    # Create and configure opencl node
    ocl = subnet.createNode("opencl", "pf_<name>_kernel")
    _configure_opencl(ocl)
    _wire_channel_refs(ocl)

    # Find or create output node, wire it
    existing_out = None
    for n in subnet.children():
        if n.type().name() in ("output", "output0") and n is not ocl:
            existing_out = n
            break
    if existing_out is None:
        existing_out = subnet.createNode("output", "OUT")

    # Set subnet output count and types
    try:
        subnet.parm("outputs").set(N_OUTPUTS)
        for i, (wname, _, stype) in enumerate(OUTPUTS, start=1):
            lp = subnet.parm(f"outputlabel{i}")
            if lp: lp.set(wname)
            tp = subnet.parm(f"outputtype{i}")
            if tp: tp.set(stype)
    except Exception as e:
        print(f"[WARN] subnet output multiparm: {e}")

    for idx in range(N_OUTPUTS):
        existing_out.setInput(idx, ocl, idx)
    existing_out.setDisplayFlag(True)
    subnet.layoutChildren()

    # Wrap as HDA
    hda_node = subnet.createDigitalAsset(
        name="pf_<name>",
        hda_file_name=OUTPUT_HDA,
        description="PF <Name>",
        min_num_inputs=0, max_num_inputs=0,
        version="1",
    )

    # CRITICAL: re-wire after createDigitalAsset (it inserts a passthrough)
    hda_node.allowEditingOfContents()
    inner = {n.name(): n for n in hda_node.children()}
    inner_ocl = inner.get("pf_<name>_kernel")
    inner_out = None
    for n in hda_node.children():
        if n.type().name() in ("output", "output0", "outputs") and n is not inner_ocl:
            inner_out = n
            break

    if inner_ocl and inner_out:
        for slot in range(20):
            try: inner_out.setInput(slot, None)
            except: break
        for idx in range(N_OUTPUTS):
            inner_out.setInput(idx, inner_ocl, idx)

    # CRITICAL: set parms on DEFINITION, not node instance
    defn = hda_node.type().definition()
    defn.setParmTemplateGroup(_build_ptg())

    # Save
    defn.save(OUTPUT_HDA, template_node=hda_node)

    # Cleanup
    hda_node.destroy()
    copnet.destroy()
    return OUTPUT_HDA

if __name__ == "__main__":
    create()
```

### Critical Rules

1. **`defn.setParmTemplateGroup()` NOT `hda_node.setParmTemplateGroup()`**
   - Node instance version only adds spare parms — they don't persist into the HDA file.
   - Always get the definition: `defn = hda_node.type().definition()`

2. **Re-wire after `createDigitalAsset()`**
   - `createDigitalAsset()` resets internal connections (inserts a passthrough).
   - Call `allowEditingOfContents()`, then re-wire `opencl → output`.

3. **Clear all output node inputs before re-wiring**
   - COP nodes don't have `nInputs()`. Use a `for slot in range(20): try/except` loop.

4. **`#bind` declarations must match `CONST_BINDINGS` exactly**
   - The kernel `#bind parm name type val=default` must match what you set in `_configure_opencl()`.

## Building

```powershell
$env:POLYFACTORY = "F:/projects/polyfactory/polyfactory"
& "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" `
    "F:/projects/polyfactory/devScripts/create_pf_<name>_hda.py"
```

Expected output:
```
[INFO] subnet outputs set to 1
[OK] inner wiring restored.
[OK] parm template set on definition.
[OK] Saved: F:/projects/polyfactory/polyfactory/otls/pf_<name>.hda
[OK] Build context cleaned up.
```

## Testing / Verification

### Automated verification via hython

```powershell
& "C:\Program Files\Side Effects Software\Houdini 21.0.631\bin\hython.exe" -c @"
import hou
hou.hipFile.clear(suppress_save_prompt=True)
hou.hda.installFile(r'F:/projects/polyfactory/polyfactory/otls/pf_<name>.hda')
img = hou.node('/img') or hou.node('/').createNode('img', 'img')
copnet = img.createNode('copnet', '_test')
node = copnet.createNode('pf_<name>', '_verify')

# Print all parameters
print('=== Parms ===')
for p in node.parms():
    pt = p.parmTemplate()
    if pt.type() in (hou.parmTemplateType.Folder, hou.parmTemplateType.FolderSet,
                     hou.parmTemplateType.Separator):
        continue
    print(f'  {p.name():20s} = {p.eval()}')

# Print bindings and verify ch() expressions
node.allowEditingOfContents()
for c in node.children():
    if c.type().name() == 'opencl':
        nb = c.parm('bindings').eval()
        print(f'\n=== Bindings ({nb}) ===')
        for i in range(1, nb+1):
            nm = c.parm(f'bindings{i}_name').eval()
            bt = c.parm(f'bindings{i}_type').eval()
            vpn = f'bindings{i}_intval' if bt == 0 else f'bindings{i}_fval'
            try:
                expr = c.parm(vpn).expression()
                val = c.parm(vpn).eval()
                print(f'  {nm:20s}: {expr} -> {val}')
            except:
                print(f'  {nm:20s}: val={c.parm(vpn).eval()} (NO EXPR)')
        kc = c.parm('kernelcode').eval()
        print(f'\n=== Kernel: {len(kc.splitlines())} lines ===')

copnet.destroy()
"@
```

**What to verify:**
1. All HDA parms exist with correct defaults
2. Every binding has a `ch("../parm")` expression (no "NO EXPR" lines)
3. Expression values resolve to the HDA parm defaults
4. Kernel line count is reasonable

### Visual testing in interactive Houdini

1. Open Houdini
2. Go to `/img/` context, create a `copnet`
3. Inside copnet, Tab → search for `pf_<name>`
4. Connect output to a `null` or viewer
5. Check the COP viewer for visual output
6. Tweak parameters to confirm they affect the output

## Porting Shadertoy Code

1. **Read the Shadertoy** — understand the algorithm, identify which parts are the core noise vs. coloring/compositing
2. **Map GLSL → OpenCL** — fix `fract()`, `vec2()→(float2)()`, `abs()→fabs()` for floats
3. **Extract parameters** — anything that's a `#define` or magic number becomes a `#bind parm`
4. **Normalize UV** — Shadertoy uses `fragCoord/iResolution`; OpenCL uses `@ix/@xres`
5. **Prefix all functions** — use `pf_` prefix to avoid name collisions with OpenCL builtins
6. **Test with defaults matching the Shadertoy** — so the first visual output matches the reference
