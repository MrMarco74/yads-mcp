"""MCP server exposing YADS's API-key-authenticated /api/v1 surface as
tools, so any MCP-capable LLM agent can drive queue control, tagging,
scanning, and target/asset management without a human at the dashboard.

Run with: YADS_URL=https://yads.example.com YADS_API_KEY=<token> \
    python -m yads_mcp.server
"""

import httpx

from mcp.server.mcpserver import MCPServer

from yads_mcp.client import client

mcp = MCPServer("yads")


def _ok(resp: httpx.Response):
    """Raise with the server's actual error detail instead of a bare status
    code. `resp.raise_for_status()` alone discards the response body, so an
    LLM agent calling e.g. queue_purge(confirm=False) would only ever see
    "400 Bad Request" and never the "Set confirm=true..." detail it needs
    to self-correct. The body contains no credentials -- it's the target's
    own JSON error response -- so it's safe to surface in full."""
    if resp.is_error:
        raise RuntimeError(f"YADS API {resp.status_code}: {resp.text[:500]}")
    return resp.json()


# --- Queue & Scan Control ---


@mcp.tool()
def queue_status() -> dict:
    """Current queue state for this API key's tenant: whether the queue is
    active (paused/resumed), queued/running target counts, and the tenant's
    active/reserved Celery tasks."""
    with client() as c:
        return _ok(c.get("/api/v1/queue/status"))


@mcp.tool()
def queue_list_rate_limited_modules() -> dict:
    """How many scanner modules are currently being rate-limited by an
    external target's API (circuit-breaker tripped), if any -- surfaced as
    part of the same queue-status data queue_status() returns, exposed here
    as its own discoverable tool for the common "is anything rate-limited
    right now" question. Only a count is available via the API, not the
    specific module names."""
    data = None
    with client() as c:
        data = _ok(c.get("/api/v1/queue/status"))
    return {"rate_limited_module_count": data.get("rate_limited_module_count", 0)}


@mcp.tool()
def queue_pause() -> dict:
    """Pause the scan queue -- stops workers from picking up new tasks.
    NOTE: this is fleet-wide, not scoped to this key's tenant (matches
    YADS's existing dashboard pause behavior)."""
    with client() as c:
        return _ok(c.post("/api/v1/queue/control", json={"action": "pause"}))


@mcp.tool()
def queue_resume() -> dict:
    """Resume the scan queue after a pause. NOTE: like queue_pause, this is
    fleet-wide, not scoped to this key's tenant."""
    with client() as c:
        return _ok(c.post("/api/v1/queue/control", json={"action": "resume"}))


@mcp.tool()
def queue_cancel_task(task_id: str) -> dict:
    """Cancel a single queued/reserved/active scan task by its Celery task
    id (see queue_status's active_tasks/reserved_tasks for ids). Only
    cancels tasks belonging to this key's tenant."""
    with client() as c:
        return _ok(c.post(f"/api/v1/queue/tasks/{task_id}/cancel"))


@mcp.tool()
def queue_purge(confirm: bool) -> dict:
    """Clear every queued/running scan for this key's tenant -- irreversible
    beyond a 60-second undo window (see queue_undo_purge). Requires the
    'destructive' scope on this API key. Set confirm=True to actually
    perform this."""
    with client() as c:
        return _ok(c.post("/api/v1/queue/purge", json={"confirm": confirm}))


@mcp.tool()
def queue_undo_purge(undo_batch: str) -> dict:
    """Re-queue the tasks purged by a prior queue_purge call, using the
    undo_batch id from that call's response. Only works within 60 seconds
    of the purge, and only for tasks that hadn't started running yet."""
    with client() as c:
        return _ok(c.post("/api/v1/queue/undo-purge", json={"undo_batch": undo_batch}))


# --- Tagging & Organization ---


@mcp.tool()
def tags_list() -> list[str]:
    """All unique tags currently in use across this key's tenant's targets."""
    with client() as c:
        return _ok(c.get("/api/v1/tags"))


@mcp.tool()
def tags_add_to_target(target_id: int, tag: str) -> list[str]:
    """Add a tag to one target. Returns the target's full tag list after
    the change."""
    with client() as c:
        return _ok(c.post(f"/api/v1/targets/{target_id}/tags", json={"tag": tag}))


@mcp.tool()
def tags_remove_from_target(target_id: int, tag: str) -> list[str]:
    """Remove a tag from one target. Returns the target's full tag list
    after the change."""
    with client() as c:
        return _ok(c.delete(f"/api/v1/targets/{target_id}/tags/{tag}"))


@mcp.tool()
def tags_bulk_assign(target_ids: list[int], tags: list[str], action: str = "add") -> dict:
    """Add, remove, or replace tags on multiple targets at once. action:
    "add" (default), "remove", or "replace" (replaces each target's entire
    tag list with `tags`)."""
    with client() as c:
        return _ok(c.post("/api/v1/tags/bulk-assign", json={"target_ids": target_ids, "tags": tags, "action": action}))


