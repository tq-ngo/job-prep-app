import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient

from app.core.task_owner import record_task_owner


@pytest.mark.integration
async def test_get_task_status_single(client: AsyncClient, auth_headers, test_user):
    await record_task_owner(["task-uuid-1"], test_user.id)
    mock_result = MagicMock()
    mock_result.state = "SUCCESS"
    mock_result.result = {"synced": 42}
    mock_result.info = None

    with patch("app.tasks.celery_app.celery_app.AsyncResult", return_value=mock_result):
        res = await client.get(
            "/api/v1/tasks/task-uuid-1",
            cookies=auth_headers["cookies"],
        )
        assert res.status_code == 200
        data = res.json()
        assert data["task_id"] == "task-uuid-1"
        assert data["status"] == "SUCCESS"
        assert data["result"] == {"synced": 42}


@pytest.mark.integration
async def test_get_task_status_batch_comma_separated(
    client: AsyncClient, auth_headers, test_user
):
    await record_task_owner(["task-1", "task-2"], test_user.id)

    def mock_async_result(tid):
        res = MagicMock()
        res.state = "SUCCESS"
        res.result = {"item": tid}
        res.info = None
        return res

    with patch(
        "app.tasks.celery_app.celery_app.AsyncResult", side_effect=mock_async_result
    ):
        res = await client.get(
            "/api/v1/tasks/task-1,task-2",
            cookies=auth_headers["cookies"],
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "SUCCESS"
        assert data["result"]["completed"] == 2


@pytest.mark.integration
async def test_task_status_hidden_from_other_users(
    client: AsyncClient, auth_headers, test_user
):
    await record_task_owner(["mine"], test_user.id)
    await record_task_owner(["theirs"], test_user.id + 1)

    with patch("app.tasks.celery_app.celery_app.AsyncResult") as async_result:
        # Someone else's task, an unknown one, and a batch mixing in either
        # all look the same: not found, and the backend is never consulted.
        for path in ("theirs", "never-existed", "mine,theirs"):
            res = await client.get(f"/api/v1/tasks/{path}", cookies=auth_headers["cookies"])
            assert res.status_code == 404, path
        async_result.assert_not_called()


@pytest.mark.integration
async def test_task_status_caps_batch_size(client: AsyncClient, auth_headers, test_user):
    ids = [f"t{i}" for i in range(11)]
    await record_task_owner(ids, test_user.id)
    res = await client.get(f"/api/v1/tasks/{','.join(ids)}", cookies=auth_headers["cookies"])
    assert res.status_code == 422


@pytest.mark.integration
async def test_scrape_trigger_records_owner(client: AsyncClient, auth_headers, test_user):
    task = MagicMock(id="scrape-task-1")
    with patch("app.api.v1.jobs.scrape_github.delay", return_value=task):
        res = await client.post(
            "/api/v1/jobs/scrape/github",
            cookies=auth_headers["cookies"],
            headers=auth_headers["headers"],
        )
    assert res.status_code == 202

    done = MagicMock(state="SUCCESS", result={"synced": 1}, info=None)
    with patch("app.tasks.celery_app.celery_app.AsyncResult", return_value=done):
        res = await client.get("/api/v1/tasks/scrape-task-1", cookies=auth_headers["cookies"])
    assert res.status_code == 200
