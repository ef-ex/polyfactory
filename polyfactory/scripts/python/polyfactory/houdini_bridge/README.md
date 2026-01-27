# Houdini Bridge - AI Agent WebSocket Server

## Overview

Enables AI agents and external tools to control Houdini via WebSocket + MessagePack protocol.

**Features:**
- WebSocket server running in Houdini (localhost:9876)
- Binary MessagePack protocol for efficient communication
- Synchronous API (no asyncio) compatible with Houdini's threading model
- Safe command execution with approval modes
- Session state management

## Dependencies

### Houdini (Server-side)

Install these in Houdini's Python environment:

```powershell
# Using hython (Houdini's Python)
& "C:\Program Files\Side Effects Software\Houdini 21.0.603\bin\hython.exe" -m pip install websockets msgpack
```

**Required packages:**
- `websockets==16.0` - WebSocket server/client library
- `msgpack==1.1.2` - MessagePack binary serialization

### External Python (Client-side)

For testing or building custom clients:

```bash
pip install websockets msgpack
```

## Quick Start

### 1. Start Server in Houdini

**Option A: Shelf Button**
- Click the "AI Bridge" shelf button in Houdini
- Server starts on port 9876 (or next available port)

**Option B: Python Shell**
```python
from polyfactory.houdini_bridge import start_server

server = start_server()
# Server now listening on localhost:9876
```

**Option C: Houdini Startup Script**
```python
# In $HOUDINI_USER_PREF_DIR/scripts/123.py
from polyfactory.houdini_bridge import start_server
start_server()
```

### 2. Connect from External Python

```python
from websockets.sync.client import connect as ws_connect
import msgpack

# Connect to server
with ws_connect('ws://localhost:9876') as websocket:
    # Send command (MessagePack binary)
    command = {
        'type': 'command',
        'data': {
            'command': 'create_node',
            'parent': '/obj',
            'node_type': 'geo',
            'name': 'my_geo'
        }
    }
    
    websocket.send(msgpack.packb(command, use_bin_type=True))
    
    # Receive response
    response_data = websocket.recv()
    response = msgpack.unpackb(response_data, raw=False)
    
    print(response)
    # {'success': True, 'data': {'node_path': '/obj/my_geo', ...}}
```

### 3. Connect from VS Code Extension (TypeScript)

```typescript
import * as WebSocket from 'ws';
import * as msgpack from 'msgpack-lite';

const ws = new WebSocket('ws://localhost:9876');

ws.on('open', () => {
    const command = {
        type: 'command',
        data: {
            command: 'create_node',
            parent: '/obj',
            node_type: 'geo',
            name: 'my_geo'
        }
    };
    
    ws.send(msgpack.encode(command));
});

ws.on('message', (data) => {
    const response = msgpack.decode(data);
    console.log('Response:', response);
});
```

## Protocol

### Message Format

All messages use MessagePack binary encoding.

**Command Message:**
```python
{
    'type': 'command',
    'data': {
        'type': 'create_node',  # Command type
        'parent': '/obj',        # Command-specific data
        'node_type': 'geo',
        'name': 'my_geo'
    }
}
```

**Response:**
```python
{
    'success': True,
    'data': {
        'node_path': '/obj/my_geo',
        'node_type': 'geo',
        'name': 'my_geo'
    }
}
```

**Error Response:**
```python
{
    'success': False,
    'error': 'Node not found: /obj/missing',
    'traceback': '...'  # Python traceback if available
}
```

## Supported Commands

### Node Operations

**Create Node:**
```python
{
    'type': 'create_node',
    'parent': '/obj',
    'node_type': 'geo',
    'name': 'my_geo',
    'parameters': {  # Optional
        'tx': 1.0,
        'ty': 2.0
    }
}
```

**Delete Node:**
```python
{
    'type': 'delete_node',
    'node_path': '/obj/geo1'
}
```

**Set Parameter:**
```python
{
    'type': 'set_parameter',
    'node_path': '/obj/geo1',
    'parameter': 'tx',
    'value': 5.0
}
```

**Get Parameter:**
```python
{
    'type': 'get_parameter',
    'node_path': '/obj/geo1',
    'parameter': 'tx'
}
```

**Get Node Info:**
```python
{
    'type': 'get_node_info',
    'node_path': '/obj/geo1'
}
```

### Selection Operations

**Get Selection:**
```python
{
    'type': 'get_selection'
}
```

**Select Nodes:**
```python
{
    'type': 'select_nodes',
    'nodes': ['/obj/geo1', '/obj/geo2']
}
```

### Python Execution

**Execute Python Code:**
```python
{
    'type': 'execute_python',
    'code': 'result = hou.node("/obj").children()'
}
```

Set `result` variable to return value to agent.

### File Operations

**Save Scene:**
```python
{
    'type': 'save_scene',
    'filepath': '/path/to/scene.hip'  # Optional
}
```