@mcp.tool()
def tags_bulk_add_by_ids(target_ids: list[int], tag: str) -> dict:
    """Add a single tag to multiple targets by id (simpler variant of
    tags_bulk_assign for the common "add one tag to many targets" case)."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk/tag", json={"target_ids": target_ids, "tag": tag}))


@mcp.tool()
def tags_delete_globally(tag_name: str, confirm: bool) -> dict:
    """Remove a tag from every target in this key's tenant that has it --
    irreversible, no undo. Requires the 'destructive' scope on this API
    key. Set confirm=True to actually perform this."""
    with client() as c:
        return _ok(c.delete(f"/api/v1/tags/{tag_name}", params={"confirm": confirm}))


# --- Scanning Execution ---


@mcp.tool()
def scan_trigger(target_url: str, profile: str = "standard") -> dict:
    """Trigger a scan for a URL, finding-or-creating the Target by domain.
    profile: "quick" (web_analyzer only), "standard" (dns_scanner,
    web_analyzer, ssl_scanner -- default), or "full" (all 7 modules:
    dns_cleanup, subdomain_scanner, dns_scanner, web_analyzer, ssl_scanner,
    crawler, cve_scanner)."""
    with client() as c:
        return _ok(c.post("/api/v1/dast/scan", json={"target_url": target_url, "profile": profile}))


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
        return _ok(c.post(f"/api/v1/targets/{target_id}/scan", json=body))


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
        return _ok(c.get("/api/v1/targets/bulk-scan/preview-count", params=params))


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
        return _ok(c.post("/api/v1/targets/bulk-scan", json=body))


@mcp.tool()
def scan_bulk_selected(target_ids: list[int], scan_types: list[str]) -> dict:
    """Queue a scan for an explicit list of target ids."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk/scan", json={"target_ids": target_ids, "scan_types": scan_types}))


@mcp.tool()
def scan_get_findings() -> list[dict]:
    """Security findings for this key's tenant, newest first (first page).

    Superseded by list_findings(), which adds severity/status/module/domain
    filtering and pagination and returns the full {items,total,page,limit}
    envelope. Kept as a simple list-returning convenience; for anything beyond
    a quick first-page peek, use list_findings()."""
    with client() as c:
        return _ok(c.get("/api/v1/findings")).get("items", [])


# --- Target & Asset Management ---


@mcp.tool()
def list_targets(
    tag: str | None = None,
    online: bool | None = None,
    scan_status: str | None = None,
    domain_search: str | None = None,
    archived: bool = False,
    last_scanned_before: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """List targets for this key's tenant, with optional filters (combined
    with AND). limit is capped at 100 server-side. scan_status accepts
    "idle"/"queued"/"running"/"failed". last_scanned_before is an ISO date
    string; matches targets scanned before that date OR never scanned."""
    params: dict = {"archived": archived, "page": page, "limit": limit}
    if tag:
        params["tag"] = tag
    if online is not None:
        params["online"] = online
    if scan_status:
        params["scan_status"] = scan_status
    if domain_search:
        params["domain_search"] = domain_search
    if last_scanned_before:
        params["last_scanned_before"] = last_scanned_before
    with client() as c:
        return _ok(c.get("/api/v1/targets", params=params))


@mcp.tool()
def get_target(target_id: int) -> dict:
    """Lean summary of one target: domain, scan status/progress, tags,
    archive state, when it was created, when it was last scanned, and how
    many distinct scanner modules have results for it. For per-module scan
    data, use scan_get_findings() (Wave 1) -- note it returns every finding
    for the whole tenant, not just this target, so filter its result by
    target_id client-side. For this target's recent change history, use
    get_target_changes() instead."""
    with client() as c:
        return _ok(c.get(f"/api/v1/targets/{target_id}"))


@mcp.tool()
def add_target(domain: str) -> dict:
    """Add a target by domain, or return the existing one if it's already
    present (find-or-create). Blocked for internal/private-network domains
    by SSRF protection. Does not trigger a scan -- follow up with
    scan_trigger_by_target_id() if you want one."""
    with client() as c:
        return _ok(c.post("/api/v1/targets", json={"domain": domain}))


@mcp.tool()
def bulk_delete_targets(target_ids: list[int], confirm: bool) -> dict:
    """Permanently delete targets and all their scan history/findings --
    irreversible beyond a 60-second undo window (see
    undo_bulk_delete_targets; the domain/tags are restorable, scan history
    is not). Requires the 'destructive' scope on this API key. Set
    confirm=True to actually perform this."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk-delete", json={"target_ids": target_ids, "confirm": confirm}))


@mcp.tool()
def undo_bulk_delete_targets(undo_batch: str) -> dict:
    """Re-create targets deleted by a prior bulk_delete_targets call, using
    the undo_batch id from that call's response. Only works within 60
    seconds of the delete -- restores domain/tags only, not scan history."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk-delete/undo", json={"undo_batch": undo_batch}))


