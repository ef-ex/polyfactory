"""
Command Executor - Handles AI agent commands in Houdini session

Supports:
- Node operations (create, delete, set parameters)
- Scene queries (get selection, node info)
- File operations (save, load)
- Python code execution (with approval)
"""

from typing import Dict, Any, Optional, List
import threading
import traceback

try:
    import hou
except ImportError:
    hou = None

try:
    import hdefereval  # Houdini-only: marshal work onto the main thread
except ImportError:
    hdefereval = None


class CommandExecutor:
    """Executes commands from AI agent in Houdini session"""
    
    def __init__(self):
        self.session_state = {}  # Persistent state between commands
        self.last_selection: Optional[List] = None
        
    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command on Houdini's MAIN thread and return the result.

        The bridge handles connections on a background socket thread, but the HOM
        API is not thread-safe: touching `hou` from a background thread can crash
        Houdini intermittently (cooks, UI, GL). We marshal every command onto the
        main thread via hdefereval so callers don't have to.

        `execute_python` is the one exception — it stays on the calling thread.
        It is the escape hatch where the caller owns thread-safety and may marshal
        GL/viewport work to the main thread itself (see render_view). Marshaling it
        here would deadlock that executeDeferred()+wait() pattern.
        """
        cmd_type = command.get('type')

        if (hou is not None and hdefereval is not None
                and cmd_type != 'execute_python'
                and threading.current_thread() is not threading.main_thread()):
            try:
                return hdefereval.executeInMainThreadWithResult(
                    self._execute_impl, command)
            except Exception as e:
                return {
                    'success': False,
                    'error': f"Main-thread execution failed: {e}",
                    'traceback': traceback.format_exc(),
                }
        return self._execute_impl(command)

    def _execute_impl(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Route a command to its handler. Runs on the main thread (see execute)."""
        cmd_type = command.get('type')

        try:
            # Route to appropriate handler
            if cmd_type == 'create_node':
                return self._create_node(command)
            elif cmd_type == 'delete_node':
                return self._delete_node(command)
            elif cmd_type == 'set_parameter':
                return self._set_parameter(command)
            elif cmd_type == 'get_parameter':
                return self._get_parameter(command)
            elif cmd_type == 'get_selection':
                return self._get_selection(command)
            elif cmd_type == 'select_nodes':
                return self._select_nodes(command)
            elif cmd_type == 'get_node_info':
                return self._get_node_info(command)
            elif cmd_type == 'execute_python':
                return self._execute_python(command)
            elif cmd_type == 'read_network':
                return self._read_network(command)
            elif cmd_type == 'write_network':
                return self._write_network(command)
            elif cmd_type == 'get_errors':
                return self._get_errors(command)
            elif cmd_type == 'validate_vex':
                return self._validate_vex(command)
            elif cmd_type == 'validate_opencl':
                return self._validate_opencl(command)
            elif cmd_type == 'save_scene':
                return self._save_scene(command)
            elif cmd_type == 'load_scene':
                return self._load_scene(command)
            elif cmd_type == 'get_session_state':
                return self._get_session_state(command)
            elif cmd_type == 'set_session_state':
                return self._set_session_state(command)
            else:
                return {
                    'success': False,
                    'error': f"Unknown command type: {cmd_type}"
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    # Node Operations
    
    def _create_node(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new node"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        parent_path = command.get('parent', '/obj')
        node_type = command.get('node_type')
        name = command.get('name')
        
        parent = hou.node(parent_path)
        if not parent:
            return {'success': False, 'error': f"Parent node not found: {parent_path}"}
            
        node = parent.createNode(node_type, node_name=name)
        
        # Set parameters if provided
        parameters = command.get('parameters', {})
        for parm_name, value in parameters.items():
            parm = node.parm(parm_name)
            if parm:
                parm.set(value)
                
        return {
            'success': True,
            'data': {
                'node_path': node.path(),
                'node_type': node.type().name(),
                'name': node.name()
            }
        }
    
    def _delete_node(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a node"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        node_path = command.get('node_path')
        node = hou.node(node_path)
        
        if not node:
            return {'success': False, 'error': f"Node not found: {node_path}"}
            
        node.destroy()
        
        return {
            'success': True,
            'data': {'deleted': node_path}
        }
    
    def _set_parameter(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Set node parameter value"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        node_path = command.get('node_path')
        parm_name = command.get('parameter')
        value = command.get('value')
        
        node = hou.node(node_path)
        if not node:
            return {'success': False, 'error': f"Node not found: {node_path}"}
            
        parm = node.parm(parm_name)
        if not parm:
            return {'success': False, 'error': f"Parameter not found: {parm_name}"}
            
        parm.set(value)
        
        return {
            'success': True,
            'data': {
                'node_path': node_path,
                'parameter': parm_name,
                'value': value
            }
        }
    
    def _get_parameter(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Get node parameter value"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        node_path = command.get('node_path')
        parm_name = command.get('parameter')
        
        node = hou.node(node_path)
        if not node:
            return {'success': False, 'error': f"Node not found: {node_path}"}
            
        parm = node.parm(parm_name)
        if not parm:
            return {'success': False, 'error': f"Parameter not found: {parm_name}"}
            
        return {
            'success': True,
            'data': {
                'node_path': node_path,
                'parameter': parm_name,
                'value': parm.eval()
            }
        }
    
    # Selection Operations
    
    def _get_selection(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Get current node selection"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        selected = hou.selectedNodes()
        self.last_selection = selected
        
        return {
            'success': True,
            'data': {
                'selection': [node.path() for node in selected],
                'count': len(selected)
            }
        }
    
    def _select_nodes(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Select nodes by path"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        node_paths = command.get('nodes', [])
        nodes = []
        
        for path in node_paths:
            node = hou.node(path)
            if node:
                nodes.append(node)
                
        # Clear current selection and select new nodes
        for node in hou.selectedNodes():
            node.setSelected(False)
            
        for node in nodes:
            node.setSelected(True)
            
        return {
            'success': True,
            'data': {
                'selected': [node.path() for node in nodes],
                'count': len(nodes)
            }
        }
    
    def _get_node_info(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Get detailed node information"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        node_path = command.get('node_path')
        node = hou.node(node_path)
        
        if not node:
            return {'success': False, 'error': f"Node not found: {node_path}"}
            
        # Gather node info
        info = {
            'path': node.path(),
            'name': node.name(),
            'type': node.type().name(),
            'type_description': node.type().description(),
            'position': list(node.position()),
            'parameters': {}
        }
        
        # Get parameters (optionally only those changed from their defaults —
        # far less output on large HDAs).
        non_default_only = command.get('non_default_only', False)
        for parm in node.parms():
            if non_default_only and parm.isAtDefault():
                continue
            info['parameters'][parm.name()] = {
                'value': parm.eval(),
                'label': parm.description(),
                'type': parm.parmTemplate().type().name()
            }
            
        return {
            'success': True,
            'data': info
        }
    
    # Python Execution
    
    def _execute_python(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute arbitrary Python code (requires approval)"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        code = command.get('code')
        
        # Create execution namespace with hou module
        namespace = {
            'hou': hou,
            'session_state': self.session_state,
            '__builtins__': __builtins__
        }
        
        # Capture stdout for print statements
        import io
        import contextlib
        stdout_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, namespace)

            # Extract result if 'result' variable was set
            result = namespace.get('result', None)

            # Get captured output
            output = stdout_capture.getvalue()

            return {
                'success': True,
                'data': {
                    'result': result,
                    'output': output.strip() if output else None
                }
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    # File Operations
    
    def _save_scene(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Save current scene"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        filepath = command.get('filepath')
        
        if filepath:
            hou.hipFile.save(file_name=filepath)
        else:
            hou.hipFile.save()
            
        return {
            'success': True,
            'data': {'filepath': hou.hipFile.path()}
        }
    
    def _load_scene(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Load a scene file"""
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}
            
        filepath = command.get('filepath')
        
        hou.hipFile.load(filepath)
        
        return {
            'success': True,
            'data': {'filepath': hou.hipFile.path()}
        }
    
    # Session State
    
    def _get_session_state(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Get session state variables"""
        key = command.get('key')
        
        if key:
            value = self.session_state.get(key)
            return {
                'success': True,
                'data': {'key': key, 'value': value}
            }
        else:
            return {
                'success': True,
                'data': {'state': self.session_state}
            }
    
    def _set_session_state(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Set session state variables"""
        key = command.get('key')
        value = command.get('value')
        
        self.session_state[key] = value
        
        return {
            'success': True,
            'data': {'key': key, 'value': value}
        }

    # Recipe API (read/write full networks)

    def _read_network(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Read a network as Houdini Recipe data using hou.data API.

        If parent_path is given, returns all children of that node.
        If use_selection=True or no parent_path, returns selected nodes.
        brief=True (default) omits default parm values for compact AI output.
        """
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}

        parent_path: Optional[str] = command.get('parent_path')
        use_selection: bool = command.get('use_selection', False)
        brief: bool = command.get('brief', True)

        if use_selection or not parent_path:
            nodes = hou.selectedNodes()
            if not nodes:
                return {
                    'success': False,
                    'error': 'No nodes selected and no parent_path provided'
                }
            data = hou.data.nodesAsData(nodes, brief=brief)
            source = 'selection'
        else:
            parent = hou.node(parent_path)
            if not parent:
                return {'success': False, 'error': f"Node not found: {parent_path}"}
            data = parent.childrenAsData(brief=brief)
            source = parent_path

        return {
            'success': True,
            'data': {
                'recipe': data,
                'source': source,
                'node_count': len(data)
            }
        }

    def _write_network(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Create a network from Houdini Recipe data using hou.data.createItemsFromData.

        recipe_data must be a Network Items dict (same format as returned by _read_network).
        """
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}

        parent_path: str = command.get('parent_path', '/obj')
        recipe_data: Optional[Dict[str, Any]] = command.get('recipe_data')

        if not recipe_data:
            return {'success': False, 'error': 'recipe_data is required'}

        parent = hou.node(parent_path)
        if not parent:
            return {'success': False, 'error': f"Parent node not found: {parent_path}"}

        created = hou.data.createItemsFromData(parent, recipe_data)

        # createItemsFromData returns {name: hou.NetworkItem}; extract paths
        created_paths: Dict[str, str] = {}
        for name, item in created.items():
            if hasattr(item, 'path'):
                created_paths[name] = item.path()

        return {
            'success': True,
            'data': {
                'created': created_paths,
                'count': len(created_paths),
                'parent_path': parent_path
            }
        }

    # Diagnostics

    def _get_errors(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Collect cook errors/warnings from nodes.

        node_path given -> that node's subtree (recurse=True by default).
        No node_path -> sweep the common context roots. Only nodes that HAVE
        errors/warnings are returned, so output stays small on healthy scenes.
        """
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}

        node_path = command.get('node_path')
        recurse = command.get('recurse', True)
        cook_first = command.get('cook_first', False)
        include_warnings = command.get('include_warnings', True)
        max_results = command.get('max_results', 100)

        if node_path:
            root = hou.node(node_path)
            if not root:
                return {'success': False, 'error': f"Node not found: {node_path}"}
            if cook_first:
                try:
                    root.cook(force=True)
                except Exception:
                    pass  # the error we're after lands on the node(s)
            roots = [root]
        else:
            roots = [n for n in (hou.node(p) for p in
                     ('/obj', '/stage', '/mat', '/out', '/img', '/tasks')) if n]

        findings = []
        visited = 0
        truncated = False
        stack = list(roots)
        while stack:
            node = stack.pop()
            visited += 1
            if visited > 20000:
                truncated = True
                break
            errors = list(node.errors())
            warnings = list(node.warnings()) if include_warnings else []
            if errors or warnings:
                findings.append({
                    'path': node.path(),
                    'type': node.type().name(),
                    'errors': errors,
                    'warnings': warnings,
                })
                if len(findings) >= max_results:
                    truncated = True
                    break
            if recurse:
                stack.extend(node.children())

        return {
            'success': True,
            'data': {
                'findings': findings,
                'nodes_with_issues': len(findings),
                'nodes_scanned': visited,
                'truncated': truncated,
            }
        }

    def _validate_vex(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Compile a VEX snippet in a throwaway attribwrangle and return the
        real compiler errors/warnings. Temp nodes are undo-disabled and
        destroyed afterwards, so the scene is left untouched.
        """
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}

        snippet = command.get('snippet')
        if not snippet:
            return {'success': False, 'error': 'snippet is required'}
        run_over = str(command.get('run_over', 'points'))
        input_node_path = command.get('input_node')

        with hou.undos.disabler():
            container = None
            wrangle = None
            try:
                if input_node_path:
                    src = hou.node(input_node_path)
                    if not src:
                        return {'success': False,
                                'error': f"Input node not found: {input_node_path}"}
                    if not isinstance(src, hou.SopNode):
                        return {'success': False,
                                'error': f"input_node must be a SOP node: {input_node_path}"}
                    wrangle = src.parent().createNode(
                        'attribwrangle', '__bridge_vex_validate')
                    wrangle.setInput(0, src)
                else:
                    # Small grid so the snippet runs over real elements.
                    container = hou.node('/obj').createNode(
                        'geo', '__bridge_vex_validate')
                    grid = container.createNode('grid')
                    grid.parm('rows').set(3)
                    grid.parm('cols').set(3)
                    wrangle = container.createNode('attribwrangle')
                    wrangle.setInput(0, grid)

                # Resolve the Run Over menu token from the friendly name by
                # prefix-matching the node's real menu (tokens vary across
                # Houdini versions).
                class_parm = wrangle.parm('class')
                tokens = list(class_parm.menuItems())
                prefix = run_over.lower()[:4]
                token = next(
                    (t for t in tokens if t.lower().startswith(prefix)), None)
                if token:
                    class_parm.set(token)

                wrangle.parm('snippet').set(snippet)
                try:
                    wrangle.cook(force=True)
                except Exception:
                    pass  # compile errors are read off the node below

                errors = list(wrangle.errors())
                warnings = list(wrangle.warnings())
                data = {
                    'ok': not errors,
                    'errors': errors,
                    'warnings': warnings,
                    'run_over': token if token else
                        f"unresolved '{run_over}' - node default used (menu: {tokens})",
                }
                if not errors:
                    geo = wrangle.geometry()
                    if geo is not None:
                        data['result_geometry'] = {
                            'points': geo.intrinsicValue('pointcount'),
                            'prims': geo.intrinsicValue('primitivecount'),
                            'point_attribs': [a.name() for a in geo.pointAttribs()],
                            'prim_attribs': [a.name() for a in geo.primAttribs()],
                            'detail_attribs': [a.name() for a in geo.globalAttribs()],
                        }
                return {'success': True, 'data': data}
            finally:
                try:
                    if container is not None:
                        container.destroy()   # takes the wrangle with it
                    elif wrangle is not None:
                        wrangle.destroy()
                except Exception as e:
                    print(f"[Bridge] validate_vex cleanup failed: {e}")

    def _validate_opencl(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Compile an OpenCL (Copernicus COP) kernel in a throwaway opencl node
        and return the real compiler/binding errors. Temp nodes are
        undo-disabled and destroyed afterwards, so the scene is left untouched.

        The kernel must be complete kernelcode including its #bind directives
        and a writable output bind (e.g. '#bind layer !&dst float') — without
        one the node fails at binding before the compiler even runs.
        """
        if not hou:
            return {'success': False, 'error': 'Houdini not available'}

        kernel = command.get('kernel')
        if not kernel:
            return {'success': False, 'error': 'kernel is required'}
        input_node_path = command.get('input_node')

        with hou.undos.disabler():
            container = None
            ocl = None
            try:
                if input_node_path:
                    src = hou.node(input_node_path)
                    if not src:
                        return {'success': False,
                                'error': f"Input node not found: {input_node_path}"}
                    if src.type().category().name() != 'Cop':
                        return {'success': False,
                                'error': "input_node must be a COP (Copernicus) "
                                         f"node: {input_node_path}"}
                    ocl = src.parent().createNode(
                        'opencl', '__bridge_ocl_validate')
                    ocl.setInput(0, src)
                else:
                    parent = hou.node('/img') or hou.node('/obj')
                    if parent is None:
                        return {'success': False,
                                'error': 'No /img or /obj root to build in'}
                    container = parent.createNode(
                        'copnet', '__bridge_ocl_validate')
                    ocl = container.createNode('opencl')

                ocl.parm('kernelcode').set(kernel)
                try:
                    ocl.cook(force=True)
                except Exception:
                    pass  # compile/binding errors are read off the node below

                errors = list(ocl.errors())
                warnings = list(ocl.warnings())
                return {
                    'success': True,
                    'data': {
                        'ok': not errors,
                        'errors': errors,
                        'warnings': warnings,
                    }
                }
            finally:
                try:
                    if container is not None:
                        container.destroy()   # takes the opencl node with it
                    elif ocl is not None:
                        ocl.destroy()
                except Exception as e:
                    print(f"[Bridge] validate_opencl cleanup failed: {e}")
