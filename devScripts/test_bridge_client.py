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


def test_diagnostics(port=9876):
    """Test get_errors and validate_vex commands"""
    uri = f"ws://localhost:{port}"

    def send(ws, cmd):
        ws.send(msgpack.packb({'type': 'command', 'data': cmd}, use_bin_type=True))
        return msgpack.unpackb(ws.recv(), raw=False)

    with ws_connect(uri) as websocket:
        # Test 1: scene-wide error sweep
        print("\n--- Diagnostics 1: get_errors (scene sweep) ---")
        r = send(websocket, {'type': 'get_errors'})
        assert r['success'], r
        print(f"Scanned {r['data']['nodes_scanned']} nodes, "
              f"{r['data']['nodes_with_issues']} with issues")

        # Test 2: validate a GOOD snippet — expect ok + result_geometry
        print("\n--- Diagnostics 2: validate_vex (good snippet) ---")
        r = send(websocket, {
            'type': 'validate_vex',
            'snippet': 'f@mask = rand(@ptnum); @P.y += 0.1 * sin(@P.x);',
        })
        assert r['success'], r
        assert r['data']['ok'], f"good snippet reported errors: {r['data']['errors']}"
        assert 'mask' in r['data']['result_geometry']['point_attribs']
        print(f"ok={r['data']['ok']}, run_over={r['data']['run_over']}, "
              f"attribs={r['data']['result_geometry']['point_attribs']}")

        # Test 3: validate a BAD snippet — expect compiler error, not ok
        print("\n--- Diagnostics 3: validate_vex (bad snippet) ---")
        r = send(websocket, {
            'type': 'validate_vex',
            'snippet': '@P.y += noize(@P.x);',  # misspelled function
        })
        assert r['success'], r
        assert not r['data']['ok'], "bad snippet was not flagged"
        print(f"ok={r['data']['ok']}, errors={r['data']['errors']}")

        # Test 4: validate a GOOD OpenCL kernel — expect ok
        print("\n--- Diagnostics 4: validate_opencl (good kernel) ---")
        r = send(websocket, {
            'type': 'validate_opencl',
            'kernel': "#bind layer !&dst float\n\n@KERNEL\n{\n"
                      "    @dst.set(1.0f);\n}\n",
        })
        assert r['success'], r
        assert r['data']['ok'], f"good kernel reported errors: {r['data']['errors']}"
        print(f"ok={r['data']['ok']}, warnings={r['data']['warnings']}")

        # Test 5: validate a BAD OpenCL kernel — expect compiler error
        print("\n--- Diagnostics 5: validate_opencl (bad kernel) ---")
        r = send(websocket, {
            'type': 'validate_opencl',
            'kernel': "#bind layer !&dst float\n\n@KERNEL\n{\n"
                      "    @dst.set(nonexistent_function(1.0f));\n}\n",
        })
        assert r['success'], r
        assert not r['data']['ok'], "bad kernel was not flagged"
        print(f"ok={r['data']['ok']}, errors={r['data']['errors'][0][:120]}...")

        # Test 6: temp nodes cleaned up
        print("\n--- Diagnostics 6: cleanup check ---")
        r = send(websocket, {
            'type': 'execute_python',
            'code': "result = ["
                    "n.path() for root in ('/obj', '/img') for n in "
                    "hou.node(root).children() if '__bridge' in n.name()]",
        })
        leftovers = (r.get('data') or {}).get('result')
        assert not leftovers, f"temp nodes left behind: {leftovers}"
        print("no temp nodes left behind")

        print("\n[ok] Diagnostics tests passed!")


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

    # New diagnostics commands (get_errors / validate_vex)
    test_diagnostics(port)

    # Uncomment to test batch commands:
    # test_batch_commands()
