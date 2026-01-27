"""
Command Executor - Handles AI agent commands in Houdini session

Supports:
- Node operations (create, delete, set parameters)
- Scene queries (get selection, node info)
- File operations (save, load)
- Python code execution (with approval)
"""

from typing import Dict, Any, Optional, List
import traceback

try:
    import hou
except ImportError:
    hou = None


class CommandExecutor:
    """Executes commands from AI agent in Houdini session"""
    
    def __init__(self):
        self.session_state = {}  # Persistent state between commands
        self.last_selection: Optional[List] = None
        
    def execute(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a command and return result.
        
        Args:
            command: Dict with 'type' and command-specific parameters
            
        Returns:
            Result dict with 'success', 'data', and optional 'error'
        """
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
        
        # Get all parameters
        for parm in node.parms():
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
        
        try:
            exec(code, namespace)
            
            # Extract result if 'result' variable was set
            result = namespace.get('result', None)
            
            return {
                'success': True,
                'data': {'result': result}
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
