from fastapi import APIRouter
from app.tasks.celery_app import celery_app

router = APIRouter()

@router.get("/{task_id}")
async def get_task_status(task_id: str):
    """
    Poll Celery task state by ID. Supports comma-separated task IDs for batch tracking.
    Returns standard Celery states: PENDING, STARTED, SUCCESS, FAILURE, PROGRESS
    """
    task_ids = [tid.strip() for tid in task_id.split(",") if tid.strip()]
    if not task_ids:
        return {"task_id": task_id, "status": "FAILURE", "error": "No valid task IDs provided"}
        
    if len(task_ids) == 1:
        task = celery_app.AsyncResult(task_ids[0])
        res_val = task.result if task.state == "SUCCESS" and isinstance(task.result, (dict, list, str, int, float, bool)) else (str(task.result) if task.state == "SUCCESS" else None)
        return {
            "task_id": task_ids[0],
            "status": task.state,
            "result": res_val,
            "error": str(task.info) if task.state == "FAILURE" else None,
            "meta": task.info if task.state == "PROGRESS" else None
        }

    # Multiple tasks tracking
    states = []
    progress_metas = []
    results = []
    errors = []
    
    for tid in task_ids:
        res = celery_app.AsyncResult(tid)
        states.append(res.state)
        if res.state == "SUCCESS":
            results.append(res.result)
        elif res.state == "FAILURE":
            errors.append(str(res.info))
        elif res.state == "PROGRESS" and isinstance(res.info, dict):
            progress_metas.append(res.info)

    # Check if all tasks are in terminal states (SUCCESS, FAILURE, REVOKED)
    terminal_states = {"SUCCESS", "FAILURE", "REVOKED"}
    if all(s in terminal_states for s in states):
        return {
            "task_id": task_id,
            "status": "SUCCESS",
            "result": {"completed": len(results), "failed": len(errors), "details": [str(r) for r in results]},
            "error": "; ".join(errors) if errors and not results else None,
            "meta": {"percent": 100, "message": "All scrapers completed"}
        }

    # If any task is in PROGRESS, report progress
    if progress_metas:
        avg_percent = sum(m.get("percent", 0) for m in progress_metas) // len(task_ids)
        latest_msg = progress_metas[-1].get("message", "Scrapers running...")
        return {
            "task_id": task_id,
            "status": "PROGRESS",
            "result": None,
            "error": None,
            "meta": {"percent": avg_percent, "message": f"Syncing: {latest_msg}"}
        }

    # Otherwise, they are PENDING or STARTED
    return {
        "task_id": task_id,
        "status": "STARTED",
        "result": None,
        "error": None,
        "meta": {"percent": 10, "message": f"Running {len(task_ids)} scrapers..."}
    }

