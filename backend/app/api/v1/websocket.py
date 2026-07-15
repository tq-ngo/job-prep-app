import json
import logging
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """
    Manages active WebSocket connections.
    
    Used to push real-time job alerts to users when new jobs matching
    their skill profile are scraped.
    
    State:
    - active_connections: maps user_id → WebSocket
    - skill_filters: maps user_id → set of skills they care about
    
    In production with multiple backend instances, this state needs to
    live in Redis (pub/sub), not in-memory. This in-memory version works
    only when you have a single backend process.
    """
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.skill_filters: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str, skills: list[str]):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.skill_filters[user_id] = {s.lower() for s in skills}
        logger.info(f"WebSocket connected: user={user_id}, skills={skills}")
    
    def disconnect(self, user_id: str):
        self.active_connections.pop(user_id, None)
        self.skill_filters.pop(user_id, None)
        logger.info(f"WebSocket disconnected: user={user_id}")
    
    async def broadcast_new_job(self, job_data: dict):
        """
        Send a new job to all users whose skill filters match.
        
        Matching logic: if the job has ANY skill that the user is tracking,
        they get the alert. (OR match, not AND)
        """
        job_skills = {s.lower() for s in (job_data.get("skills") or [])}
        
        disconnected = []
        for user_id, websocket in self.active_connections.items():
            user_skills = self.skill_filters.get(user_id, set())
            
            # Does any job skill match any user skill?
            if user_skills & job_skills:  # Set intersection
                try:
                    await websocket.send_text(json.dumps({
                        "type": "new_job",
                        "data": job_data,
                    }))
                except Exception:
                    disconnected.append(user_id)
        
        # Clean up dead connections
        for user_id in disconnected:
            self.disconnect(user_id)


# Singleton — shared by all WebSocket endpoints
manager = ConnectionManager()


@router.websocket("/jobs/alerts")
async def job_alerts_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time job alerts.
    
    Client connects with skill filters:
    ws://localhost:8000/ws/jobs/alerts?skills=Python,FastAPI&user_id=123
    
    Server pushes new jobs that match the skills.
    """
    # Parse query parameters from the WebSocket URL
    user_id = websocket.query_params.get("user_id", "anonymous")
    skills_param = websocket.query_params.get("skills", "")
    skills = [s.strip() for s in skills_param.split(",") if s.strip()]
    
    await manager.connect(websocket, user_id, skills)
    
    try:
        while True:
            # Keep connection alive by waiting for messages
            # Client can send {"type": "ping"} to check connection
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif message.get("type") == "update_skills":
                # User updated their skill filters
                new_skills = message.get("skills", [])
                manager.skill_filters[user_id] = {s.lower() for s in new_skills}
                
    except WebSocketDisconnect:
        manager.disconnect(user_id)