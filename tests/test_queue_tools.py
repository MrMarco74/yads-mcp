"""Covers the Queue & Scan Control tool group against the real (in-process)
YADS app -- see conftest.py for how yads_mcp.client is patched."""


def test_queue_status_tool_returns_shape():
    from yads_mcp.server import queue_status
    result = queue_status()
    for key in ("queue_active", "queued_count", "running_count"):
        assert key in result


def test_queue_pause_and_resume_tools():
    from yads_mcp.server import queue_pause, queue_resume

    result = queue_pause()
    assert result["queue_active"] is False

    result = queue_resume()
    assert result["queue_active"] is True


def test_queue_cancel_task_tool_not_found():
    from yads_mcp.server import queue_cancel_task
    import httpx
    with __import__("pytest").raises(httpx.HTTPStatusError):
        queue_cancel_task(task_id="nonexistent-task-id")


def test_queue_purge_requires_confirm():
    from yads_mcp.server import queue_purge
    result = queue_purge(confirm=True)
    assert "purged_count" in result


def test_queue_undo_purge_not_found():
    from yads_mcp.server import queue_undo_purge
    import httpx
    with __import__("pytest").raises(httpx.HTTPStatusError):
        queue_undo_purge(undo_batch="nonexistent-batch-id")
