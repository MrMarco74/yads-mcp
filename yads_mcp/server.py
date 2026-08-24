"""MCP server exposing YADS's API-key-authenticated /api/v1 surface as
tools, so any MCP-capable LLM agent can drive queue control, tagging, and
scanning operations without a human at the dashboard.

Run with: YADS_URL=https://yads.example.com YADS_API_KEY=<token> \
    python -m yads_mcp.server
"""

from mcp.server.mcpserver import MCPServer

from yads_mcp.client import client

mcp = MCPServer("yads")


# --- Queue & Scan Control ---


@mcp.tool()
def queue_status() -> dict:
    """Current queue state for this API key's tenant: whether the queue is
    active (paused/resumed), queued/running target counts, and the tenant's
    active/reserved Celery tasks."""
    with client() as c:
        resp = c.get("/api/v1/queue/status")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def queue_pause() -> dict:
    """Pause the scan queue -- stops workers from picking up new tasks.
    NOTE: this is fleet-wide, not scoped to this key's tenant (matches
    YADS's existing dashboard pause behavior)."""
    with client() as c:
        resp = c.post("/api/v1/queue/control", json={"action": "pause"})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def queue_resume() -> dict:
    """Resume the scan queue after a pause."""
    with client() as c:
        resp = c.post("/api/v1/queue/control", json={"action": "resume"})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def queue_cancel_task(task_id: str) -> dict:
    """Cancel a single queued/reserved/active scan task by its Celery task
    id (see queue_status's active_tasks/reserved_tasks for ids). Only
    cancels tasks belonging to this key's tenant."""
    with client() as c:
        resp = c.post(f"/api/v1/queue/tasks/{task_id}/cancel")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def queue_purge(confirm: bool) -> dict:
    """Clear every queued/running scan for this key's tenant -- irreversible
    beyond a 60-second undo window (see queue_undo_purge). Requires the
    'destructive' scope on this API key. Set confirm=True to actually
    perform this."""
    with client() as c:
        resp = c.post("/api/v1/queue/purge", json={"confirm": confirm})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def queue_undo_purge(undo_batch: str) -> dict:
    """Re-queue the tasks purged by a prior queue_purge call, using the
    undo_batch id from that call's response. Only works within 60 seconds
    of the purge, and only for tasks that hadn't started running yet."""
    with client() as c:
        resp = c.post("/api/v1/queue/undo-purge", json={"undo_batch": undo_batch})
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
