# Asset Library & Kitbash Workflow Redesign

**Date:** February 5, 2026  
**Status:** Planning / Not Implemented

---

## Goals
- Simplify the current complex kitbash HDA
- Create a more integrated, Blender-like asset browser experience
- Streamline asset placement workflow with single-asset HDA approach

---

## Asset Browser Redesign

### Pane Integration
- **Convert to Houdini Pane** (not standalone Qt window)
  - Make dockable within Houdini's UI system
  - Follow standard Houdini pane behavior
  - Should be launchable via shelf tool or menu

### Export Workflow
- **Keep existing shelf button** for quick export
  - Export selected geometry to library
  - Eventually convert shelf button to keyboard shortcut
- **Add "Export" button to Asset Browser UI**
  - Same functionality as shelf button
  - More discoverable for new users
  - Integrated workflow (browse → export → see result immediately)

### Browser Structure (Blender-Style Layout)

**Main Layout Components:**

```
┌─────────────────────────────────────────────────────┐
│ Top Bar: Search | Library Selector | View Options   │
├──────────────┬──────────────────────────────────────┤
│              │                                       │
│  Catalog     │  Asset Grid (Thumbnails)             │
│  Tree        │  [Tag filtering already exists]      │
│  (NEW)       │  [Grid size adjustment exists]       │
│              │                                       │
│  📁 Library1 │  ┌────┐ ┌────┐ ┌────┐               │
│    📁 Props  │  │img │ │img │ │img │               │
│    📁 Chars  │  └────┘ └────┘ └────┘               │
│  📁 Library2 │  ┌────┐ ┌────┐ ┌────┐               │
│    📁 Env    │  │img │ │img │ │img │               │
│              │  └────┘ └────┘ └────┘               │
│              │                                       │
├──────────────┴──────────────────────────────────────┤
│ Bottom Panel: Asset Metadata (already exists)       │
│ Name, Description, Tags, Author, Turntable Button   │
└─────────────────────────────────────────────────────┘
```

**NEW: Catalog Tree (Left Sidebar)**
- Hierarchical folder organization
- Nested categories
- Collapsible tree structure
- Click to filter assets by catalog
- Can organize assets into multiple nested levels

**NEW: Multiple Libraries Support**
- Switch between different asset libraries
- User library, project libraries, shared libraries
- Dropdown or tree-based library selector
- Each library can have its own catalog structure

**Existing Features to Preserve:**
- Tag filtering system (keep current implementation)
- Metadata panel (name, description, tags, author)
- Grid size adjustment (keep current slider/controls)
- Turntable rendering feature
- Export button (add to browser UI)

**Skip for Now:**
- List view mode (grid view only)

---

## Asset Placement Workflow

### Drag & Drop
- **Drag from Asset Browser → Viewport**
  - Should create HDA instance in scene
  - HDA placed following Houdini node hierarchy rules
  - Automatic context detection (SOP/OBJ level)

### Custom HDA Design
- **Single Asset HDA** (simplified approach)
  - Each HDA instance loads ONE asset only
  - Contrast with current multi-asset kitbash HDA complexity
  - Cleaner parameter interface
  - Easier to maintain and understand

### Python State Integration
- **Activated with HDA**
  - State launches when HDA is created/selected
  - Provides viewport positioning tools
  - Simplified implementation (only handles single asset)
  - Interactive placement, rotation, scale
  - Preview before committing

---

## Technical Benefits

### Simplified Architecture
- **Current:** Complex kitbash HDA manages multiple assets
- **New:** Single-asset HDA = simpler logic
  - Easier parameter management
  - Clearer HDA code
  - Better performance per instance
  - More intuitive for users

### Python State Advantages
- Only needs to track one asset at a time
- Simpler event handling
- Easier viewport interaction
- Better UX with focused tools

---

## Implementation Notes

### HDA Placement Rules
- Follow Houdini's automatic node creation rules
- Detect appropriate network context (OBJ, SOP, etc.)
- Create in correct location based on current selection
- Respect Houdini conventions for node insertion

### Asset Browser as Pane
- Implement as Python Panel (`.pypanel`)
- Register with Houdini's pane system
- Save/restore state with hip file layout
- Support multiple instances (can open multiple browsers)

---

## Open Questions
- Catalog tree: Allow drag & drop to reorganize catalogs?
- Catalog tree: Right-click menu for create/rename/delete catalogs?
- Multiple libraries: How to configure library paths? (Project setting vs user pref?)
- Should catalogs sync to database or be folder-based?
- Default library structure/catalogs?

---

## Related Files
- Current kitbash implementation:
  - `polyfactory/otls/pf_kitbash.hda`
  - `polyfactory/scripts/python/polyfactory/asset_library/kitbash_placement_state.py`
  - `polyfactory/scripts/python/polyfactory/asset_library/kitbash_ui.py`
- Asset library core:
  - `polyfactory/scripts/python/polyfactory/asset_library/`
  - Asset database: `$PF_ASSET_DB`

---

## Next Steps
1. Define exact Blender asset browser features to implement
2. Design new HDA parameter interface (single asset)
3. Design Python Panel layout for dockable browser
4. Plan Python state functionality (positioning tools)
5. Prototype drag & drop workflow
