"""Covers the Scanning Execution tool group -- the final piece of the
Wave 1 surface."""

import pytest


@pytest.fixture
def scan_target_id():
    from yads.database import engine
    from sqlmodel import Session, select
    from yads.models import Target, Tenant

    with Session(engine) as session:
        # NOTE: Tenant has no `slug` column in this yads schema version --
        # reuse the shared test tenant created by conftest.py's
        # `_patch_client` fixture, looked up the same way (by `name`).
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        existing = session.exec(select(Target).where(Target.domain == "yads-mcp-scan-fixture.example.com")).first()
        if existing:
            return existing.id
        target = Target(domain="yads-mcp-scan-fixture.example.com", tenant_id=tenant.id, tags=[])
        session.add(target)
        session.commit()
        session.refresh(target)
        return target.id


def test_scan_trigger_tool():
    from yads_mcp.server import scan_trigger
    result = scan_trigger(target_url="https://yads-mcp-dast-fixture.example.com", profile="quick")
    assert result["status"] == "queued"


def test_scan_trigger_by_target_id_tool(scan_target_id):
    from yads_mcp.server import scan_trigger_by_target_id
    result = scan_trigger_by_target_id(target_id=scan_target_id, scan_types=["ssl_scanner"])
    assert result["status"] == "queued"


def test_scan_bulk_preview_count_tool(scan_target_id):
    from yads_mcp.server import scan_bulk_preview_count
    result = scan_bulk_preview_count()
    assert "count" in result


def test_scan_bulk_by_criteria_tool(scan_target_id):
    from yads_mcp.server import scan_bulk_by_criteria
    result = scan_bulk_by_criteria(scan_types=["ssl_scanner"])
    assert "queued_count" in result


def test_scan_bulk_selected_tool(scan_target_id):
    from yads_mcp.server import scan_bulk_selected
    result = scan_bulk_selected(target_ids=[scan_target_id], scan_types=["ssl_scanner"])
    # Defensively >= 1 rather than strict == 1: a rerun against a warm
    # test-Postgres container could see this same fixture target already
    # queued from a prior run's leftovers (see Task 11 precedent).
    assert result["queued_count"] >= 1


def test_scan_get_findings_tool():
    from yads_mcp.server import scan_get_findings
    result = scan_get_findings()
    assert isinstance(result, list)
