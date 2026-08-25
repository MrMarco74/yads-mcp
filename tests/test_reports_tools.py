"""Covers the Reports & Export tool group (Wave 4), against the real
in-process YADS app -- see conftest.py for how yads_mcp.client is patched."""

import pytest


@pytest.fixture
def seeded_reports():
    from yads.database import engine
    from sqlmodel import Session, select, delete
    from yads.models import Target, Tenant, SecurityTrend
    from datetime import datetime, timedelta

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        tgt = session.exec(
            select(Target).where(Target.domain == "yads-mcp-reports-fixture.example.com")
        ).first()
        if not tgt:
            tgt = Target(domain="yads-mcp-reports-fixture.example.com", tenant_id=tenant.id, tags=[])
            session.add(tgt); session.commit(); session.refresh(tgt)

        session.exec(delete(SecurityTrend).where(SecurityTrend.tenant_id == tenant.id))
        session.commit()
        now = datetime.utcnow()
        for days_ago, score, grade in [(15, 55, "E"), (2, 80, "B")]:
            session.add(SecurityTrend(
                tenant_id=tenant.id, score=score, grade=grade,
                recorded_at=now - timedelta(days=days_ago),
            ))
        session.commit()
        return tgt.id


def test_get_executive_summary_tool(seeded_reports):
    from yads_mcp.server import get_executive_summary
    result = get_executive_summary()
    for key in ("total_targets", "findings", "security_score", "grade"):
        assert key in result


def test_get_security_trends_tool(seeded_reports):
    from yads_mcp.server import get_security_trends
    result = get_security_trends(days=30)
    assert len(result["points"]) >= 2
    assert {"score", "grade", "recorded_at"} <= set(result["points"][0].keys())


def test_get_security_trends_tool_respects_window(seeded_reports):
    from yads_mcp.server import get_security_trends
    result = get_security_trends(days=5)
    assert len(result["points"]) == 1


def test_export_targets_tool(seeded_reports):
    from yads_mcp.server import export_targets
    result = export_targets()
    assert "items" in result and "total" in result
    domains = {row["domain"] for row in result["items"]}
    assert "yads-mcp-reports-fixture.example.com" in domains
