"""
Batch Kitbash Importer - AABB-based asset detection and batch export backend

Algorithm:
  1. Run connectivity SOP to label each disconnected island with a 'class' prim attribute.
  2. Compute per-island AABB from vertex positions (bulk fetch via pointFloatAttribValues).
  3. Incremental BFS cluster finding: process one island at a time, check candidates only
     against the current frontier, remove matched candidates from the unassigned pool so
     they are never checked again. O(n*k) typical instead of O(n^2).
  4. Read optional prim attributes 'file', 'category', 'tag' from the first prim of each group.
  5. Optional on_group_detected callback is called as each cluster is completed, enabling
     progressive UI updates.
"""

import hou
import os
from typing import Callable, Dict, List, Optional, Tuple


# ── Public API ────────────────────────────────────────────────────────────────

def detect_asset_groups(
    sop_node: hou.SopNode,
    on_group_detected: Optional[Callable[[Dict], None]] = None,
) -> List[Dict]:
    """Detect asset groups in a SOP node using connectivity + AABB overlap.

    Each disconnected island gets an AABB.  Islands whose AABBs overlap are
    merged into a single asset group via incremental BFS: each island is
    removed from the candidate pool the moment it joins a cluster, so later
    frontier checks never compare against it.

    Optional prim attributes read from the first prim of each group:
        'file'     - base filename (without number suffix)
        'category' - asset category
        'tag'      - comma-separated list of tags

    Args:
        sop_node:           SOP node containing the kitbash geometry.
        on_group_detected:  Optional callback(group_dict) called as each
                            cluster is completed.  Use this for streaming UI
                            updates; call QApplication.processEvents() inside
                            the callback to keep the UI responsive.

    Returns:
        List of group dicts, each with:
            prim_numbers  - sorted list of prim indices
            name          - base name from 'file' attrib, or ''
            category      - category from 'category' attrib, or ''
            tags          - list of tag strings from 'tag' attrib, or []
            prim_count    - total primitive count in the group
            island_count  - number of disconnected islands merged into the group
    """
    import re as _re

    parent = sop_node.parent()
    temp_nodes: List[hou.Node] = []

    try:
        # Run connectivity SOP to assign a unique 'class' prim attribute
        conn = parent.createNode('connectivity', '__batch_detect_tmp')
        conn.setInput(0, sop_node)
        conn.parm('connecttype').set(0)  # topology (shared verts/edges)
        temp_nodes.append(conn)
        conn.cook(force=True)
        geo: hou.Geometry = conn.geometry()

        # Bulk-fetch all point positions (single C++ call, avoids per-vertex Python overhead)
        all_pos: Tuple = geo.pointFloatAttribValues('P')  # flat (x0,y0,z0, x1,y1,z1, ...)

        # Bulk-fetch prim class values if the attribute exists
        class_attrib = geo.findPrimAttrib('class')
        all_classes: Optional[Tuple] = geo.primIntAttribValues('class') if class_attrib else None

        # Group prim numbers and point indices by connectivity class ───────────
        island_prims: Dict[int, List[int]] = {}
        island_pts: Dict[int, set] = {}
        for prim in geo.prims():
            pn: int = prim.number()
            cls: int = int(all_classes[pn]) if all_classes is not None else pn
            island_prims.setdefault(cls, []).append(pn)
            pt_set = island_pts.setdefault(cls, set())
            for vtx in prim.vertices():
                pt_set.add(vtx.point().number())

        # Compute per-island AABB from the pre-fetched position array ──────────
        island_bboxes: Dict[int, Tuple[float, float, float, float, float, float]] = {}
        for cls, pt_indices in island_pts.items():
            xs = [all_pos[i * 3]     for i in pt_indices]
            ys = [all_pos[i * 3 + 1] for i in pt_indices]
            zs = [all_pos[i * 3 + 2] for i in pt_indices]
            island_bboxes[cls] = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))

        # Incremental BFS clustering — remove islands from pool as they join a cluster.
        # Each island is tested against the current frontier only; once assigned it is
        # never compared again, giving O(n*k) behaviour for typical sparse scenes. ──
        unassigned: set = set(island_prims.keys())
        result: List[Dict] = []

        while unassigned:
            start: int = next(iter(unassigned))
            unassigned.discard(start)
            cluster: set = {start}
            frontier: set = {start}

            while frontier:
                new_frontier: set = set()
                matched: set = set()
                for candidate in unassigned:
                    bbox_c = island_bboxes[candidate]
                    for member in frontier:
                        if _aabbs_overlap(island_bboxes[member], bbox_c):
                            matched.add(candidate)
                            new_frontier.add(candidate)
                            break  # candidate already matched; skip other frontier members
                unassigned -= matched
                cluster |= matched
                frontier = new_frontier

            # Build group dict for this cluster ────────────────────────────────
            all_prim_nums: List[int] = []
            for cls in cluster:
                all_prim_nums.extend(island_prims[cls])
            all_prim_nums.sort()

            first_prim = geo.prim(all_prim_nums[0])
            name: str = _read_str_attrib(geo, first_prim, 'file', '')
            category: str = _read_str_attrib(geo, first_prim, 'category', '')
            tag_raw: str = _read_str_attrib(geo, first_prim, 'tag', '')
            tags: List[str] = (
                [t for t in _re.split(r'[\s,]+', tag_raw.strip()) if t]
                if tag_raw else []
            )

            group: Dict = {
                'prim_numbers': all_prim_nums,
                'name': name,
                'category': category,
                'tags': tags,
                'prim_count': len(all_prim_nums),
                'island_count': len(cluster),
            }
            result.append(group)

            if on_group_detected is not None:
                on_group_detected(group)

        return result

    finally:
        for node in temp_nodes:
            try:
                node.destroy()
            except Exception:
                pass


