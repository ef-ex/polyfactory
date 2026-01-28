"""
Bridge Server - WebSocket server for AI agent communication

Uses synchronous WebSocket server to avoid Houdini's asyncio thread restrictions.
Listens on localhost:9876 for VS Code extension connections.
"""

import threading
import socket
import struct
import time
from typing import Optional, Set

from websockets.sync.server import serve as ws_serve
from websockets.sync.server import ServerConnection

from .message_handler import MessageHandler

# Check if we're in Houdini
try:
    import hou
    IN_HOUDINI = True
except ImportError:
    IN_HOUDINI = False


class BridgeServer:
    """WebSocket server for AI agent communication"""
    
    def __init__(self, host: str = "localhost", port: int = 9876):
        self.host = host
        self.port = port
        self.original_port = port
        self.handler = MessageHandler()
        self.server = None
        self.server_socket: Optional[socket.socket] = None
        self.thread: Optional[threading.Thread] = None
        self.active_connections: Set[ServerConnection] = set()
        self.running = False
        
    def start(self):
        """Start server in background thread"""
        if self.running:
            print("[Bridge] Server already running")
            return
        
        # Try alternate ports if original is blocked
        ports_to_try = [self.original_port, 9877, 9878, 9879, 9880]
        for port in ports_to_try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                test_sock.bind((self.host, port))
                test_sock.close()
                self.port = port
                break
            except OSError:
                test_sock.close()
                if port == ports_to_try[-1]:
                    print(f"[Bridge] ERROR: All ports {ports_to_try} are in use!")
                    print("[Bridge] Please restart Houdini to clear zombie sockets")
                    return
            
        self.running = True
        
        # Use daemon thread to avoid blocking Houdini exit
        self.thread = threading.Thread(target=self._run_server, daemon=True)
        self.thread.start()
        
        print(f"[Bridge] Server starting on {self.host}:{self.port}")
        if self.port != self.original_port:
            print(f"[Bridge] WARNING: Using alternate port {self.port} (original {self.original_port} was in use)")
        print("[Bridge] Waiting for AI agent connection...")
        
        time.sleep(0.2)  # Give thread time to start
        
    def stop(self):
        """Stop server"""
        if not self.running:
            print("[Bridge] Server not running")
            return
            
        print("[Bridge] Stopping server...")
        self.running = False
        
        # Close all active connections
        for conn in list(self.active_connections):
            try:
                conn.close()
            except Exception as e:
                print(f"[Bridge] Error closing connection: {e}")
        
        # Shutdown server
        if self.server:
            try:
                self.server.shutdown()
            except Exception as e:
                print(f"[Bridge] Error shutting down server: {e}")
        
        # Force close socket with SO_LINGER
        if self.server_socket:
            try:
                self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, 
                                              struct.pack('ii', 1, 0))
                self.server_socket.close()
            except Exception as e:
                print(f"[Bridge] Error closing socket: {e}")
            
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                print("[Bridge] Warning: Server thread did not exit cleanly")
            
        self.server = None
        self.server_socket = None
        self.thread = None
        
        time.sleep(0.5)  # Give OS time to release port
        print("[Bridge] Server stopped")
        
    def _run_server(self):
        """Run synchronous WebSocket server in background thread"""
        try:
            # Create and start WebSocket server
            with ws_serve(self._handle_connection, self.host, self.port) as server:
                self.server = server
                self.server_socket = server.socket
                print(f"[Bridge] WebSocket server running on {self.host}:{self.port}")
                
                # Must call serve_forever() to accept connections
                server.serve_forever()
                    
        except OSError as e:
            if e.errno == 10048:
                print(f"[Bridge] Port {self.port} already in use")
            else:
                print(f"[Bridge] Server error: {e}")
            self.running = False
        except Exception as e:
            print(f"[Bridge] Server error: {e}")
            import traceback
            traceback.print_exc()
            self.running = False
        finally:
            print("[Bridge] Server thread exiting")
            
    def _handle_connection(self, websocket: ServerConnection):
        """Handle client connection"""
        try:
            self.active_connections.add(websocket)
            client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
            print(f"[Bridge] AI agent connected: {client_info}")
        except Exception as e:
            print(f"[Bridge] Error in connection setup: {e}")
            return
        
        try:
            for message in websocket:
                if isinstance(message, bytes):
                    response = self.handler.handle_binary(message)
                    websocket.send(response)
                else:
                    # Text messages not supported
                    error_msg = b'\x81\xa5error\xb7Unsupported message type'
                    websocket.send(error_msg)
                    
        except Exception as e:
            print(f"[Bridge] Connection error: {e}")
        finally:
            self.active_connections.discard(websocket)
            print(f"[Bridge] AI agent disconnected: {client_info}")
            
    def is_running(self) -> bool:
        """Check if server is running"""
        return self.running
        
    def get_connection_count(self) -> int:
        """Get number of active connections"""
        return len(self.active_connections)
        
    def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        import msgpack
        
        if not self.active_connections:
            return
            
        data = msgpack.packb(message, use_bin_type=True)
        
        for connection in list(self.active_connections):
            try:
                connection.send(data)
            except Exception as e:
                print(f"[Bridge] Broadcast error: {e}")


# Global server instance
_server_instance: Optional[BridgeServer] = None


def get_server() -> BridgeServer:
    """Get or create global server instance (survives module reload)"""
    global _server_instance
    
    # Check if server exists in hou.session (survives module reload)
    if IN_HOUDINI:
        import hou
        if hasattr(hou.session, '_bridge_server'):
            _server_instance = hou.session._bridge_server
            return _server_instance
    
    # Create new instance if needed
    if _server_instance is None:
        _server_instance = BridgeServer()
        
        # Store in hou.session to survive module reloads
        if IN_HOUDINI:
            import hou
            hou.session._bridge_server = _server_instance
    
    return _server_instance


def start_server():
    """Start global server instance"""
    server = get_server()
    server.start()
    return server


def stop_server():
    """Stop global server instance"""
    global _server_instance
    
    # Check both module global and hou.session
    server_to_stop = _server_instance
    if IN_HOUDINI:
        import hou
        if hasattr(hou.session, '_bridge_server'):
            server_to_stop = hou.session._bridge_server
    
    if server_to_stop:
        server_to_stop.stop()
    else:
        print("[Bridge] No server instance to stop")
