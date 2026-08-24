# Changelog

All notable changes to `yads-mcp` are documented here. This project follows
[Semantic Versioning](https://semver.org/) once a `0.1.0` tag is cut.

## [Unreleased]

### Added — Wave 1: Queue & Scan Control, Tagging & Organization, Scanning Execution

Initial release. `yads-mcp` is a thin MCP server wrapping YADS's
API-key-authenticated `/api/v1` surface — 19 tools across three groups,
built to mirror the `labcontrol_mcp` package's shape and conventions.

**Queue & Scan Control** (7 tools)
- `queue_status()`, `queue_list_rate_limited_modules()`
- `queue_pause()` / `queue_resume()` — fleet-wide, not tenant-scoped
- `queue_cancel_task(task_id)`
- `queue_purge(confirm)` — destructive, tenant-scoped, 60s undo window
- `queue_undo_purge(undo_batch)`

**Tagging & Organization** (6 tools)
- `tags_list()`
- `tags_add_to_target(target_id, tag)` / `tags_remove_from_target(target_id, tag)`
- `tags_bulk_assign(target_ids, tags, action)`
- `tags_bulk_add_by_ids(target_ids, tag)`
- `tags_delete_globally(tag_name, confirm)` — destructive, no undo

**Scanning Execution** (6 tools)
- `scan_trigger(target_url, profile)`
- `scan_trigger_by_target_id(target_id, scan_types, scan_priority)`
- `scan_bulk_preview_count(...)`, `scan_bulk_by_criteria(...)`, `scan_bulk_selected(...)`
- `scan_get_findings()`

**Foundation**
- New `destructive` API-key scope in YADS, required (alongside a
  `confirm: bool` body/query field) on every irreversible operation
  (`queue_purge`, `tags_delete_globally`).
- `read`/`write`/`scan_execute`/`destructive` scope enforcement on every
  route this package calls.
- A `require_tenant_scoped_key` guard in YADS rejecting any API key with a
  `NULL` tenant, closing a fail-open gap on 3 endpoints where a
  platform-admin key could otherwise see or act across every tenant.
- CSRF exemption for `X-API-Key`-authenticated requests, scoped to `/api/`
  paths (plus the one pre-existing non-`/api/` machine-to-machine route,
  `/tenants/provision`) so it can't be abused against cookie-session
  routes.
- Every tool surfaces the real server-side error detail on failure
  (`_ok()` helper) instead of a bare HTTP status code, so an agent calling
  a tool wrong can actually see why and self-correct.

### Known limitations

- `scan_bulk_by_criteria` has no target-tag filter yet — to scan targets
  *without* a given tag, resolve target ids via `tags_list`/your own
  logic and use `scan_bulk_selected` instead.
- `queue_pause`/`queue_resume` act on the whole worker fleet, not just the
  calling key's tenant (matches YADS's existing dashboard behavior).
- API-key-triggered bulk scans are not yet attributed to a specific key in
  YADS's audit log (tenant-scoped correctly, just not individually
  attributed) — a follow-up for a later wave.

Waves 2–10 (Target/Asset Management, Reports & Export, Findings &
Compliance, OSINT/Discovery, Tenant/User Admin, Integrations, System/Infra
Admin) are tracked separately, each its own design spec and release.