@mcp.tool()
def bulk_archive_targets(target_ids: list[int]) -> dict:
    """Archive targets -- stops them from being scanned, but fully
    reversible via restore_target(). Not destructive."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk-archive", json={"target_ids": target_ids}))


@mcp.tool()
def archive_dead_targets() -> dict:
    """Archive every target in this key's tenant whose most recent DNS
    scan returned empty records (i.e. the domain no longer resolves).
    Tenant-wide sweep, no target_ids needed. Reversible via
    restore_target()."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/archive-dead"))


@mcp.tool()
def restore_target(target_id: int) -> dict:
    """Un-archive a target, clearing its archived state so it's scanned
    again."""
    with client() as c:
        return _ok(c.post(f"/api/v1/targets/{target_id}/restore"))


@mcp.tool()
def bulk_blocklist_targets(target_ids: list[int], confirm: bool) -> dict:
    """Add each target's domain to this tenant's Discovery blocklist
    (exact match -- future Discovery runs won't re-add it) AND archive the
    target. Requires the 'destructive' scope: unlike plain archiving,
    reversing this needs both restore_target() and manually removing the
    blocklist entry (no blocklist-management tool exists yet), so there's
    no clean single-action undo. Set confirm=True to actually perform
    this."""
    with client() as c:
        return _ok(c.post("/api/v1/targets/bulk-blocklist", json={"target_ids": target_ids, "confirm": confirm}))


@mcp.tool()
def get_target_changes(target_id: int, limit: int = 30) -> list[dict]:
    """Recent detected changes for a target (new/changed/removed findings
    across scans), newest first. limit capped at 100 server-side."""
    with client() as c:
        return _ok(c.get(f"/api/v1/targets/{target_id}/changes", params={"limit": limit}))


@mcp.tool()
def get_scan_status(target_id: int) -> dict:
    """Current scan status/progress message for a target -- live if a scan
    is running, otherwise the last known state ("idle", "queued", etc.)."""
    with client() as c:
        return _ok(c.get(f"/api/v1/targets/{target_id}/scan-status"))


@mcp.tool()
def get_network_context(target_id: int) -> dict:
    """Network context captured during a target's scans -- the external IP
    YADS scanned from and the IPs the target resolved to at scan time."""
    with client() as c:
        return _ok(c.get(f"/api/v1/targets/{target_id}/network-context"))


# --- Findings & Compliance (Wave 3, read-only) ---


@mcp.tool()
def list_findings(
    severity: str | None = None,
    status: str | None = None,
    module: str | None = None,
    domain_search: str | None = None,
    page: int = 1,
    limit: int = 20,
) -> dict:
    """List security findings for this key's tenant, with optional filters
    (combined with AND). severity is critical/high/medium/low/info; status is
    open/acknowledged/false_positive/fixed; module is the scanner module name
    (e.g. "ssl_scanner"); domain_search is a substring match on the domain.
    Returns {items, total, page, limit}; limit is capped at 200 server-side."""
    params: dict = {"page": page, "limit": limit}
    if severity:
        params["severity"] = severity
    if status:
        params["status"] = status
    if module:
        params["module"] = module
    if domain_search:
        params["domain_search"] = domain_search
    with client() as c:
        return _ok(c.get("/api/v1/findings", params=params))


@mcp.tool()
def get_finding(yf_id: str) -> dict:
    """Full detail for one security finding by its YF id (e.g. "YF-000042"),
    including triage status, assignee and ticket reference. 404 if the finding
    doesn't exist or belongs to another tenant."""
    with client() as c:
        return _ok(c.get(f"/api/v1/findings/{yf_id}"))


@mcp.tool()
def get_findings_summary() -> dict:
    """Aggregate counts of this tenant's security findings, grouped by
    severity, status and module -- the quick "what's my finding posture"
    overview. Returns {total, by_severity, by_status, by_module}."""
    with client() as c:
        return _ok(c.get("/api/v1/findings/summary"))


@mcp.tool()
def list_compliance_status(
    framework: str | None = None,
    page: int = 1,
    limit: int = 50,
) -> dict:
    """Per-target compliance status rows for this tenant (each with domain,
    framework, score, grade, passing/failing control counts), ordered worst
    score first. Optionally filter by framework (e.g. "bsi", "dora").
    Returns {items, total, page, limit}; limit is capped at 500 server-side."""
    params: dict = {"page": page, "limit": limit}
    if framework:
        params["framework"] = framework
    with client() as c:
        return _ok(c.get("/api/v1/compliance/status", params=params))


@mcp.tool()
def get_compliance_summary() -> dict:
    """Per-framework compliance rollup for this tenant: assessed-target count,
    average score, and grade distribution for each framework. Returns
    {frameworks: {<framework>: {target_count, avg_score, grade_distribution}}}."""
    with client() as c:
        return _ok(c.get("/api/v1/compliance/summary"))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
