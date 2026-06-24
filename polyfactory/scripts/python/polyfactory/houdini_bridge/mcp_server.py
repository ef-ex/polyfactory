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
import re
import urllib.error
import urllib.request
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
# Houdini help server (the reflection / API-docs layer).
#
# Houdini runs a local help web server whenever it is open (default port 48626,
# bumping upward if taken). It serves the FULL version-correct manual: node
# reference (params + descriptions + examples), HOM Python reference, VEX,
# expressions, and auto-generated help for installed HDAs. We fetch it directly
# (localhost) — no bridge needed, so docs work whenever Houdini is open.
# --------------------------------------------------------------------------- #

_HELP_PORT_ENV = os.environ.get("HOUDINI_HELP_PORT")
_help_base_cache: Optional[str] = None


def _help_base() -> Optional[str]:
    """Resolve the live help-server base URL (cached). Honors HOUDINI_HELP_PORT,
    else probes the default 48626 and a few above it (the bump-on-conflict range)."""
    global _help_base_cache
    if _help_base_cache:
        return _help_base_cache
    ports = [int(_HELP_PORT_ENV)] if _HELP_PORT_ENV else list(range(48626, 48631))
    for p in ports:
        base = f"http://127.0.0.1:{p}"
        try:
            req = urllib.request.Request(base + "/", headers={"User-Agent": "houdini-mcp"})
            with urllib.request.urlopen(req, timeout=3) as r:
                if r.status == 200 and b"oudini" in r.read(2000):
                    _help_base_cache = base
                    return base
        except Exception:
            continue
    return None


def _html_to_text(raw: str) -> str:
    body = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    body = re.sub(r"(?s)<[^>]+>", " ", body)
    return re.sub(r"\s+", " ", body).strip()


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
# Reflection / API docs — read live from Houdini's own help server
# --------------------------------------------------------------------------- #

@mcp.tool()
def houdini_doc(path: str, max_chars: int = 8000) -> Dict[str, Any]:
    """Read version-correct Houdini documentation from the running editor's local
    help server. Use this to check the REAL API/parameters before writing code,
    instead of guessing from memory.

    `path` examples:
      nodes/sop/box        node reference (params, descriptions, examples)
      nodes/cop            a context's node list
      hom/hou/Node         HOM (Python) reference for a class
      vex/functions/noise  VEX function reference

    Returns readable text (HTML stripped), capped at max_chars. Requires Houdini
    to be open; does NOT require the bridge server."""
    base = _help_base()
    if not base:
        return {"ok": False, "error": "Houdini help server not reachable on "
                "127.0.0.1:48626(+). Is Houdini open?"}
    url = f"{base}/{path.lstrip('/')}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "houdini-mcp"})
        with urllib.request.urlopen(req, timeout=8) as r:
            ctype = r.headers.get("Content-Type", "")
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return {"ok": False, "url": url, "error": f"HTTP {e.code} - wrong path? "
                "Discover node types via the bridge or try a known scheme."}
    except Exception as e:
        return {"ok": False, "url": url, "error": str(e)}
    text = _html_to_text(raw) if "html" in ctype else raw
    return {"ok": True, "url": url, "truncated": len(text) > max_chars,
            "text": text[:max_chars]}


@mcp.tool()
def houdini_node_help(category: str, name: str, max_chars: int = 8000) -> Dict[str, Any]:
    """Convenience wrapper for node reference docs. `category` is the help-path
    context segment (sop, cop, obj, lop, dop, vop, chop, top, driver), `name` the
    node type. E.g. houdini_node_help('cop', 'opencl')."""
    return houdini_doc(f"nodes/{category}/{name}", max_chars)


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
