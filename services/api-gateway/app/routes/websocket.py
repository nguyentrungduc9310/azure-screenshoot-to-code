"""
WebSocket Routes
Real-time streaming for code and image generation
"""
import json
import asyncio
from typing import Dict, Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends
from fastapi.websockets import WebSocketState

from shared.monitoring.structured_logger import StructuredLogger
from shared.monitoring.correlation import set_correlation_id

router = APIRouter()

class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_connections: Dict[str, set] = {}  # user_id -> connection_ids
    
    async def connect(self, websocket: WebSocket, connection_id: str, user_id: Optional[str] = None):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        
        if user_id:
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
        
        await self.send_message(connection_id, {
            "type": "connection_established",
            "connection_id": connection_id,
            "message": "WebSocket connection established"
        })
    
    def disconnect(self, connection_id: str, user_id: Optional[str] = None):
        """Remove a WebSocket connection"""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        
        if user_id and user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
    
    async def send_message(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send message to a specific connection"""
        if connection_id not in self.active_connections:
            return False
        
        websocket = self.active_connections[connection_id]
        if websocket.client_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_json(message)
                return True
            except Exception:
                # Connection closed, remove it
                self.disconnect(connection_id)
                return False
        return False
    
    async def send_to_user(self, user_id: str, message: Dict[str, Any]) -> int:
        """Send message to all connections for a user"""
        if user_id not in self.user_connections:
            return 0
        
        sent_count = 0
        connection_ids = list(self.user_connections[user_id])
        
        for connection_id in connection_ids:
            if await self.send_message(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def broadcast(self, message: Dict[str, Any]) -> int:
        """Broadcast message to all connections"""
        sent_count = 0
        connection_ids = list(self.active_connections.keys())
        
        for connection_id in connection_ids:
            if await self.send_message(connection_id, message):
                sent_count += 1
        
        return sent_count

# Global connection manager
manager = ConnectionManager()

def get_logger() -> StructuredLogger:
    """Get logger instance"""
    return StructuredLogger(
        service_name="api-gateway",
        environment="development",  # This should come from settings
        log_level="INFO"
    )

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_id: str = Query(..., description="Unique connection identifier"),
    user_id: Optional[str] = Query(None, description="User ID for authentication"),
    logger: StructuredLogger = Depends(get_logger)
):
    """WebSocket endpoint for real-time communication"""
    
    # Set correlation ID for this connection
    set_correlation_id(connection_id)
    
    logger.info("WebSocket connection attempt",
                connection_id=connection_id,
                user_id=user_id,
                client_ip=websocket.client.host if websocket.client else "unknown")
    
    try:
        # Accept connection
        await manager.connect(websocket, connection_id, user_id)
        
        logger.info("WebSocket connection established",
                   connection_id=connection_id,
                   user_id=user_id)
        
        # Connection loop
        while True:
            try:
                # Receive message from client
                message = await websocket.receive_json()
                
                logger.debug("WebSocket message received",
                           connection_id=connection_id,
                           message_type=message.get("type"),
                           user_id=user_id)
                
                # Handle different message types
                await handle_websocket_message(websocket, connection_id, user_id, message, logger)
                
            except WebSocketDisconnect:
                logger.info("WebSocket client disconnected",
                           connection_id=connection_id,
                           user_id=user_id)
                break
            except json.JSONDecodeError:
                await manager.send_message(connection_id, {
                    "type": "error",
                    "error": "Invalid JSON message"
                })
            except Exception as e:
                logger.error("Error handling WebSocket message",
                           connection_id=connection_id,
                           error=str(e),
                           user_id=user_id)
                
                await manager.send_message(connection_id, {
                    "type": "error",
                    "error": "Message processing failed"
                })
    
    except Exception as e:
        logger.error("WebSocket connection error",
                    connection_id=connection_id,
                    error=str(e),
                    user_id=user_id)
    
    finally:
        # Clean up connection
        manager.disconnect(connection_id, user_id)
        logger.info("WebSocket connection closed",
                   connection_id=connection_id,
                   user_id=user_id)

async def handle_websocket_message(
    websocket: WebSocket,
    connection_id: str,
    user_id: Optional[str],
    message: Dict[str, Any],
    logger: StructuredLogger
):
    """Handle incoming WebSocket messages"""
    
    message_type = message.get("type")
    
    if message_type == "ping":
        # Respond to ping with pong
        await manager.send_message(connection_id, {
            "type": "pong",
            "timestamp": logger._get_timestamp()
        })
    
    elif message_type == "subscribe_generation":
        # Subscribe to generation updates
        generation_id = message.get("generation_id")
        if generation_id:
            # Store subscription (in a real implementation, you'd use Redis or similar)
            await manager.send_message(connection_id, {
                "type": "subscription_confirmed",
                "generation_id": generation_id,
                "message": f"Subscribed to generation {generation_id}"
            })
        else:
            await manager.send_message(connection_id, {
                "type": "error",
                "error": "generation_id required for subscription"
            })
    
    elif message_type == "unsubscribe_generation":
        # Unsubscribe from generation updates
        generation_id = message.get("generation_id")
        if generation_id:
            await manager.send_message(connection_id, {
                "type": "subscription_cancelled",
                "generation_id": generation_id,
                "message": f"Unsubscribed from generation {generation_id}"
            })
    
    elif message_type == "stream_code_generation":
        # Start streaming code generation
        await handle_streaming_code_generation(connection_id, user_id, message, logger)
    
    elif message_type == "stream_image_generation":
        # Start streaming image generation updates
        await handle_streaming_image_generation(connection_id, user_id, message, logger)
    
    else:
        await manager.send_message(connection_id, {
            "type": "error",
            "error": f"Unknown message type: {message_type}"
        })

async def handle_streaming_code_generation(
    connection_id: str,
    user_id: Optional[str],
    message: Dict[str, Any],
    logger: StructuredLogger
):
    """Handle streaming code generation request"""
    
    try:
        # Extract generation parameters
        generation_params = message.get("params", {})
        
        # Send generation started message
        await manager.send_message(connection_id, {
            "type": "generation_started",
            "generation_type": "code",
            "status": "processing",
            "message": "Code generation started"
        })
        
        # Simulate streaming progress updates
        # In real implementation, this would integrate with the code generation service
        for progress in [25, 50, 75, 90]:
            await asyncio.sleep(1)  # Simulate processing time
            
            await manager.send_message(connection_id, {
                "type": "generation_progress",
                "generation_type": "code",
                "progress": progress,
                "status": "processing",
                "message": f"Code generation {progress}% complete"
            })
        
        # Send completion message
        await manager.send_message(connection_id, {
            "type": "generation_completed",
            "generation_type": "code",
            "status": "completed",
            "result": {
                "id": "gen_123",
                "code": "<html><!-- Generated code would be here --></html>",
                "generation_time_ms": 5000
            }
        })
        
        logger.info("Streaming code generation completed",
                   connection_id=connection_id,
                   user_id=user_id)
    
    except Exception as e:
        logger.error("Error in streaming code generation",
                    connection_id=connection_id,
                    error=str(e))
        
        await manager.send_message(connection_id, {
            "type": "generation_error",
            "generation_type": "code",
            "status": "failed",
            "error": "Code generation failed"
        })

async def handle_streaming_image_generation(
    connection_id: str,
    user_id: Optional[str],
    message: Dict[str, Any],
    logger: StructuredLogger
):
    """Handle streaming image generation request"""
    
    try:
        # Extract generation parameters
        generation_params = message.get("params", {})
        
        # Send generation started message
        await manager.send_message(connection_id, {
            "type": "generation_started",
            "generation_type": "image",
            "status": "processing",
            "message": "Image generation started"
        })
        
        # Simulate image generation progress
        stages = [
            {"progress": 20, "message": "Analyzing prompt"},
            {"progress": 40, "message": "Generating image"},
            {"progress": 70, "message": "Refining details"},
            {"progress": 90, "message": "Finalizing image"}
        ]
        
        for stage in stages:
            await asyncio.sleep(1.5)  # Simulate processing time
            
            await manager.send_message(connection_id, {
                "type": "generation_progress",
                "generation_type": "image",
                "progress": stage["progress"],
                "status": "processing",
                "message": stage["message"]
            })
        
        # Send completion message
        await manager.send_message(connection_id, {
            "type": "generation_completed",
            "generation_type": "image",
            "status": "completed",
            "result": {
                "id": "img_456",
                "images": [
                    {
                        "url": "https://example.com/generated-image.jpg",
                        "size": "1024x1024"
                    }
                ],
                "generation_time_ms": 8000
            }
        })
        
        logger.info("Streaming image generation completed",
                   connection_id=connection_id,
                   user_id=user_id)
    
    except Exception as e:
        logger.error("Error in streaming image generation",
                    connection_id=connection_id,
                    error=str(e))
        
        await manager.send_message(connection_id, {
            "type": "generation_error",
            "generation_type": "image",
            "status": "failed",
            "error": "Image generation failed"
        })

@router.get("/ws/connections")
async def get_active_connections():
    """Get information about active WebSocket connections (admin endpoint)"""
    return {
        "active_connections": len(manager.active_connections),
        "users_connected": len(manager.user_connections),
        "connection_details": {
            conn_id: {"state": "connected"}
            for conn_id in manager.active_connections.keys()
        }
    }