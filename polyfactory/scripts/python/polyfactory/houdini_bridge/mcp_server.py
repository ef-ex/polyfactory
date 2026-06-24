"""
Houdini Bridge MCP server (v1).

A FastMCP stdio server that exposes the in-Houdini bridge (server.py, port 9876)
as MCP tools, so a context-rich agent (Claude Code / Vela) can drive Houdini.

The agent — with all its project/Hub/Studio context — stays the brain; Houdini
is one tool it drives. This is the foundation; an in-DCC relay chat is a later
layer on top of the same connection.

Run (stdio):
    python -m polyfactory.houdini_bridge.mcp_server
or via the .mcp.json snippet in MCP_SETUP.md.

Env:
    HOUDINI_BRIDGE_HOST (default localhost)
    HOUDINI_BRIDGE_PORT (default 9876)

Deps: mcp, websockets, msgpack  (see requirements-mcp.txt)
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from .bridge_client import BridgeClient, BridgeError
from . import skills_registry as skills

_HOST = os.environ.get("HOUDINI_BRIDGE_HOST", "localhost")
_PORT = int(os.environ.get("HOUDINI_BRIDGE_PORT", "9876"))

mcp = FastMCP("houdini")
client = BridgeClient(host=_HOST, port=_PORT)


def _call(cmd: str, **params: Any) -> Dict[str, Any]:
    """Forward to the bridge, surfacing connection errors as a readable result
    rather than crashing the tool (so the agent can react)."""
    try:
        return client.command(cmd, **params)
    except BridgeError as e:
        return {"success": False, "error": str(e)}


# --------------------------------------------------------------------------- #
# Houdini control tools (thin wrappers over CommandExecutor commands)
# --------------------------------------------------------------------------- #

@mcp.tool()
def houdini_status() -> Dict[str, Any]:
    """Check whether the Houdini bridge is reachable. Call this first."""
    try:
        return {"connected": True, "response": client.ping()}
    except BridgeError as e:
        return {"connected": False, "error": str(e)}


@mcp.tool()
def houdini_execute_python(code: str) -> Dict[str, Any]:
    """Execute arbitrary Python in the Houdini session (`hou` is in scope).
    Assign to a variable named `result` to return a value; stdout is captured.
    The escape hatch for anything not covered by a structured tool."""
    return _call("execute_python", code=code)


@mcp.tool()
def houdini_create_node(
    parent: str, node_type: str, name: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a node of `node_type` under `parent` (e.g. parent='/obj').
    Optionally set `parameters` {parm_name: value} on it."""
    return _call("create_node", parent=parent, node_type=node_type,
                 name=name, parameters=parameters or {})


@mcp.tool()
def houdini_set_parameter(node_path: str, parameter: str, value: Any) -> Dict[str, Any]:
    """Set a single parameter `value` on the node at `node_path`."""
    return _call("set_parameter", node_path=node_path, parameter=parameter, value=value)


@mcp.tool()
def houdini_get_node_info(node_path: str) -> Dict[str, Any]:
    """Read a node's type, position, and all parameters. Ground yourself in real
    state before editing and verify after."""
    return _call("get_node_info", node_path=node_path)


@mcp.tool()
def houdini_get_selection() -> Dict[str, Any]:
    """Return the paths of the currently selected nodes."""
    return _call("get_selection")


@mcp.tool()
def houdini_read_network(
    parent_path: Optional[str] = None, use_selection: bool = False, brief: bool = True,
) -> Dict[str, Any]:
    """Read a whole network as structured Recipe data (hou.data). Pass
    `parent_path` for that node's children, or `use_selection=True`."""
    return _call("read_network", parent_path=parent_path,
                 use_selection=use_selection, brief=brief)


@mcp.tool()
def houdini_write_network(parent_path: str, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a network under `parent_path` from Recipe data (same shape as
    houdini_read_network returns)."""
    return _call("write_network", parent_path=parent_path, recipe_data=recipe_data)


@mcp.tool()
def houdini_save_scene(filepath: Optional[str] = None) -> Dict[str, Any]:
    """Save the current .hip (to `filepath` if given, else in place)."""
    return _call("save_scene", filepath=filepath)


# --------------------------------------------------------------------------- #
# Skills — the extendable recipe library (works without Houdini running)
# --------------------------------------------------------------------------- #

@mcp.tool()
def houdini_list_skills() -> List[Dict[str, Any]]:
    """List available Houdini skills/recipes (name, description, when-to-use).
    Check here before tackling a non-trivial Houdini task — a proven recipe may
    already exist."""
    return skills.list_skills()


@mcp.tool()
def houdini_get_skill(name: str) -> str:
    """Get the full markdown of one skill by name (from houdini_list_skills)."""
    try:
        return skills.get_skill(name)
    except KeyError as e:
        return str(e)


@mcp.tool()
def houdini_save_skill(
    name: str, description: str, when_to_use: str, body: str,
    tags: Optional[List[str]] = None,
) -> str:
    """Bank a new skill/recipe so future agents can discover and reuse it.
    Call this after working out a reliable Houdini procedure. `body` is markdown:
    inputs, step-by-step workflow, the non-obvious traps, and a done-condition."""
    path = skills.save_skill(name, description, when_to_use, body, tags)
    return f"Saved skill '{name}' to {path}"


if __name__ == "__main__":
    mcp.run()