**Load Scene:**
```python
{
    'type': 'load_scene',
    'filepath': '/path/to/scene.hip'
}
```

### Session State

**Get State:**
```python
{
    'type': 'get_session_state',
    'key': 'my_variable'  # Optional, omit to get all state
}
```

**Set State:**
```python
{
    'type': 'set_session_state',
    'key': 'my_variable',
    'value': {'some': 'data'}
}
```

### Batch Commands

Execute multiple commands:
```python
{
    'type': 'batch',
    'data': {
        'commands': [
            {'type': 'create_node', ...},
            {'type': 'set_parameter', ...},
            {'type': 'save_scene', ...}
        ]
    }
}
```

## Approval Modes

Control command execution safety:

```python
{
    'type': 'set_approval_mode',
    'data': {
        'mode': 'auto'  # or 'preview', 'destructive'
    }
}
```

**Modes:**
- `auto`: Execute read-only operations automatically, confirm destructive operations
- `preview`: Show preview for ALL operations before execution
- `destructive`: Only confirm operations that modify scene

**Destructive Commands:**
- create_node
- delete_node
- set_parameter
- execute_python
- load_scene

## Testing

### Run Test Suite

A comprehensive test client is included:

```powershell
# Start Houdini and run the bridge server first
# Then from external terminal:
python devScripts/test_bridge_client.py --port 9876
```

**Test coverage:**
1. ✓ Ping - Server connectivity
2. ✓ Get Selection - Command execution
3. ✓ Create Node - Node creation
4. ✓ Get Node Info - Parameter introspection
5. ✓ Set Approval Mode - Configuration
6. ✓ Session State - State management

### Manual Testing

```python
from websockets.sync.client import connect as ws_connect
import msgpack

with ws_connect('ws://localhost:9876') as ws:
    # Ping test
    ws.send(msgpack.packb({'type': 'ping'}, use_bin_type=True))
    response = msgpack.unpackb(ws.recv(), raw=False)
    print(response)  # {'success': True, 'data': {'pong': True}}
```

## Troubleshooting

### Port Already in Use

If you see "Port 9876 already in use":
1. Click the AI Bridge shelf button to stop/restart the server
2. If that fails, restart Houdini to clear zombie sockets
3. Server will automatically try alternate ports (9877-9880)

### Connection Timeout

If connection times out:
1. Verify server is running: Check for "WebSocket server running on..." message
2. Check firewall settings (allow localhost connections)
3. Verify websockets library is installed in both Houdini and external Python

### Module Not Found

If you get "No module named 'websockets'":
```powershell
# Install in Houdini's Python
& "C:\Program Files\Side Effects Software\Houdini 21.0.603\bin\hython.exe" -m pip install websockets msgpack
```

### Performance Issues

If commands are slow:
- Use batch commands to reduce round-trips
- MessagePack is already optimized for speed
- Consider running expensive operations in background threads

## Architecture

```
External Client (Python/VS Code)
    |
    | WebSocket (localhost:9876)
    | MessagePack binary protocol
    |
Houdini Bridge Server (Background Thread)
    |
    +-- MessageHandler (protocol parsing)
    +-- CommandExecutor (Houdini operations)
    +-- ApprovalManager (safety controls)
    |
    v
Houdini Python API (Main Thread)
```

**Threading Model:**
- Server runs in daemon background thread
- Synchronous `serve_forever()` accepts connections
- Each connection handled synchronously
- Commands executed in main thread via Houdini API

## Server Management

```python
from polyfactory.houdini_bridge import get_server, start_server, stop_server

# Start server
server = start_server()

# Check status
if server.is_running():
    print(f"Active connections: {server.get_connection_count()}")

# Broadcast event to all clients
server.broadcast({
    'type': 'event',
    'data': {'event': 'scene_changed'}
})

# Stop server
stop_server()
```

## Security Considerations

- Server only listens on **localhost** - not accessible from network
- Approval system prevents accidental destructive operations
- Python code execution requires user approval by default
- All file operations use Houdini's file access permissions
- No authentication required (localhost-only trusted environment)

## Technical Notes

### Why Synchronous WebSockets?

Houdini's custom `asyncio` implementation (haio.py) enforces main thread execution, causing `RuntimeError` with async WebSocket servers. The synchronous `websockets.sync.server` API works in background threads without conflicts.

### Port Selection

Server tries ports in order: 9876, 9877, 9878, 9879, 9880. This prevents conflicts when restarting after crashes or when multiple Houdini instances run.

### Module Reloading

Server instance stored in `hou.session` to survive module reloads during development. Avoid reloading server module in production.

## Performance

- **MessagePack** ~3x faster than JSON for encoding/decoding
- Binary protocol reduces bandwidth by ~30-40% vs JSON
- WebSocket maintains persistent connection (no HTTP overhead)
- Synchronous processing ensures thread-safe Houdini API access

## License

Part of Polyfactory package. See LICENSE file in repository root.
