"""Asset Placement Viewer State for pf_asset_place HDA.

Two modes (toggle with Q):
  surface_align -- LMB places on surface, aligns Y to face normal. Gizmo hidden.
                   S + drag: uniform scale. R + drag: rotate around local Y.
  gizmo         -- xform handle visible for precise manual placement.
"""

import hou
import time
import hdefereval
import viewerstate.utils as su  # noqa: F401 (needed for state registration)

# ── Constants ─────────────────────────────────────────────────────────────────

STATE_NAME = "polyfactory.asset_place"

MODE_SURFACE = "surface_align"
MODE_GIZMO   = "gizmo"

# Set to True by the drop handler immediately before calling setCurrentState.
# onEnter consumes it (one-shot) so only that single entry starts in surface-align.
_drop_triggered: bool = False

_HANDLE_NAME = "ap_xform"

_MSG_SURFACE       = "Move: preview | LMB: place | D: scale | F: rotate Y | Q: gizmo | ESC: exit"
_MSG_SURFACE_SCALE = "Hold D + drag left/right to scale | Release D to finish"
_MSG_SURFACE_ROT   = "Hold F + drag left/right to rotate around Y | Release F to finish"
_MSG_GIZMO         = "Drag handles to transform | Q: surface align mode | ESC: exit"

_SCALE_SENSITIVITY  = 0.005   # scale units per pixel
_ROTATE_SENSITIVITY = 0.5     # degrees per pixel


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normal_to_euler(normal: hou.Vector3) -> hou.Vector3:
    """Return XYZ Euler angles (degrees) that rotate +Y to align with normal.

    Builds a right-handed orthonormal frame (new_x, normal, new_z) and sets
    matrix rows directly — cleaner than axis-angle which produces a column-major
    matrix (for R*v convention) but Houdini uses row-major (v*M convention).
    In Houdini's row-major Matrix4: row i = where world axis i maps to.
    """
    y = normal.normalized()

    # Reference direction for building perpendicular axes; must not be parallel to y
    ref = hou.Vector3(0.0, 0.0, 1.0) if abs(y.dot(hou.Vector3(0.0, 0.0, 1.0))) < 0.9 \
        else hou.Vector3(1.0, 0.0, 0.0)

    # Right-handed frame: y is the normal axis
    x = y.cross(ref).normalized()   # "right" in the surface plane
    z = x.cross(y).normalized()     # "forward" in the surface plane

    # Each row i of the Houdini Matrix4 = where world axis i maps after rotation
    m = hou.Matrix4(1.0)
    m.setAt(0, 0, x.x()); m.setAt(0, 1, x.y()); m.setAt(0, 2, x.z())  # world X -> new_x
    m.setAt(1, 0, y.x()); m.setAt(1, 1, y.y()); m.setAt(1, 2, y.z())  # world Y -> normal
    m.setAt(2, 0, z.x()); m.setAt(2, 1, z.y()); m.setAt(2, 2, z.z())  # world Z -> new_z

    return m.extractRotates()


def _ground_plane_hit(origin: hou.Vector3, direction: hou.Vector3) -> hou.Vector3 | None:
    """Intersect ray with Y=0 ground plane. Returns hit position or None."""
    if abs(direction.y()) < 1e-8:
        return None
    t = -origin.y() / direction.y()
    if t <= 0.0:
        return None
    return origin + direction * t


# ── State class ───────────────────────────────────────────────────────────────

