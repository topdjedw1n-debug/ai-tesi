"""
WebSocket manager for real-time progress updates
"""
import logging
import uuid
from contextvars import ContextVar
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.exceptions import WebSocketException

logger = logging.getLogger(__name__)

# Isolated user context for multi-user WebSocket connections
user_context: ContextVar[dict[str, Any]] = ContextVar('user_context', default={})


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: dict[int, list[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: int) -> None:
        """
        Accept a new WebSocket connection for a user.
        
        Args:
            websocket: WebSocket connection to accept
            user_id: ID of the user making the connection
        """
        try:
            await websocket.accept()
            
            # Add connection to user's connections list
            if user_id not in self.active_connections:
                self.active_connections[user_id] = []
            self.active_connections[user_id].append(websocket)
            
            # Set isolated context for this user
            user_context.set({
                "user_id": user_id,
                "session_id": str(uuid.uuid4())
            })
            
            logger.info(f"WebSocket connected for user {user_id}")
        except WebSocketException as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise
    
    async def disconnect(self, websocket: WebSocket, user_id: int) -> None:
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
            user_id: ID of the user
        """
        if user_id in self.active_connections:
            try:
                self.active_connections[user_id].remove(websocket)
            except ValueError:
                pass  # Connection already removed
            
            # Clean up empty lists
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_progress(self, user_id: int, message: dict[str, Any]) -> None:
        """
        Send progress update to all connections for a user.
        
        Args:
            user_id: ID of the user to send to
            message: Message to send (will be sent as JSON)
        """
        if user_id not in self.active_connections:
            logger.debug(f"No active connections for user {user_id}")
            return
        
        # Send to all active connections for this user
        disconnected = []
        for connection in self.active_connections[user_id]:
            try:
                await connection.send_json(message)
            except (WebSocketDisconnect, WebSocketException) as e:
                logger.warning(f"Failed to send progress update: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for connection in disconnected:
            await self.disconnect(connection, user_id)
    
    async def broadcast(self, message: dict[str, Any]) -> None:
        """
        Broadcast message to all connected users.
        
        Args:
            message: Message to broadcast
        """
        all_users = list(self.active_connections.keys())
        for user_id in all_users:
            await self.send_progress(user_id, message)
    
    def get_active_connections_count(self) -> int:
        """
        Get total number of active WebSocket connections.
        
        Returns:
            Total number of active connections
        """
        return sum(len(connections) for connections in self.active_connections.values())


# Global connection manager instance
manager = ConnectionManager()

