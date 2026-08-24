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
def queue_list_rate_limited_modules() -> dict:
    """Which scanner modules are currently being rate-limited by an
    external target's API (circuit-breaker tripped), if any -- surfaced as
    part of the same queue-status data queue_status() returns, exposed here
    as its own discoverable tool for the common "is anything rate-limited
    right now" question."""
    with client() as c:
        resp = c.get("/api/v1/queue/status")
        resp.raise_for_status()
        data = resp.json()
        return {"rate_limited_module_count": data.get("rate_limited_module_count", 0)}


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


# --- Tagging & Organization ---


@mcp.tool()
def tags_list() -> list[str]:
    """All unique tags currently in use across this key's tenant's targets."""
    with client() as c:
        resp = c.get("/api/v1/tags")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def tags_add_to_target(target_id: int, tag: str) -> list[str]:
    """Add a tag to one target. Returns the target's full tag list after
    the change."""
    with client() as c:
        resp = c.post(f"/api/v1/targets/{target_id}/tags", json={"tag": tag})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def tags_remove_from_target(target_id: int, tag: str) -> list[str]:
    """Remove a tag from one target. Returns the target's full tag list
    after the change."""
    with client() as c:
        resp = c.delete(f"/api/v1/targets/{target_id}/tags/{tag}")
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def tags_bulk_assign(target_ids: list[int], tags: list[str], action: str = "add") -> dict:
    """Add, remove, or replace tags on multiple targets at once. action:
    "add" (default), "remove", or "replace" (replaces each target's entire
    tag list with `tags`)."""
    with client() as c:
        resp = c.post("/api/v1/tags/bulk-assign", json={"target_ids": target_ids, "tags": tags, "action": action})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def tags_bulk_add_by_ids(target_ids: list[int], tag: str) -> dict:
    """Add a single tag to multiple targets by id (simpler variant of
    tags_bulk_assign for the common "add one tag to many targets" case)."""
    with client() as c:
        resp = c.post("/api/v1/targets/bulk/tag", json={"target_ids": target_ids, "tag": tag})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def tags_delete_globally(tag_name: str) -> dict:
    """Remove a tag from every target in this key's tenant that has it --
    irreversible. Requires the 'destructive' scope on this API key."""
    with client() as c:
        resp = c.delete(f"/api/v1/tags/{tag_name}")
        resp.raise_for_status()
        return resp.json()


# --- Scanning Execution ---


@mcp.tool()
def scan_trigger(target_url: str, profile: str = "standard") -> dict:
    """Trigger a scan for a URL, finding-or-creating the Target by domain.
    profile: "quick" (web_analyzer only), "standard" (dns_scanner,
    web_analyzer, ssl_scanner -- default), or "full" (every module except
    dns_cleanup)."""
    with client() as c:
        resp = c.post("/api/v1/dast/scan", json={"target_url": target_url, "profile": profile})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def scan_trigger_by_target_id(target_id: int, scan_types: list[str], scan_priority: int | None = None) -> dict:
    """Trigger a scan for an already-known target by its numeric id, with
    an explicit module list (e.g. ["catchall_detector"] for a
    parked-domain-only check). scan_types accepts module names from the
    scanner registry, plus "full_scan" (expands to every module except
    subdomain_scanner and catchall_detector) and "dns_cleanup"."""
    body: dict = {"scan_types": scan_types}
    if scan_priority is not None:
        body["scan_priority"] = scan_priority
    with client() as c:
        resp = c.post(f"/api/v1/targets/{target_id}/scan", json=body)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def scan_bulk_preview_count(only_roots: bool = False, online_only: bool = False, scanned_before: str | None = None) -> dict:
    """Count how many targets match a set of bulk-scan criteria, without
    queuing anything -- use before scan_bulk_by_criteria to see the blast
    radius first. scanned_before is an ISO date string ("2026-08-01");
    matches targets last scanned before that date OR never scanned."""
    params: dict = {"only_roots": only_roots, "online_only": online_only}
    if scanned_before:
        params["scanned_before"] = scanned_before
    with client() as c:
        resp = c.get("/api/v1/targets/bulk-scan/preview-count", params=params)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def scan_bulk_by_criteria(
    scan_types: list[str],
    only_roots: bool = False,
    online_only: bool = False,
    scanned_before: str | None = None,
) -> dict:
    """Queue a scan for every target matching the given criteria (combined
    with AND). No target-tag filter exists yet -- to scan only targets
    without a given tag, list tags_list, resolve target ids yourself, and
    use scan_bulk_selected instead."""
    body: dict = {"scan_types": scan_types, "only_roots": only_roots, "online_only": online_only}
    if scanned_before:
        body["scanned_before"] = scanned_before
    with client() as c:
        resp = c.post("/api/v1/targets/bulk-scan", json=body)
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def scan_bulk_selected(target_ids: list[int], scan_types: list[str]) -> dict:
    """Queue a scan for an explicit list of target ids."""
    with client() as c:
        resp = c.post("/api/v1/targets/bulk/scan", json={"target_ids": target_ids, "scan_types": scan_types})
        resp.raise_for_status()
        return resp.json()


@mcp.tool()
def scan_get_findings() -> list[dict]:
    """All scan findings for this key's tenant, newest first."""
    with client() as c:
        resp = c.get("/api/v1/findings")
        resp.raise_for_status()
        return resp.json()


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
