# yads-mcp

MCP server that lets any MCP-capable LLM agent (Claude Code, or another
agent process reachable over the same network as YADS) drive queue
control, tagging, and scan execution through YADS's own `/api/v1` API,
without a human at the dashboard.

It's a thin stdio wrapper around YADS's existing HTTP API
(`/api/v1/queue/*`, `/api/v1/tags*`, `/api/v1/targets/*`) — no separate
execution path, no bypassing tenant scoping or the scan-dispatch code
path. Every action taken through here is subject to the same tenant
isolation, concurrent-scan limits, and change-detection logic as the
dashboard.

## 1. Create an API key

From a machine already logged into YADS (session cookie), via
`/developer` or the `/api-keys/` endpoint, create a key with the scopes
this agent needs:

- `read` — status/list operations (queue_status, tags_list, scan_get_findings, ...)
- `write` — tag mutations
- `scan_execute` — triggering scans (single or bulk)
- `destructive` — queue_purge, tags_delete_globally (also requires
  `confirm=True` on the call itself)

Copy the returned token now — it is never shown again.

## 2. Install

```bash
cd yads-mcp
python -m venv .venv
.venv/bin/pip install -e .
```

### Tests

```bash
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest tests/ -q
```

`tests/conftest.py` runs YADS in-process (Starlette `TestClient`) against
the same test Postgres/Redis stack as the `yads` repo's own tests
(`docker-compose.test.yml` in that repo, ports 5433/6380) — start that
stack first if these tests aren't passing.

## 3. Configure a client

Environment variables the server needs:

- `YADS_URL` — e.g. `https://yads.example.com`
- `YADS_API_KEY` — the token from step 1

### Claude Code

```bash
claude mcp add yads \
  --env YADS_URL=https://yads.example.com \
  --env YADS_API_KEY=<token> \
  -- /path/to/yads-mcp/.venv/bin/python -m yads_mcp.server
```

or add to `.mcp.json`:

```json
{
  "mcpServers": {
    "yads": {
      "command": "/path/to/yads-mcp/.venv/bin/python",
      "args": ["-m", "yads_mcp.server"],
      "env": {
        "YADS_URL": "https://yads.example.com",
        "YADS_API_KEY": "<token>"
      }
    }
  }
}
```

## Tools (Wave 1)

**Queue & Scan Control**
- `queue_status()`
- `queue_list_rate_limited_modules()`
- `queue_pause()` / `queue_resume()` — fleet-wide, not tenant-scoped
- `queue_cancel_task(task_id)`
- `queue_purge(confirm)` — destructive, tenant-scoped, 60s undo window
- `queue_undo_purge(undo_batch)`

**Tagging & Organization**
- `tags_list()`
- `tags_add_to_target(target_id, tag)` / `tags_remove_from_target(target_id, tag)`
- `tags_bulk_assign(target_ids, tags, action="add"|"remove"|"replace")`
- `tags_bulk_add_by_ids(target_ids, tag)`
- `tags_delete_globally(tag_name)` — destructive

**Scanning Execution**
- `scan_trigger(target_url, profile="standard")`
- `scan_trigger_by_target_id(target_id, scan_types, scan_priority=None)`
- `scan_bulk_preview_count(only_roots=False, online_only=False, scanned_before=None)`
- `scan_bulk_by_criteria(scan_types, only_roots=False, online_only=False, scanned_before=None)`
- `scan_bulk_selected(target_ids, scan_types)`
- `scan_get_findings()`

Waves 2–10 (Target/Asset Management, Reports & Export, Findings &
Compliance, OSINT/Discovery, Tenant/User Admin, Integrations, System/Infra
Admin) are tracked separately, each with its own design spec.