def next_free_filename(base_name: str, category: str, library_path: str, db_path: str) -> str:
    """Find the next available numbered filename (no extension).

    Scans both the filesystem and database for existing variants like
    base_name_00001.usd, base_name_00002.usd and returns the next free
    numbered name WITHOUT the .usd extension.

    Args:
        base_name:    Base name to use (will be sanitized).
        category:     Asset category (determines the filesystem subdirectory).
        library_path: Root asset library directory ($PF_ASSET_LIBRARY).
        db_path:      Path to asset database file.

    Returns:
        String like 'base_name_00003' ready to pass as export name.
    """
    safe_name = _sanitize(base_name)
    safe_category = _sanitize(category)
    prefix = safe_name + '_'
    existing: set = set()

    # Scan filesystem
    category_dir = os.path.join(library_path, safe_category)
    if os.path.isdir(category_dir):
        for fname in os.listdir(category_dir):
            if fname.startswith(prefix) and fname.endswith('.usd'):
                num_part = fname[len(prefix):-4]
                try:
                    existing.add(int(num_part))
                except ValueError:
                    pass

    # Scan database
    if os.path.exists(db_path):
        try:
            from polyfactory.asset_library.database import AssetDatabase
            with AssetDatabase(db_path) as db:
                for asset in db.search_assets():
                    fname = os.path.basename(asset.get('file_path', ''))
                    if fname.startswith(prefix) and fname.endswith('.usd'):
                        num_part = fname[len(prefix):-4]
                        try:
                            existing.add(int(num_part))
                        except ValueError:
                            pass
        except Exception as e:
            print(f"Warning: could not scan database for existing names: {e}")

    n = 1
    while n in existing:
        n += 1
    return f"{safe_name}_{n:05d}"


def export_batch_group(
    sop_node: hou.SopNode,
    prim_numbers: List[int],
    name: str,
    category: str,
    tags: List[str],
    prep_settings: Dict,
    debug: bool = False,
) -> bool:
    """Export a single asset group detected by detect_asset_groups.

    Converts prim indices back to hou.Prim objects and delegates to the
    existing export_asset pipeline with conflict check suppressed (the caller
    is responsible for providing a unique name via next_free_filename).

    Args:
        sop_node:      Source SOP node.
        prim_numbers:  Primitive indices for this group.
        name:          Final asset name (already numbered, no extension).
        category:      Asset category.
        tags:          List of tag strings.
        prep_settings: Dict matching export_asset keys:
                         use_prepare_mesh, scale_to, up, y_z,
                         align_x, align_y, align_z, remove_attribs.
        debug:         Enable verbose output.

    Returns:
        True on success.
    """
    from polyfactory.asset_library.exporter import export_asset

    geo = sop_node.geometry()
    selected_prims = [geo.prim(n) for n in prim_numbers]

    export_data = {
        'name': name,
        'category': category,
        'tags': tags,
        'notes': '',
        'selection_node': sop_node,
        'selected_prims': selected_prims,
        'use_prepare_mesh': prep_settings.get('use_prepare_mesh', True),
        'scale_to': prep_settings.get('scale_to', 1),
        'up': prep_settings.get('up', 1),
        'y_z': prep_settings.get('y_z', False),
        'align_x': prep_settings.get('align_x', 2),
        'align_y': prep_settings.get('align_y', 2),
        'align_z': prep_settings.get('align_z', 2),
        'remove_attribs': prep_settings.get('remove_attribs', True),
        '_skip_conflict_check': True,
    }

    return export_asset(export_data, debug=debug)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _aabbs_overlap(
    a: Tuple[float, float, float, float, float, float],
    b: Tuple[float, float, float, float, float, float],
) -> bool:
    """Return True if two AABBs (min_x,min_y,min_z,max_x,max_y,max_z) overlap."""
    return (
        a[0] <= b[3] and a[3] >= b[0] and
        a[1] <= b[4] and a[4] >= b[1] and
        a[2] <= b[5] and a[5] >= b[2]
    )


def _read_str_attrib(geo: hou.Geometry, prim: hou.Prim, name: str, default: str) -> str:
    """Read a string primitive attribute value; return default if absent."""
    if geo.findPrimAttrib(name):
        try:
            return str(prim.attribValue(name))
        except Exception:
            # Attribute exists but the value could not be read (e.g. type mismatch);
            # return the caller-supplied default rather than propagating.
            pass
    return default


def _sanitize(name: str) -> str:
    """Sanitize a name for use as a filesystem component."""
    safe = ''.join(c for c in name if c.isalnum() or c in (' ', '_', '-'))
    return safe.replace(' ', '_').strip('_')
