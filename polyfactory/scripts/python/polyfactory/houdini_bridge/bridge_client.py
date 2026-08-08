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


# The in-Houdini server bumps 9876 -> 9877..9880 when the port is taken (e.g. a
# zombie socket after a crash). Probe the same range so a bumped server is still
# reachable, and cache the port that answered.
_PORT_SPAN = 5


class BridgeClient:
    def __init__(self, host: str = "localhost", port: int = 9876, timeout: float = 30.0):
        self.host = host
        self.base_port = port
        self.timeout = timeout
        self._port: Optional[int] = None  # last port that answered (cached)

    def _round_trip(self, message: Dict[str, Any]) -> Dict[str, Any]:
        ports = [self._port] if self._port is not None \
            else list(range(self.base_port, self.base_port + _PORT_SPAN))
        conn_errors = []
        for port in ports:
            uri = f"ws://{self.host}:{port}"
            try:
                ws = connect(uri, open_timeout=5)
            except (ConnectionRefusedError, OSError, TimeoutError) as e:
                conn_errors.append(f"{port}: {e}")
                continue
            # Connected — commit to this port. A recv timeout past this point is
            # NOT retried on another port: the command already ran server-side and
            # retrying could double-execute a mutation.
            self._port = port
            with ws:
                ws.send(msgpack.packb(message, use_bin_type=True))
                try:
                    raw = ws.recv(timeout=self.timeout)
                except (OSError, TimeoutError) as e:
                    raise BridgeError(
                        f"No response from bridge on port {port} within "
                        f"{self.timeout}s ({e})."
                    ) from e
            if isinstance(raw, str):
                raise BridgeError(f"Unexpected text response: {raw}")
            return msgpack.unpackb(raw, raw=False)

        # Nothing accepted a connection. If we were only trying a cached port,
        # widen the search once (Houdini may have restarted on a different port).
        if self._port is not None:
            self._port = None
            return self._round_trip(message)

        raise BridgeError(
            f"Houdini bridge not reachable on {self.host} ports "
            f"{self.base_port}-{self.base_port + _PORT_SPAN - 1} "
            f"({'; '.join(conn_errors)}). Is Houdini open and the bridge server "
            "started (shelf button / start_server())?"
        )

    def ping(self) -> Dict[str, Any]:
        return self._round_trip({"type": "ping"})

    def command(self, cmd_type: str, **params: Any) -> Dict[str, Any]:
        """Run a CommandExecutor command. Returns the raw response dict
        ({'success', 'data', 'error', ...}) so the agent sees errors verbatim
        and can self-correct."""
        data = {"type": cmd_type}
        data.update(params)
        return self._round_trip({"type": "command", "data": data})
