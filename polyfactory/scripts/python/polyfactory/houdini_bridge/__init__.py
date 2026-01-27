"""
Houdini Bridge - AI Agent WebSocket Server

Enables AI agents in VS Code to control Houdini via WebSocket + MessagePack protocol.
Start server via shelf button, agent connects to localhost:9876 to execute commands.
"""

from .server import BridgeServer
from .message_handler import MessageHandler
from .commands import CommandExecutor
from .approval import ApprovalMode, ApprovalManager

__all__ = [
    'BridgeServer',
    'MessageHandler',
    'CommandExecutor',
    'ApprovalMode',
    'ApprovalManager',
]
