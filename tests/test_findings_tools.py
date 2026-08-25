"""Covers the Findings & Compliance tool group (Wave 3), against the real
in-process YADS app -- see conftest.py for how yads_mcp.client is patched."""

import pytest


@pytest.fixture
def seeded_findings():
    """A target with three SecurityFindings and a compliance status row, all
    owned by the shared 'yads-mcp Test Tenant'."""
    from yads.database import engine
    from sqlmodel import Session, select, delete
    from yads.models import Target, Tenant, SecurityFinding, ComplianceTargetStatus

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        tgt = session.exec(
            select(Target).where(Target.domain == "yads-mcp-findings-fixture.example.com")
        ).first()
        if not tgt:
            tgt = Target(domain="yads-mcp-findings-fixture.example.com", tenant_id=tenant.id, tags=[])
            session.add(tgt); session.commit(); session.refresh(tgt)

        session.exec(delete(SecurityFinding).where(SecurityFinding.target_id == tgt.id))
        session.exec(delete(ComplianceTargetStatus).where(ComplianceTargetStatus.target_id == tgt.id))
        session.commit()

        for yf_id, h, sev, status, module, issue in [
            ("YF-MCP-001", "mcph1", "critical", "open", "nuclei_scanner", "RCE"),
            ("YF-MCP-002", "mcph2", "high", "open", "ssl_scanner", "Weak cipher"),
            ("YF-MCP-003", "mcph3", "low", "fixed", "http_headers", "Missing HSTS"),
        ]:
            session.add(SecurityFinding(
                yf_id=yf_id, finding_hash=h, tenant_id=tenant.id, target_id=tgt.id,
                domain=tgt.domain, module=module, issue=issue, severity=sev, status=status,
            ))
        session.add(ComplianceTargetStatus(
            target_id=tgt.id, framework="bsi", score=64, grade="D",
            passing_controls=12, failing_controls=9, findings=[],
        ))
        session.commit()
        return tgt.id


def test_list_findings_tool_returns_shape(seeded_findings):
    from yads_mcp.server import list_findings
    result = list_findings()
    assert "items" in result and "total" in result
    assert {"YF-MCP-001", "YF-MCP-002", "YF-MCP-003"} <= {f["yf_id"] for f in result["items"]}


def test_list_findings_tool_filters_by_severity(seeded_findings):
    from yads_mcp.server import list_findings
    result = list_findings(severity="critical")
    assert all(f["severity"] == "critical" for f in result["items"])


def test_get_finding_tool(seeded_findings):
    from yads_mcp.server import get_finding
    assert get_finding("YF-MCP-001")["issue"] == "RCE"


def test_get_finding_tool_not_found(seeded_findings):
    from yads_mcp.server import get_finding
    with pytest.raises(RuntimeError, match="404"):
        get_finding("YF-DOES-NOT-EXIST")


def test_get_findings_summary_tool(seeded_findings):
    from yads_mcp.server import get_findings_summary
    result = get_findings_summary()
    assert result["by_severity"].get("critical", 0) >= 1
    assert result["by_status"].get("open", 0) >= 2


def test_list_compliance_status_tool(seeded_findings):
    from yads_mcp.server import list_compliance_status
    rows = list_compliance_status()["items"]
    row = next((r for r in rows if r["domain"] == "yads-mcp-findings-fixture.example.com"), None)
    assert row is not None and row["framework"] == "bsi" and row["score"] == 64


def test_get_compliance_summary_tool(seeded_findings):
    from yads_mcp.server import get_compliance_summary
    frameworks = get_compliance_summary()["frameworks"]
    assert "bsi" in frameworks and frameworks["bsi"]["target_count"] >= 1
