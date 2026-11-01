# pf_geoimporter — owner doc

`pf::geoimporter::1.0.0` imports every file a pattern matches, one piece per file: `pf_enum` (int, point) numbers the
files in sorted-path order (upper case first; the for-each's order), `filepath` (string, prim) names each file, and
**Pack Primitives** packs each file. Artist-facing help is in the asset (Help section). Checks:
`tests/hda/run_geoimporter_checks.py` (generated fixtures, File SOP oracle, mutations).

## glTF support (2026-11-01, Hannes: "behave the same as with the rest"; textures not wanted)

How it imports: inside `topgeometry1` (TOP net) `filepattern1` feeds two branches that `merge_imports` joins:
- `geo_only` -> `geometryimport`: the files PDG tags `file/geo` (abc, bgeo*, geo, fbx, obj, vdb).
- `gltf_only` (regex `.*\.(glb|gltf)$`) -> `geometryimport_gltf`: PDG tags glTF as plain `file`, which the original
  `geometryimport` (filetag `file/geo`) never took, so a `.glb` imported nothing.
At SOP level `unpack_gltf` (group `@filepath=*.glb @filepath=*.gltf`, transfer `*`) unpacks the packed prims a glTF
loads as, before `pf_enum` is set, so the output is polygons like any other format. glTF names come along (`name`,
`path`, `gltf_node_name`, `gltf_mesh_name`, `gltf_material_name`, `shop_materialpath`, `material_override`), as other
formats keep their own attributes; no materials or textures are imported.

## Decision log

- **`geo_only` filters on the PDG result tag** with the native HScript `strlen(pdgoutput(0, "file/geo", 0)) == 0`
  (round-2 audit found it; the first build used a Python expression on the false belief that no native filter could see
  a tag). Cost: one "Invalid tag" warning per stray file on that inner node, never on the asset. Without the filter any
  non-geometry file in the folder (a `.txt`, an image, a `.gltf`'s `.bin`, a `.glb`) failed the whole import with
  "Empty or missing file path". Rejected: `geometryimport` *On Empty Geometry = Ignore* — it also drops files that fail
  to READ, so a corrupt file vanished and every later `pf_enum` shifted (round-1 audit). Rejected: a regex of geometry
  extensions — it would repeat PDG's own list.
- **Upper-case `.GLB`/`.GLTF` are skipped** (case-sensitive regex): Houdini 22.0.442 segfaults reading them, even in a
  plain File SOP (`GLTF_Importer::doImportScene`). Revisit on a newer build.
- **Formats PDG does not tag as geometry** (`.ply`, `.stl`, `.off`, `.dxf`, USD = `file/usd`) are skipped; before, they
  failed the whole import. Not added: nobody asked, and each needs its own branch like glTF.
- **Broken files behave as before:** a corrupt `.bgeo.sc`, `.abc`, `.fbx` or `.glb` empties the whole import (errors on
  the TOP nodes inside the asset, none on the asset node); a corrupt or empty `.obj` and a `.gltf` missing its `.bin`
  read as empty geometry and drop out silently, shifting later `pf_enum` (a plain File SOP does the same). Pre-existing
  / Houdini behaviour; not changed.
- **The unpack runs per file inside the for-each** (against "batch over language"): it has to happen before `pf_enum`
  is set per file, and it costs little (25 real GLBs, 2.65 M polygons, 8.6 s).
