# Houdini Bridge - Installation & Setup

## Prerequisites

### Python Dependencies

The bridge requires two packages that aren't included with Houdini by default:

```bash
# In Houdini's Python (hython or from Houdini Python Shell)
python -m pip install websockets msgpack
```

Or use Houdini's `hython`:
```bash
hython -m pip install websockets msgpack
```

**For Windows:**
```powershell
cd "C:\Program Files\Side Effects Software\Houdini 21.0.603\bin"
.\hython.exe -m pip install websockets msgpack
```

## Quick Start

### 1. Start Bridge Server in Houdini

**Option A: Shelf Button (Recommended)**
1. Load Polyfactory shelf
2. Click "AI Bridge" button
3. Server starts on `localhost:9876`

**Option B: Python Shell**
```python
from polyfactory.houdini_bridge import start_server
server = start_server()
```

### 2. Test Connection

From external Python:
```bash
python devScripts/test_bridge_client.py
```

This will run through several test commands and verify the connection works.

### 3. Try AI Agent Example

```bash
python devScripts/example_ai_agent.py
```

This demonstrates how an AI agent would control Houdini by creating procedural setups.

## VS Code Extension Integration

### TypeScript/JavaScript Example

```typescript
import * as WebSocket from 'ws';
import * as msgpack from 'msgpack-lite';

class HoudiniBridge {
    private ws: WebSocket;
    
    async connect(): Promise<void> {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket('ws://localhost:9876');
            
            this.ws.on('open', () => {
                console.log('[Bridge] Connected to Houdini');
                resolve();
            });
            
            this.ws.on('error', (error) => {
                console.error('[Bridge] Connection error:', error);
                reject(error);
            });
        });
    }
    
    async sendCommand(command: any): Promise<any> {
        return new Promise((resolve, reject) => {
            const message = {
                type: 'command',
                data: command
            };
            
            // Send MessagePack-encoded message
            this.ws.send(msgpack.encode(message));
            
            // Wait for response
            const handler = (data: Buffer) => {
                const response = msgpack.decode(data);
                this.ws.removeListener('message', handler);
                resolve(response);
            };
            
            this.ws.on('message', handler);
        });
    }
}

// Usage in VS Code extension
async function createTube() {
    const bridge = new HoudiniBridge();
    await bridge.connect();
    
    const result = await bridge.sendCommand({
        type: 'create_node',
        parent: '/obj',
        node_type: 'geo',
        name: 'my_tube'
    });
    
    console.log('Created:', result.data.node_path);
}
```

### Required npm Packages

```json
{
  "dependencies": {
    "ws": "^8.0.0",
    "msgpack-lite": "^0.1.26"
  }
}
```

## Approval Modes

The bridge has three safety modes:

### AUTO (Default)
- Read-only operations execute immediately
- Destructive operations require approval
- Best for normal AI agent usage

### PREVIEW
- All operations require approval
- Shows preview before execution
- Best for learning/debugging

### DESTRUCTIVE
- Only destructive operations require approval
- Same as AUTO
- Explicit name for clarity

**Change mode:**
```python
# In Houdini Python Shell
from polyfactory.houdini_bridge import get_server
server = get_server()
server.handler.approval.set_mode(ApprovalMode.PREVIEW)
```

Or from client:
```python
await client.send_command({
    'type': 'set_approval_mode',
    'data': {'mode': 'preview'}
})
```

## Troubleshooting

### "Module not found: websockets"

Install the package in Houdini's Python:
```bash
hython -m pip install websockets msgpack
```

### "Connection refused"

Make sure:
1. Bridge server is running in Houdini
2. No firewall blocking localhost:9876
3. Port 9876 isn't used by another application

Check server status:
```python
from polyfactory.houdini_bridge import get_server
server = get_server()
print(f"Running: {server.is_running()}")
print(f"Connections: {server.get_connection_count()}")
```

### "Command cancelled by user"

This is normal - you clicked "Cancel" in the approval dialog.
To avoid approvals, set mode to `auto` (default) or execute only read-only operations.

### Server stops responding

Restart the server:
```python
from polyfactory.houdini_bridge import stop_server, start_server
stop_server()
start_server()
```

## Security Notes

- Server **only listens on localhost** - not accessible from network
- Cannot be accessed remotely without port forwarding
- All file operations use Houdini's permissions
- Python code execution requires approval by default

## Performance

**Benchmarks (approximate):**
- MessagePack encoding: ~3x faster than JSON
- Message size: ~30-40% smaller than JSON
- Connection overhead: Persistent (no HTTP handshake per request)
- Command latency: <10ms for simple operations

**Recommended usage:**
- Batch multiple commands when possible
- Use session state for persistent data
- Avoid polling - bridge can push events (future feature)

## Development

### Reload modules during development

```python
from polyfactory.asset_library import reload_modules
reload_modules.reload_houdini_bridge()
```

### Debug mode

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Test without VS Code

Use the test scripts:
- `devScripts/test_bridge_client.py` - Basic command tests
- `devScripts/example_ai_agent.py` - AI workflow simulation
