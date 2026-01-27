# Houdini Bridge - AI Agent WebSocket Server

## Overview

Enables AI agents in VS Code to control Houdini via WebSocket + MessagePack protocol.

## Architecture

```
VS Code Extension (AI Agent)
    |
    | WebSocket (localhost:9876)
    | MessagePack binary protocol
    |
Houdini Bridge Server
    |
    +-- MessageHandler (protocol parsing)
    +-- CommandExecutor (Houdini operations)
    +-- ApprovalManager (safety controls)
```

## Quick Start

### 1. Start Server in Houdini

```python
# In Houdini Python Shell or shelf button
from polyfactory.houdini_bridge import start_server

server = start_server()
# Server now listening on localhost:9876
```

### 2. Connect from VS Code

```typescript
// VS Code extension (TypeScript)
import * as WebSocket from 'ws';
import * as msgpack from 'msgpack-lite';

const ws = new WebSocket('ws://localhost:9876');

ws.on('open', () => {
    // Send command
    const command = {
        type: 'command',
        data: {
            type: 'create_node',
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

## Dependencies

- `websockets` - WebSocket server
- `msgpack` - MessagePack binary serialization

Install via pip:
```bash
pip install websockets msgpack
```

Or in Houdini's Python:
```bash
hython -m pip install websockets msgpack
```

## Security Considerations

- Server only listens on **localhost** - not accessible from network
- Approval system prevents accidental destructive operations
- Python code execution requires user approval by default
- All file operations use Houdini's file access permissions

## Performance

- **MessagePack** ~3x faster than JSON for encoding/decoding
- Binary protocol reduces bandwidth by ~30-40% vs JSON
- WebSocket maintains persistent connection (no HTTP overhead)
- Asyncio allows concurrent command processing

## Future Enhancements

- [ ] Authentication tokens for additional security
- [ ] Rate limiting for command execution
- [ ] Command history and undo support
- [ ] Event subscriptions (scene changes, parameter updates)
- [ ] Remote debugging support
- [ ] Multi-session support (multiple Houdini instances)
