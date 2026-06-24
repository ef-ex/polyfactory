"""
Bridge client — thin sync WebSocket + MessagePack client for the in-Houdini
bridge server (see server.py / message_handler.py).

Used by mcp_server.py to forward MCP tool calls into Houdini. One short-lived
connection per call: simple, and the bridge's MessageHandler state (approval
mode, session state) persists server-side across connections.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import msgpack
from websockets.sync.client import connect


class BridgeError(RuntimeError):
    pass


class BridgeClient:
    def __init__(self, host: str = "localhost", port: int = 9876, timeout: float = 30.0):
        self.uri = f"ws://{host}:{port}"
        self.timeout = timeout

    def _round_trip(self, message: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with connect(self.uri, open_timeout=5) as ws:
                ws.send(msgpack.packb(message, use_bin_type=True))
                raw = ws.recv(timeout=self.timeout)
        except (ConnectionRefusedError, OSError, TimeoutError) as e:
            raise BridgeError(
                f"Houdini bridge not reachable at {self.uri} ({e}). "
                "Is Houdini open and the bridge server started (shelf button / "
                "start_server())?"
            ) from e
        if isinstance(raw, str):
            raise BridgeError(f"Unexpected text response: {raw}")
        return msgpack.unpackb(raw, raw=False)

    def ping(self) -> Dict[str, Any]:
        return self._round_trip({"type": "ping"})

    def command(self, cmd_type: str, **params: Any) -> Dict[str, Any]:
        """Run a CommandExecutor command. Returns the raw response dict
        ({'success', 'data', 'error', ...}) so the agent sees errors verbatim
        and can self-correct."""
        data = {"type": cmd_type}
        data.update(params)
        return self._round_trip({"type": "command", "data": data})
