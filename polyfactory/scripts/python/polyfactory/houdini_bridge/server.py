"""
Bridge Server - WebSocket server for AI agent communication

Runs in Houdini's main thread using asyncio event loop.
Listens on localhost:9876 for VS Code extension connections.

Usage:
    from polyfactory.houdini_bridge import BridgeServer
    server = BridgeServer()
    server.start()
"""

import asyncio
import websockets
from typing import Optional, Set
import threading

from .message_handler import MessageHandler


class BridgeServer:
    """WebSocket server for AI agent communication"""
    
    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        self.handler = MessageHandler()
        self.server: Optional[websockets.WebSocketServer] = None
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[threading.Thread] = None
        self.active_connections: Set[websockets.WebSocketServerProtocol] = set()
        self.running = False
        
    def start(self):
        """Start server in background thread"""
        if self.running:
            print("[Bridge] Server already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        
        print(f"[Bridge] Server started on {self.host}:{self.port}")
        print("[Bridge] Waiting for AI agent connection...")
        
    def stop(self):
        """Stop server"""
        if not self.running:
            return
            
        self.running = False
        
        if self.loop:
            self.loop.call_soon_threadsafe(self._shutdown)
            
        if self.thread:
            self.thread.join(timeout=5.0)
            
        print("[Bridge] Server stopped")
        
    def _run_server(self):
        """Run asyncio event loop in background thread"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._start_websocket_server())
            self.loop.run_forever()
        except Exception as e:
            print(f"[Bridge] Server error: {e}")
        finally:
            self.loop.close()
            
    async def _start_websocket_server(self):
        """Start WebSocket server"""
        try:
            self.server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                max_size=10 * 1024 * 1024,  # 10MB max message size
                compression=None  # Disable compression (MessagePack already efficient)
            )
        except Exception as e:
            print(f"[Bridge] Failed to start server: {e}")
            self.running = False
            
    async def _handle_connection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle client connection"""
        self.active_connections.add(websocket)
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        
        print(f"[Bridge] AI agent connected: {client_info}")
        
        try:
            async for message in websocket:
                # Handle binary MessagePack messages
                if isinstance(message, bytes):
                    response = self.handler.handle_binary(message)
                    await websocket.send(response)
                else:
                    # Text messages not supported
                    error_msg = b'\x81\xa5error\xb7Unsupported message type'
                    await websocket.send(error_msg)
                    
        except websockets.exceptions.ConnectionClosed:
            print(f"[Bridge] AI agent disconnected: {client_info}")
        except Exception as e:
            print(f"[Bridge] Connection error: {e}")
        finally:
            self.active_connections.discard(websocket)
            
    def _shutdown(self):
        """Shutdown server gracefully"""
        if self.server:
            self.server.close()
            
        # Close all active connections
        for connection in list(self.active_connections):
            asyncio.create_task(connection.close())
            
        self.loop.stop()
        
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running
        
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
        
    def broadcast(self, message: dict):
        """
        Broadcast message to all connected clients.
        Useful for notifications/events from Houdini.
        """
        import msgpack
        
        if not self.active_connections:
            return
            
        data = msgpack.packb(message, use_bin_type=True)
        
        for connection in list(self.active_connections):
            try:
                asyncio.run_coroutine_threadsafe(
                    connection.send(data),
                    self.loop
                )
            except Exception as e:
                print(f"[Bridge] Broadcast error: {e}")


# Global server instance
_server_instance: Optional[BridgeServer] = None


def get_server() -> BridgeServer:
    """Get or create global server instance"""
    global _server_instance
    if _server_instance is None:
        _server_instance = BridgeServer()
    return _server_instance


def start_server():
    """Start global server instance"""
    server = get_server()
    server.start()
    return server


def stop_server():
    """Stop global server instance"""
    global _server_instance
    if _server_instance:
        _server_instance.stop()
        _server_instance = None