class AssetPlaceState:
    """Interactive placement state for the pf_asset_place HDA."""

    def __init__(self, state_name: str, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node: hou.SopNode | None = None
        self._mode: str = MODE_SURFACE
        # S / R drag state
        self._scale_active: bool = False
        self._rotate_active: bool = False
        self._drag_ref_x: int = 0
        self._drag_ref_scale: float = 1.0
        self._drag_ref_ry: float = 0.0
        # Track last mouse X and last key-event time for key-held detection
        self._last_mouse_x: int = 0
        self._last_s_time: float = 0.0
        self._last_r_time: float = 0.0
        # Physical key-held flags (set on DOWN, cleared on UP via onKeyTransitEvent)
        self._d_held: bool = False
        self._f_held: bool = False
        # Accumulated Y rotation offset from F+drag (survives raycasts)
        self._ry_offset: float = 0.0
        # Surface-normal-derived Y from the last raycast (used during F+drag)
        self._last_normal_ry: float = 0.0

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def onEnter(self, kwargs: dict) -> None:
        global _drop_triggered
        self.node = kwargs.get("node")
        if _drop_triggered:
            self._mode = MODE_SURFACE
            _drop_triggered = False
        else:
            self._mode = MODE_GIZMO
        self._ry_offset = 0.0
        self._last_normal_ry = 0.0
        self._d_held = False
        self._f_held = False
        if self.node:
            self.node.parm("place_mode").set(1 if self._mode == MODE_GIZMO else 0)
        self._apply_mode()

    def onExit(self, kwargs: dict) -> None:
        # Reset parm to gizmo so the next manual entry always starts in gizmo.
        if self.node:
            parm = self.node.parm("place_mode")
            if parm:
                parm.set(1)  # 1 = gizmo
        self.node = None
        self._scale_active = False
        self._rotate_active = False
        self._d_held = False
        self._f_held = False

    def onInterrupt(self, kwargs: dict) -> None:
        self._end_drag()

    def onResume(self, kwargs: dict) -> None:
        self._apply_mode()

    # ── Mouse ─────────────────────────────────────────────────────────────────

    def onMouseEvent(self, kwargs: dict) -> bool:
        # In gizmo mode return False so the handle system receives all events.
        if self._mode == MODE_GIZMO:
            return False

        ui_event = kwargs["ui_event"]
        device = ui_event.device()
        reason = ui_event.reason()
        current_x: int = int(device.mouseX())
        self._last_mouse_x = current_x

        # Timeout fallback: if no key event for >300ms AND key is not physically
        # held, assume it was released and the UP event was missed.
        now = time.time()
        if self._scale_active and not self._d_held and now - self._last_s_time > 0.3:
            self._end_drag()
        if self._rotate_active and not self._f_held and now - self._last_r_time > 0.3:
            self._end_drag()

        if self._scale_active:
            self._apply_scale_drag(current_x)
            return True
        if self._rotate_active:
            self._ry_offset = self._drag_ref_ry + (current_x - self._drag_ref_x) * _ROTATE_SENSITIVITY
            if self.node:
                r = self.node.parmTuple("r").eval()
                self.node.parmTuple("r").set((r[0], self._last_normal_ry + self._ry_offset, r[2]))
            return True

        if reason == hou.uiEventReason.Located:
            self._raycast_and_set(ui_event)
            return True

        if reason == hou.uiEventReason.Picked and device.isLeftButton():
            self._raycast_and_set(ui_event)
            viewer = self.scene_viewer
            hdefereval.executeDeferred(lambda: viewer.setCurrentState("select"))
            return True

        return False

    # ── Keyboard ──────────────────────────────────────────────────────────────

    def onKeyEvent(self, kwargs: dict) -> bool:
        device = kwargs["ui_event"].device()
        key = device.keyString().lower()

        if self._mode == MODE_SURFACE:
            # Always consume d/f to block any global hotkeys from firing.
            if key == "d":
                if not self._scale_active and not self._rotate_active:
                    self._begin_scale_drag(self._last_mouse_x)
                self._last_s_time = time.time()
                return True
            if key == "f":
                if not self._rotate_active and not self._scale_active:
                    self._begin_rotate_drag(self._last_mouse_x)
                self._last_r_time = time.time()
                return True

        if key == "q" and not self._scale_active and not self._rotate_active:
            self._toggle_mode()
            return True
        return False

    def onKeyTransitEvent(self, kwargs: dict) -> bool:
        """Key DOWN / UP transitions for clean drag start/end.
        Works as a supplement to onKeyEvent: onKeyEvent handles blocking global
        hotkeys and starting the drag; this handles the key-UP release."""
        if self._mode != MODE_SURFACE:
            return False
        device = kwargs["ui_event"].device()
        key = device.keyString().lower()
        if key == "d":
            if device.isKeyDown():
                self._d_held = True
                self._last_s_time = time.time()
                if not self._scale_active and not self._rotate_active:
                    self._begin_scale_drag(int(device.mouseX()))
            elif device.isKeyUp():
                self._d_held = False
                if self._scale_active:
                    self._end_drag()
            return True
        if key == "f":
            if device.isKeyDown():
                self._f_held = True
                self._last_r_time = time.time()
                if not self._rotate_active and not self._scale_active:
                    self._begin_rotate_drag(int(device.mouseX()))
            elif device.isKeyUp():
                self._f_held = False
                if self._rotate_active:
                    self._end_drag()
            return True
        return False

    # ── Private helpers ───────────────────────────────────────────────────────

    def _intersect_input(self, origin: hou.Vector3, direction: hou.Vector3):
        """Intersect against ONLY the geometry connected to SOP input 0.

        Input geometry is in OBJ-local space, so we transform the world-space
        ray into local space before testing, then transform results back.
        Returns (pos_world, normal_world) or (None, None).
        """
        if not self.node:
            return None, None

        inputs = self.node.inputs()
        if not inputs or inputs[0] is None:
            return None, None

        try:
            geo = self.node.inputGeometry(0)
            if not geo:
                return None, None

            # Input geometry lives in the OBJ parent's local space
            obj_node = self.node.parent()
            xform = obj_node.worldTransform()
            xform_inv = xform.inverted()

            o_local = origin * xform_inv
            d_local = ((origin + direction) * xform_inv - o_local).normalized()

            pos_local = hou.Vector3()
            normal_local = hou.Vector3()
            uvw_local = hou.Vector3()
            prim_num = geo.intersect(o_local, d_local, pos_local, normal_local, uvw_local)

            if prim_num < 0:
                return None, None

            # Position: transform back with translation (w=1)
            pos_world: hou.Vector3 = pos_local * xform
            # Normal: use only the 3x3 part (no translation) via inverse-transpose
            m3_inv = hou.Matrix3(xform_inv)
            normal_world: hou.Vector3 = (normal_local * m3_inv.transposed()).normalized()

            return pos_world, normal_world

        except Exception as e:
            print(f"[asset_place_state] input intersect error: {e}")
            return None, None

    def _raycast_and_set(self, ui_event) -> None:
        """Raycast against input geometry only, set t/r parms on node."""
        if not self.node:
            return

        origin, direction = ui_event.ray()

        hit_pos, hit_normal = self._intersect_input(origin, direction)

        # Fall back to ground plane if no input connected or ray missed
        if hit_pos is None:
            hit_pos = _ground_plane_hit(origin, direction)
            hit_normal = hou.Vector3(0.0, 1.0, 0.0)

        if hit_pos is None:
            return

        self.node.parmTuple("t").set((hit_pos.x(), hit_pos.y(), hit_pos.z()))
        if hit_normal:
            euler = _normal_to_euler(hit_normal)
            self._last_normal_ry = euler.y()
            self.node.parmTuple("r").set((euler.x(), euler.y() + self._ry_offset, euler.z()))

    # ── Handle sync (gizmo state only) ────────────────────────────────────────

    def onHandleToState(self, kwargs: dict) -> None:
        if kwargs.get("handle") != _HANDLE_NAME:
            return
        node = kwargs.get("node") or self.node
        if not node:
            return
        parms = kwargs.get("parms", {})
        node.parmTuple("t").set((parms.get("tx", 0.0), parms.get("ty", 0.0), parms.get("tz", 0.0)))
        node.parmTuple("r").set((parms.get("rx", 0.0), parms.get("ry", 0.0), parms.get("rz", 0.0)))
        node.parm("scale").set(parms.get("uniform_scale", 1.0))

    def onStateToHandle(self, kwargs: dict) -> None:
        if kwargs.get("handle") != _HANDLE_NAME:
            return
        node = kwargs.get("node") or self.node
        if not node:
            return
        parms = kwargs.get("parms", {})
        t = node.parmTuple("t").eval()
        r = node.parmTuple("r").eval()
        s = node.parm("scale").eval()
        parms["tx"] = t[0]; parms["ty"] = t[1]; parms["tz"] = t[2]
        parms["rx"] = r[0]; parms["ry"] = r[1]; parms["rz"] = r[2]
        parms["uniform_scale"] = s

    # ── Private helpers ───────────────────────────────────────────────────────

    # ── S / R drag helpers ────────────────────────────────────────────────────

    def _begin_scale_drag(self, mouse_x: int) -> None:
        if not self.node:
            return
        self._scale_active = True
        self._drag_ref_x = mouse_x
        self._drag_ref_scale = self.node.parm("scale").eval()
        self.scene_viewer.setPromptMessage(_MSG_SURFACE_SCALE)

    def _begin_rotate_drag(self, mouse_x: int) -> None:
        if not self.node:
            return
        self._rotate_active = True
        self._drag_ref_x = mouse_x
        self._drag_ref_ry = self._ry_offset
        self.scene_viewer.setPromptMessage(_MSG_SURFACE_ROT)

    def _apply_scale_drag(self, mouse_x: int) -> None:
        if not self.node:
            return
        delta = mouse_x - self._drag_ref_x
        new_scale = max(0.001, self._drag_ref_scale + delta * _SCALE_SENSITIVITY)
        self.node.parm("scale").set(new_scale)

    def _end_drag(self) -> None:
        self._scale_active = False
        self._rotate_active = False
        self.scene_viewer.setPromptMessage(_MSG_SURFACE)

    # ── Mode helpers ──────────────────────────────────────────────────────────

    def _toggle_mode(self) -> None:
        if not self.node:
            return
        self._scale_active = False
        self._rotate_active = False
        self._mode = MODE_GIZMO if self._mode == MODE_SURFACE else MODE_SURFACE
        self.node.parm("place_mode").set(1 if self._mode == MODE_GIZMO else 0)
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Show or hide the xform handle and update the prompt message."""
        is_gizmo = self._mode == MODE_GIZMO
        self.scene_viewer.showHandle(_HANDLE_NAME, is_gizmo)
        self.scene_viewer.setPromptMessage(_MSG_GIZMO if is_gizmo else _MSG_SURFACE)


# ── Template factory ──────────────────────────────────────────────────────────

def createViewerStateTemplate() -> hou.ViewerStateTemplate:
    template = hou.ViewerStateTemplate(STATE_NAME, "Asset Placement", hou.sopNodeTypeCategory())

    # Dynamic factory: reload module on every state entry so code changes
    # take effect without reinstalling the HDA.
    def _factory(state_name: str, scene_viewer) -> "AssetPlaceState":
        import importlib, sys
        mod_name = "polyfactory.asset_library.asset_place_state"
        old_mod = sys.modules.get(mod_name)
        saved_flag = getattr(old_mod, "_drop_triggered", False) if old_mod else False
        importlib.reload(sys.modules[mod_name])
        new_mod = sys.modules[mod_name]
        new_mod._drop_triggered = saved_flag
        return new_mod.AssetPlaceState(state_name, scene_viewer)

    template.bindFactory(_factory)
    template.bindIcon("SOP_file")
    # Bind the xform handle. In surface mode _apply_mode() hides it via
    # scene_viewer.showHandle(); in gizmo mode it is shown. Because we
    # hide it on enter, LMB Picked events still reach onMouseEvent.
    template.bindHandle("xform", _HANDLE_NAME)
    return template
