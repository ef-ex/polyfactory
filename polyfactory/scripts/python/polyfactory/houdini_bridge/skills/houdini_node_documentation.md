---
name: houdini-node-documentation
description: Document a custom HDA in Houdini's help format so the help server exposes it and agents can discover it
when_to_use: Whenever you CREATE or modify a custom HDA — always add or refresh its help in the same change, or the node is invisible to discovery
tags: documentation, hda, help, discoverability, wiki, markup
---

# Skill: Document a custom HDA (so it's discoverable)

Houdini's local help server (port 48626) auto-exposes the help embedded in any
HDA. So a **documented** HDA shows up at `/nodes/<context>/<name>` and is
findable via `houdini_node_help(...)` / the Help browser — and an **undocumented**
HDA is effectively invisible to future agents and humans. Always document what you
build. This closes the loop: create node -> document it -> it becomes discoverable.

## Where the help goes
- **Preferred: embed it in the HDA's "Help" section** — it travels inside the
  `.hda`. Set it programmatically in the build devScript:
  ```python
  defn = hda_node.type().definition()
  defn.addSection("Help", HELP_TEXT)     # HELP_TEXT is wiki markup (below)
  defn.save(OUTPUT_HDA, template_node=hda_node)
  # verify:
  assert defn.embeddedHelp().strip(), "help not embedded!"
  ```
- Alternative (file-based): `HOUDINI_PATH/help/nodes/<catdir>/<name>.txt`
  (catdir: obj, sop, dop, cop2, out). Embedding is simpler and self-contained.

## The format (Houdini wiki markup)
Page properties come before the first heading; `"""..."""` is the one-line summary
that shows in tooltips and search.

```
= My Node Title =

#type: node
#context: cop
#internal: pf_myname
#icon: COP2/null

"""One-line summary of what this node does."""

A paragraph describing the node in more detail.

@parameters
    Frequency:
        #id: frequency
        Spatial frequency of the pattern. Higher = finer detail.
    Octaves:
        #id: octaves
        Number of FBM octaves.

@inputs
    Input Name:
        What to plug in (omit the section if the node has no inputs).

@related
    - [Node:cop/opencl]
```

Markup basics: `= Title =`, `#prop: value`, `"""summary"""`, `== Heading ==`,
`*bold*`, `_italics_`, `` `code` ``, `*` bullets. Match `#context:` to the node's
real context (`cop` for Copernicus, `sop` for SOPs, ...). `#internal:` is the node
type name. Parameter `#id:` must match the actual parm name so help auto-links.

## Learn the format from real nodes (don't guess)
- Raw wiki source of ANY page: append `.txt` to the URL —
  `houdini_doc("nodes/sop/box.txt")` shows exactly how SideFX writes node help.
- Full markup reference: `houdini_doc("help/format")`.
- The asset-documentation guide: `houdini_doc("help/nodes")`.

## Done when
- `defn.embeddedHelp()` is non-empty after the build, AND
- `houdini_node_help("<context>", "<name>")` returns your summary + parameters
  (i.e. the help server is serving it live).

## Style
Active voice, second person, concise. Document every exposed parameter. A summary
sentence is mandatory — it is what shows in search results and tooltips.
