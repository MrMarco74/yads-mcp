# yads-mcp

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Language](https://img.shields.io/badge/language-Python-informational.svg) ![MCP](https://img.shields.io/badge/protocol-MCP-orange.svg) ![Wave](https://img.shields.io/badge/wave-5%20of%2010-lightgrey.svg) ![AI generated](https://img.shields.io/badge/AI-generated-8A2BE2.svg)

MCP server that lets any MCP-capable LLM agent (Claude Code, or another
agent process reachable over the same network as YADS) drive queue
control, tagging, scan execution, and target/asset management through
YADS's own `/api/v1` API, without a human at the dashboard.

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

- `read` — status/list operations (queue_status, tags_list, scan_get_findings,
  list_targets, get_target, get_target_changes, get_scan_status,
  get_network_context, ...)
- `write` — tag mutations, and target mutations (add_target,
  undo_bulk_delete_targets, bulk_archive_targets, archive_dead_targets,
  restore_target)
- `scan_execute` — triggering scans (single or bulk)
- `destructive` — queue_purge, tags_delete_globally, bulk_delete_targets,
  bulk_blocklist_targets (also requires `confirm=True` on the call itself)

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

## Tools

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
- `tags_delete_globally(tag_name, confirm)` — destructive, no undo

**Scanning Execution**
- `scan_trigger(target_url, profile="standard")`
- `scan_trigger_by_target_id(target_id, scan_types, scan_priority=None)`
- `scan_bulk_preview_count(only_roots=False, online_only=False, scanned_before=None)`
- `scan_bulk_by_criteria(scan_types, only_roots=False, online_only=False, scanned_before=None)`
- `scan_bulk_selected(target_ids, scan_types)`
- `scan_get_findings()`

**Target & Asset Management** (Wave 2)
- `list_targets(tag=None, online=None, scan_status=None, domain_search=None, archived=False, last_scanned_before=None, page=1, limit=20)`
- `get_target(target_id)`
- `add_target(domain)`
- `bulk_delete_targets(target_ids, confirm)` — destructive, 60s undo window
- `undo_bulk_delete_targets(undo_batch)`
- `bulk_archive_targets(target_ids)` / `archive_dead_targets()` / `restore_target(target_id)`
- `bulk_blocklist_targets(target_ids, confirm)` — destructive, no undo
- `get_target_changes(target_id, limit=30)`
- `get_scan_status(target_id)`
- `get_network_context(target_id)`

**Findings & Compliance** (Wave 3, read-only)
- `list_findings(severity=None, status=None, module=None, domain_search=None, page=1, limit=20)`
- `get_finding(yf_id)`
- `get_findings_summary()` — counts by severity / status / module
- `list_compliance_status(framework=None, page=1, limit=50)` — per-target scores/grades, worst first
- `get_compliance_summary()` — per-framework rollup (target count, avg score, grade distribution)

**Reports & Export** (Wave 4, read-only)
- `get_executive_summary()` — posture summary: counts, score/grade, top risks, recommended actions
- `get_security_trends(days=30)` — historical security-score points
- `export_targets(tag=None, online=None, archived=False, page=1, limit=500)` — flat targets export

**OSINT / Discovery / Intelligence** (Wave 5, read-only)
- `list_discovery_sessions(status=None, page=1, limit=20)`
- `get_discovery_session(session_id)`
- `list_discovery_candidates(session_id, status=None, page=1, limit=50)`
- `list_brand_watches()` — brand-keyword watches with shadow-candidate counts
- `list_shadow_domains(status=None, brand_watch_id=None, page=1, limit=50)` — DORA brand-abuse hunt output

Waves 6–10 (
Integrations/Webhooks/Notifications) are tracked separately, each with its own design spec.

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT — see [LICENSE](LICENSE).
