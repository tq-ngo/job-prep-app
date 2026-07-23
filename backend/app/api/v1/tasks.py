from fastapi import APIRouter
from app.tasks.celery_app import celery_app

router = APIRouter()

@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """
    Poll Celery task state by ID.
    Returns standard Celery states: PENDING, STARTED, SUCCESS, FAILURE
    """
    task = celery_app.AsyncResult(task_id)
    
    return {
        "task_id": task_id,
        "status": task.state,
        "result": str(task.result) if task.state == "SUCCESS" else None,
        "error": str(task.info) if task.state == "FAILURE" else None,
        "meta": task.info if task.state == "PROGRESS" else None
    }
