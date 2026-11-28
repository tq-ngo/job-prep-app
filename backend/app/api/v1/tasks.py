import asyncio
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.v1.auth import get_current_user
from app.core.rate_limit import limiter
from app.core.task_owner import owns_all
from app.models.users import User
from app.tasks.celery_app import celery_app

router = APIRouter()

MAX_TASK_IDS = 10


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    meta: Optional[Any] = None


@router.get("/{task_id}", response_model=TaskStatusResponse)
@limiter.limit("120/minute")
async def get_task_status(
    request: Request,
    response: Response,
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Poll Celery task state by ID. Supports comma-separated task IDs for batch tracking.
    Only the user who started the task(s) may poll them; anyone else gets 404.
    """
    response.headers["Cache-Control"] = "private, no-store"
    task_ids = [tid.strip() for tid in task_id.split(",") if tid.strip()]
    if not task_ids:
        raise HTTPException(status_code=422, detail="No valid task IDs provided")
    if len(task_ids) > MAX_TASK_IDS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_TASK_IDS} task IDs per request")
    if not await owns_all(task_ids, current_user.id):
        raise HTTPException(status_code=404, detail="Task not found")

    return await asyncio.to_thread(_task_status, task_id, task_ids)


def _task_status(task_id: str, task_ids: List[str]) -> dict:
    if len(task_ids) == 1:
        task = celery_app.AsyncResult(task_ids[0])
        res_val = (
            task.result
            if task.state == "SUCCESS"
            and isinstance(task.result, (dict, list, str, int, float, bool))
            else (str(task.result) if task.state == "SUCCESS" else None)
        )
        return {
            "task_id": task_ids[0],
            "status": task.state,
            "result": res_val,
            "error": "Task execution failed" if task.state == "FAILURE" else None,
            "meta": task.info if task.state == "PROGRESS" and isinstance(task.info, dict) else None,
        }

    states = []
    progress_metas = []
    results = []
    failed_count = 0
    revoked_count = 0

    for tid in task_ids:
        res = celery_app.AsyncResult(tid)
        states.append(res.state)
        if res.state == "SUCCESS":
            results.append(res.result)
        elif res.state == "FAILURE":
            failed_count += 1
        elif res.state == "REVOKED":
            revoked_count += 1
        elif res.state == "PROGRESS" and isinstance(res.info, dict):
            progress_metas.append(res.info)

    terminal_states = {"SUCCESS", "FAILURE", "REVOKED"}
    if all(s in terminal_states for s in states):
        if failed_count == len(task_ids):
            overall_status = "FAILURE"
            err_msg = "All tasks failed"
        elif revoked_count == len(task_ids):
            overall_status = "REVOKED"
            err_msg = "All tasks were revoked"
        elif failed_count > 0 or revoked_count > 0:
            overall_status = "PARTIAL_FAILURE"
            err_msg = f"{failed_count} failed, {revoked_count} revoked"
        else:
            overall_status = "SUCCESS"
            err_msg = None

        return {
            "task_id": task_id,
            "status": overall_status,
            "result": {
                "completed": len(results),
                "failed": failed_count,
                "revoked": revoked_count,
                "details": [str(r) for r in results],
            },
            "error": err_msg,
            "meta": {"percent": 100, "message": "All scrapers finished"},
        }

    if progress_metas:
        avg_percent = sum(m.get("percent", 0) for m in progress_metas) // len(task_ids)
        latest_msg = progress_metas[-1].get("message", "Scrapers running...")
        return {
            "task_id": task_id,
            "status": "PROGRESS",
            "result": None,
            "error": None,
            "meta": {"percent": avg_percent, "message": f"Syncing: {latest_msg}"},
        }

    return {
        "task_id": task_id,
        "status": "STARTED",
        "result": None,
        "error": None,
        "meta": {"percent": 10, "message": f"Running {len(task_ids)} scrapers..."},
    }
