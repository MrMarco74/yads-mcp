# Changelog

All notable changes to `yads-mcp` are documented here. This project follows
[Semantic Versioning](https://semver.org/) once a `0.1.0` tag is cut.

## [Unreleased]

### Added — Wave 5: OSINT / Discovery / Intelligence

5 read-only tools over a new tenant-scoped `/api/v1/discovery*`,
`/api/v1/brand-watches` and `/api/v1/shadow-domains` surface in YADS.

**OSINT / Discovery / Intelligence** (5 tools)
- `list_discovery_sessions(status, page, limit)`
- `get_discovery_session(session_id)`
- `list_discovery_candidates(session_id, status, page, limit)`
- `list_brand_watches()` — brand watches with shadow-candidate counts
- `list_shadow_domains(status, brand_watch_id, page, limit)` — DORA brand-abuse hunt output


### Added — Wave 4: Reports & Export

3 read-only tools over a new tenant-scoped `/api/v1/reports*` surface in YADS,
exposing structured-JSON report views (the dashboard's own report downloads
are binary PDF/Excel).

**Reports & Export** (3 tools)
- `get_executive_summary()` — posture summary (counts, score/grade, top risks, actions)
- `get_security_trends(days=30)` — historical security-score points
- `export_targets(tag, online, archived, page, limit)` — flat paginated targets export


### Added — Wave 3: Findings & Compliance

5 read-only tools wrapping a new `/api/v1/findings*` and `/api/v1/compliance*`
surface in YADS (tenant-scoped, API-key-authenticated), following the same
`_ok()`/`with client()` conventions as Waves 1–2.

**Findings & Compliance** (5 tools)
- `list_findings(severity, status, module, domain_search, page, limit)`
- `get_finding(yf_id)`
- `get_findings_summary()` — counts by severity / status / module
- `list_compliance_status(framework, page, limit)` — per-target scores/grades, worst first
- `get_compliance_summary()` — per-framework rollup (target count, avg score, grade distribution)

`scan_get_findings()` (Wave 1) now returns the first page of the new
SecurityFinding-based surface and is superseded by `list_findings()`; the old
raw-`ScanResult` dump endpoint it used was removed on the YADS side.


### Added — Wave 2: Target & Asset Management

12 tools wrapping a new `/api/v1/targets*` surface in YADS, following the
same `_ok()`/`with client()` and `destructive`+`confirm` conventions
established in Wave 1.

**Target & Asset Management** (12 tools)
- `list_targets(tag, online, scan_status, domain_search, archived, last_scanned_before, page, limit)`
- `get_target(target_id)`
- `add_target(domain)`
- `bulk_delete_targets(target_ids, confirm)` — destructive, 60s undo window
- `undo_bulk_delete_targets(undo_batch)`
- `bulk_archive_targets(target_ids)` / `archive_dead_targets()` / `restore_target(target_id)`
- `bulk_blocklist_targets(target_ids, confirm)` — destructive, no undo
- `get_target_changes(target_id, limit)`
- `get_scan_status(target_id)` — also closes a pre-existing gap in YADS's
  underlying (non-`/api/v1`) scan-status route, which had no auth
  dependency or tenant check at all
- `get_network_context(target_id)`

### Known limitations (Wave 2)

- `add_target` returns `409` (not a silent 500) when the domain is already
  registered under a different tenant, but there's no cross-tenant
  "who owns this" lookup tool — the caller only learns it's taken.
- `bulk_blocklist_targets` has no companion blocklist-management tool yet;
  reversing it requires both `restore_target()` and manually removing the
  blocklist row via the dashboard.

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

Waves 3–10 (Reports & Export, Findings & Compliance, OSINT/Discovery/
Intelligence, Integrations/Webhooks/Notifications) are tracked separately,
each its own design spec and release.
