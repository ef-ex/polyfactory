"""
Approval System - Safety controls for AI commands

Modes:
- AUTO: Execute read-only operations automatically
- PREVIEW: Show preview for all operations, require confirmation
- DESTRUCTIVE: Always confirm operations that modify scene
"""

from enum import Enum
from typing import Callable, Optional, Dict, Any

try:
    import hou
except ImportError:
    hou = None


class ApprovalMode(Enum):
    """Command approval modes for safety"""
    AUTO = "auto"  # Auto-execute read-only operations
    PREVIEW = "preview"  # Always preview before execution
    DESTRUCTIVE = "destructive"  # Confirm destructive operations only


class ApprovalManager:
    """Manages command approval flow with UI dialogs"""
    
    def __init__(self):
        self.mode = ApprovalMode.AUTO
        self._pending_callback: Optional[Callable] = None
        
    def set_mode(self, mode: ApprovalMode):
        """Change approval mode"""
        self.mode = mode
        
    def requires_approval(self, command_type: str, is_destructive: bool) -> bool:
        """Check if command requires user approval"""
        if self.mode == ApprovalMode.AUTO:
            return is_destructive
        elif self.mode == ApprovalMode.PREVIEW:
            return True
        elif self.mode == ApprovalMode.DESTRUCTIVE:
            return is_destructive
        return True
        
    def request_approval(self, command: str, preview: str, is_destructive: bool) -> bool:
        """
        Show approval dialog to user.
        
        Args:
            command: Command description
            preview: Preview of what will happen
            is_destructive: Whether operation modifies scene
            
        Returns:
            True if approved, False if denied
        """
        if not self.requires_approval(command, is_destructive):
            return True
            
        if not hou:
            print(f"[Bridge] Would request approval for: {command}")
            return True
            
        # Build dialog message
        severity = hou.severityType.Warning if is_destructive else hou.severityType.Message
        message = f"AI Agent Request:\n\n{command}\n\n{preview}\n\nExecute this operation?"
        
        result = hou.ui.displayMessage(
            message,
            buttons=("Execute", "Cancel"),
            severity=severity,
            default_choice=1,  # Default to Cancel for safety
            close_choice=1,
            help="AI agent is requesting to perform this operation. Review carefully.",
            title="Houdini Bridge - Approval Required"
        )
        
        return result == 0  # 0 = Execute, 1 = Cancel
        
    def approve_batch(self, commands: list[Dict[str, Any]]) -> list[bool]:
        """
        Request approval for batch of commands.
        
        Returns list of approval decisions.
        """
        if not hou:
            return [True] * len(commands)
            
        # Build preview of all commands
        preview_text = "\n".join([
            f"{i+1}. {cmd.get('description', cmd['type'])}"
            for i, cmd in enumerate(commands)
        ])
        
        message = f"AI Agent Batch Request ({len(commands)} operations):\n\n{preview_text}\n\nExecute all?"
        
        result = hou.ui.displayMessage(
            message,
            buttons=("Execute All", "Review Each", "Cancel All"),
            severity=hou.severityType.Message,
            default_choice=1,
            close_choice=2,
            title="Houdini Bridge - Batch Approval"
        )
        
        if result == 0:  # Execute All
            return [True] * len(commands)
        elif result == 2:  # Cancel All
            return [False] * len(commands)
        else:  # Review Each
            approvals = []
            for cmd in commands:
                approved = self.request_approval(
                    cmd.get('description', cmd['type']),
                    cmd.get('preview', 'No preview available'),
                    cmd.get('is_destructive', False)
                )
                approvals.append(approved)
                if not approved:
                    # User cancelled, skip remaining
                    approvals.extend([False] * (len(commands) - len(approvals)))
                    break
            return approvals
