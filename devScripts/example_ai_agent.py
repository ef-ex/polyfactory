"""
VS Code Extension Integration Example

Shows how a VS Code extension would connect to Houdini Bridge
and execute AI agent commands.

This would be the TypeScript equivalent translated to Python
for demonstration purposes.
"""

import asyncio
import websockets
import msgpack
from typing import Optional, Dict, Any


class HoudiniBridgeClient:
    """Client for connecting VS Code extension to Houdini"""
    
    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        self.uri = f"ws://{host}:{port}"
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        
    async def connect(self) -> bool:
        """Connect to Houdini Bridge server"""
        try:
            self.websocket = await websockets.connect(self.uri)
            self.connected = True
            print(f"[Bridge Client] Connected to {self.uri}")
            return True
        except Exception as e:
            print(f"[Bridge Client] Connection failed: {e}")
            return False
            
    async def disconnect(self):
        """Disconnect from server"""
        if self.websocket:
            await self.websocket.close()
            self.connected = False
            print("[Bridge Client] Disconnected")
            
    async def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command and wait for response"""
        if not self.connected or not self.websocket:
            raise RuntimeError("Not connected to server")
            
        # Wrap in command message
        message = {
            'type': 'command',
            'data': command
        }
        
        # Send MessagePack-encoded message
        await self.websocket.send(msgpack.packb(message, use_bin_type=True))
        
        # Wait for response
        response_data = await self.websocket.recv()
        response = msgpack.unpackb(response_data, raw=False)
        
        return response
        
    async def set_approval_mode(self, mode: str) -> Dict[str, Any]:
        """Set approval mode (auto/preview/destructive)"""
        message = {
            'type': 'set_approval_mode',
            'data': {'mode': mode}
        }
        
        await self.websocket.send(msgpack.packb(message, use_bin_type=True))
        response_data = await self.websocket.recv()
        return msgpack.unpackb(response_data, raw=False)


class AIAgentExample:
    """
    Example AI agent that uses Houdini Bridge to control Houdini.
    
    This demonstrates how GitHub Copilot or similar AI would interact
    with Houdini through the bridge.
    """
    
    def __init__(self):
        self.client = HoudiniBridgeClient()
        
    async def execute_task(self, task_description: str):
        """
        AI agent receives task from user, breaks it down, executes in Houdini.
        
        Example task: "Create a simple procedural tube setup"
        """
        print(f"\n[AI Agent] Task: {task_description}")
        
        # Connect to Houdini
        if not await self.client.connect():
            print("[AI Agent] Failed to connect to Houdini")
            return
            
        try:
            # AI breaks down task into commands
            # (In real implementation, LLM would generate this)
            
            if "procedural tube" in task_description.lower():
                await self._create_tube_setup()
            elif "box" in task_description.lower():
                await self._create_box()
            else:
                print("[AI Agent] Don't know how to handle this task yet")
                
        finally:
            await self.client.disconnect()
            
    async def _create_tube_setup(self):
        """Create a procedural tube setup"""
        print("[AI Agent] Creating procedural tube setup...")
        
        # Step 1: Create geometry node
        print("[AI Agent] Step 1: Create geo container")
        result = await self.client.send_command({
            'type': 'create_node',
            'parent': '/obj',
            'node_type': 'geo',
            'name': 'procedural_tube'
        })
        
        if not result['success']:
            print(f"[AI Agent] Error: {result['error']}")
            return
            
        geo_path = result['data']['node_path']
        print(f"[AI Agent] Created: {geo_path}")
        
        # Step 2: Create tube SOP
        print("[AI Agent] Step 2: Create tube SOP")
        result = await self.client.send_command({
            'type': 'create_node',
            'parent': geo_path,
            'node_type': 'tube',
            'name': 'tube1',
            'parameters': {
                'rad': 1.0,
                'radscale': 0.8,
                'height': 4.0
            }
        })
        
        if not result['success']:
            print(f"[AI Agent] Error: {result['error']}")
            return
            
        tube_path = result['data']['node_path']
        print(f"[AI Agent] Created: {tube_path}")
        
        # Step 3: Set display flag
        print("[AI Agent] Step 3: Configure tube parameters")
        await self.client.send_command({
            'type': 'set_parameter',
            'node_path': tube_path,
            'parameter': 'rows',
            'value': 32
        })
        
        await self.client.send_command({
            'type': 'set_parameter',
            'node_path': tube_path,
            'parameter': 'cols',
            'value': 24
        })
        
        # Step 4: Select the geo node
        print("[AI Agent] Step 4: Select created node")
        await self.client.send_command({
            'type': 'select_nodes',
            'nodes': [geo_path]
        })
        
        print("[AI Agent] ✓ Tube setup complete!")
        
    async def _create_box(self):
        """Create a simple box"""
        print("[AI Agent] Creating box...")
        
        result = await self.client.send_command({
            'type': 'create_node',
            'parent': '/obj',
            'node_type': 'geo',
            'name': 'box_geo'
        })
        
        geo_path = result['data']['node_path']
        
        await self.client.send_command({
            'type': 'create_node',
            'parent': geo_path,
            'node_type': 'box',
            'name': 'box1'
        })
        
        print("[AI Agent] ✓ Box created!")


# Example usage
async def main():
    """Simulate AI agent workflow"""
    agent = AIAgentExample()
    
    # Example 1: Create tube
    await agent.execute_task("Create a simple procedural tube setup")
    
    # Wait a bit
    await asyncio.sleep(1)
    
    # Example 2: Create box
    await agent.execute_task("Create a box")


if __name__ == "__main__":
    print("="*60)
    print("AI Agent Example - Houdini Bridge")
    print("="*60)
    print("\nThis demonstrates how an AI agent would control Houdini")
    print("through the WebSocket bridge from VS Code.\n")
    print("Make sure Houdini Bridge server is running!")
    print("="*60)
    
    asyncio.run(main())
