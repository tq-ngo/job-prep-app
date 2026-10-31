import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient


@pytest.mark.integration
async def test_get_task_status_single(client: AsyncClient, auth_headers):
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
    client: AsyncClient, auth_headers
):
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

