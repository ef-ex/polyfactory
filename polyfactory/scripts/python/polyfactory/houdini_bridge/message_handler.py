"""
Message Handler - Processes WebSocket messages with MessagePack

Protocol:
- Binary MessagePack encoding for efficiency
- Message structure: {'type': 'command', 'data': {...}}
- Response structure: {'success': bool, 'data': {...}, 'error': str}
"""

from typing import Dict, Any, Optional
import msgpack

from .commands import CommandExecutor
from .approval import ApprovalManager, ApprovalMode


class MessageHandler:
    """Handles incoming messages and routes to appropriate handlers"""
    
    def __init__(self):
        self.executor = CommandExecutor()
        self.approval = ApprovalManager()
        
    def handle_binary(self, data: bytes) -> bytes:
        """
        Handle binary MessagePack message.
        
        Args:
            data: MessagePack-encoded binary data
            
        Returns:
            MessagePack-encoded response
        """
        try:
            message = msgpack.unpackb(data, raw=False)
            response = self.handle_message(message)
            return msgpack.packb(response, use_bin_type=True)
        except Exception as e:
            error_response = {
                'success': False,
                'error': f"Message decoding error: {str(e)}"
            }
            return msgpack.packb(error_response, use_bin_type=True)
    
    def handle_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle decoded message and return response.
        
        Args:
            message: Decoded message dict
            
        Returns:
            Response dict
        """
        msg_type = message.get('type')
        
        if msg_type == 'command':
            return self._handle_command(message)
        elif msg_type == 'batch':
            return self._handle_batch(message)
        elif msg_type == 'set_approval_mode':
            return self._handle_set_approval_mode(message)
        elif msg_type == 'ping':
            return {'success': True, 'data': {'pong': True}}
        else:
            return {
                'success': False,
                'error': f"Unknown message type: {msg_type}"
            }
    
    def _handle_command(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle single command execution"""
        command = message.get('data', {})
        
        # Check if command needs approval
        is_destructive = self._is_destructive_command(command)
        
        if self.approval.requires_approval(
            command.get('type'),
            is_destructive
        ):
            preview = self._generate_preview(command)
            approved = self.approval.request_approval(
                command.get('type'),
                preview,
                is_destructive
            )
            
            if not approved:
                return {
                    'success': False,
                    'error': 'Command cancelled by user'
                }
        
        # Execute command
        return self.executor.execute(command)
    
    def _handle_batch(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Handle batch of commands"""
        commands = message.get('data', {}).get('commands', [])
        
        # Request approval for batch
        approvals = self.approval.approve_batch([
            {
                'type': cmd.get('type'),
                'description': self._generate_description(cmd),
                'preview': self._generate_preview(cmd),
                'is_destructive': self._is_destructive_command(cmd)
            }
            for cmd in commands
        ])
        
        # Execute approved commands
        results = []
        for command, approved in zip(commands, approvals):
            if approved:
                result = self.executor.execute(command)
            else:
                result = {
                    'success': False,
                    'error': 'Command cancelled by user'
                }
            results.append(result)
        
        return {
            'success': True,
            'data': {'results': results}
        }
    
    def _handle_set_approval_mode(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Change approval mode"""
        mode_str = message.get('data', {}).get('mode')
        
        try:
            mode = ApprovalMode(mode_str)
            self.approval.set_mode(mode)
            return {
                'success': True,
                'data': {'mode': mode.value}
            }
        except ValueError:
            return {
                'success': False,
                'error': f"Invalid approval mode: {mode_str}"
            }
    
    # Helper Methods
    
    def _is_destructive_command(self, command: Dict[str, Any]) -> bool:
        """Check if command modifies scene state"""
        destructive_types = {
            'create_node',
            'delete_node',
            'set_parameter',
            'execute_python',
            'load_scene'
        }
        return command.get('type') in destructive_types
    
    def _generate_description(self, command: Dict[str, Any]) -> str:
        """Generate human-readable command description"""
        cmd_type = command.get('type')
        
        if cmd_type == 'create_node':
            return f"Create {command.get('node_type')} node"
        elif cmd_type == 'delete_node':
            return f"Delete node: {command.get('node_path')}"
        elif cmd_type == 'set_parameter':
            return f"Set {command.get('parameter')} on {command.get('node_path')}"
        elif cmd_type == 'execute_python':
            return "Execute Python code"
        else:
            return cmd_type
    
    def _generate_preview(self, command: Dict[str, Any]) -> str:
        """Generate preview of command effects"""
        cmd_type = command.get('type')
        
        if cmd_type == 'create_node':
            parent = command.get('parent', '/obj')
            node_type = command.get('node_type')
            name = command.get('name', 'new_node')
            return f"Will create: {parent}/{name} ({node_type})"
            
        elif cmd_type == 'delete_node':
            return f"Will delete: {command.get('node_path')}"
            
        elif cmd_type == 'set_parameter':
            node = command.get('node_path')
            parm = command.get('parameter')
            value = command.get('value')
            return f"Will set {node}.{parm} = {value}"
            
        elif cmd_type == 'execute_python':
            code = command.get('code', '')
            lines = code.split('\n')
            preview = '\n'.join(lines[:5])
            if len(lines) > 5:
                preview += f"\n... ({len(lines)-5} more lines)"
            return f"Will execute:\n{preview}"
            
        else:
            return f"Will execute: {cmd_type}"
