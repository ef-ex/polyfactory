"""
Test Client for Houdini Bridge

Simple Python client to test WebSocket + MessagePack communication.
Run this from external Python (not Houdini) after starting the bridge server.

Requirements:
    pip install websockets msgpack

Usage:
    python test_bridge_client.py [--port PORT]
"""

from websockets.sync.client import connect as ws_connect
import msgpack
import sys


def test_connection(port=9876):
    """Test basic connection and commands"""
    uri = f"ws://localhost:{port}"
    
    print(f"Connecting to {uri}...")
    
    try:
        with ws_connect(uri) as websocket:
            print("Connected!")
            
            # Test 1: Ping
            print("\n--- Test 1: Ping ---")
            ping_msg = {'type': 'ping'}
            websocket.send(msgpack.packb(ping_msg, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Response: {response}")
            
            # Test 2: Get selection
            print("\n--- Test 2: Get Selection ---")
            cmd = {
                'type': 'command',
                'data': {
                    'type': 'get_selection'
                }
            }
            websocket.send(msgpack.packb(cmd, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Response: {response}")
            
            # Test 3: Create node (will require approval)
            print("\n--- Test 3: Create Node ---")
            cmd = {
                'type': 'command',
                'data': {
                    'type': 'create_node',
                    'parent': '/obj',
                    'node_type': 'geo',
                    'name': 'test_geo'
                }
            }
            websocket.send(msgpack.packb(cmd, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Response: {response}")
            
            # Test 4: Get node info (if creation succeeded)
            if response.get('success'):
                print("\n--- Test 4: Get Node Info ---")
                node_path = response['data']['node_path']
                cmd = {
                    'type': 'command',
                    'data': {
                        'type': 'get_node_info',
                        'node_path': node_path
                    }
                }
                websocket.send(msgpack.packb(cmd, use_bin_type=True))
                response = msgpack.unpackb(websocket.recv(), raw=False)
                print(f"Response keys: {response['data'].keys()}")
                print(f"Node type: {response['data']['type']}")
                print(f"Parameter count: {len(response['data']['parameters'])}")
            
            # Test 5: Set approval mode
            print("\n--- Test 5: Set Approval Mode ---")
            cmd = {
                'type': 'set_approval_mode',
                'data': {
                    'mode': 'auto'
                }
            }
            websocket.send(msgpack.packb(cmd, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Response: {response}")
            
            # Test 6: Session state
            print("\n--- Test 6: Session State ---")
            cmd = {
                'type': 'command',
                'data': {
                    'type': 'set_session_state',
                    'key': 'test_var',
                    'value': {'foo': 'bar', 'count': 42}
                }
            }
            websocket.send(msgpack.packb(cmd, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Set state: {response}")
            
            cmd = {
                'type': 'command',
                'data': {
                    'type': 'get_session_state',
                    'key': 'test_var'
                }
            }
            websocket.send(msgpack.packb(cmd, use_bin_type=True))
            response = msgpack.unpackb(websocket.recv(), raw=False)
            print(f"Get state: {response}")
            
            print("\n✓ All tests completed!")
            
    except ConnectionRefusedError:
        print("ERROR: Could not connect to server.")
        print("Make sure Houdini Bridge server is running.")
        print("In Houdini: Click 'AI Bridge' shelf button")
        print("Or in Houdini Python Shell:")
        print("  from polyfactory.houdini_bridge import start_server")
        print("  start_server()")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()


def test_batch_commands():
    """Test batch command execution"""
    uri = "ws://localhost:9876"
    
    print(f"\n--- Test: Batch Commands ---")
    print(f"Connecting to {uri}...")
    
    with ws_connect(uri) as websocket:
        batch_msg = {
            'type': 'batch',
            'data': {
                'commands': [
                    {
                        'type': 'create_node',
                        'parent': '/obj',
                        'node_type': 'geo',
                        'name': 'batch_geo_1'
                    },
                    {
                        'type': 'create_node',
                        'parent': '/obj',
                        'node_type': 'geo',
                        'name': 'batch_geo_2'
                    },
                    {
                        'type': 'get_selection'
                    }
                ]
            }
        }
        
        websocket.send(msgpack.packb(batch_msg, use_bin_type=True))
        response = msgpack.unpackb(websocket.recv(), raw=False)
        
        print(f"Batch results:")
        for i, result in enumerate(response['data']['results']):
            print(f"  Command {i+1}: {'✓' if result['success'] else '✗'}")
            if result['success']:
                print(f"    Data: {result.get('data', {})}")


if __name__ == "__main__":
    print("="*60)
    print("Houdini Bridge Test Client")
    print("="*60)
    
    # Parse port argument
    port = 9876
    if len(sys.argv) > 1:
        for i, arg in enumerate(sys.argv):
            if arg == "--port" and i + 1 < len(sys.argv):
                try:
                    port = int(sys.argv[i + 1])
                except ValueError:
                    print(f"Invalid port: {sys.argv[i + 1]}, using default 9876")
    
    # Run basic tests
    test_connection(port)
    
    # Uncomment to test batch commands:
    # test_batch_commands()
