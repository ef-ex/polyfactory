# Houdini Bridge MCP — Setup

Connects a context-rich agent (Claude Code / Vela) to Houdini. The agent stays
the brain; Houdini is a tool it drives over the existing bridge (port 9876).

```
Agent (Claude Code / Vela)  ⇄ stdio ⇄  mcp_server.py  ⇄ ws:9876 ⇄  in-Houdini bridge  ⇄  hou
```

## 1. Install MCP server deps (one time)

Into the env that launches the MCP server — NOT Houdini's Python:

```powershell
F:/projects/polyfactory/.venv/Scripts/pip.exe install -r `
  F:/projects/polyfactory/polyfactory/scripts/python/polyfactory/houdini_bridge/requirements-mcp.txt
```

## 2. Start the in-Houdini bridge

Open Houdini → click the **AI Bridge** shelf button (or in the Python shell:
`from polyfactory.houdini_bridge import start_server; start_server()`). It listens
on `localhost:9876`.

## 3. Register the MCP server with your client

Add to the client's MCP config (Claude Code `.mcp.json`, Cursor, etc.). The server
is a module on `PYTHONPATH = .../polyfactory/scripts/python`:

```json
{
  "mcpServers": {
    "houdini": {
      "command": "F:/projects/polyfactory/.venv/Scripts/python.exe",
      "args": ["-m", "polyfactory.houdini_bridge.mcp_server"],
      "env": {
        "PYTHONPATH": "F:/projects/polyfactory/polyfactory/scripts/python",
        "HOUDINI_BRIDGE_HOST": "localhost",
        "HOUDINI_BRIDGE_PORT": "9876"
      }
    }
  }
}
```

Reload the client. Call `houdini_status` to confirm the bridge is reachable.

## Tools

**Control:** `houdini_status`, `houdini_execute_python`, `houdini_create_node`,
`houdini_set_parameter`, `houdini_get_node_info`, `houdini_get_selection`,
`houdini_read_network`, `houdini_write_network`, `houdini_save_scene`.

**Skills (extendable recipe library, works without Houdini running):**
`houdini_list_skills`, `houdini_get_skill`, `houdini_save_skill`. See `skills/README.md`.

## Notes
- Approval defaults to DISABLED in the bridge (no human-approval prompts block the
  agent). Change via the bridge's `ApprovalManager` if you want gating.
- v1 is the external shim. A v2 option is to embed an MCP/HTTP server inside
  Houdini (Epic UE-5.8 style) and drop the external process — see
  `documentation/DCC_MCP_BEST_PRACTICES.md`.
- Next tool to add: `render_view` (flipbook/COP → PNG) for a visual feedback loop.
