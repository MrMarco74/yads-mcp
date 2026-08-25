"""Covers the OSINT / Discovery / Intelligence tool group (Wave 5), against
the real in-process YADS app -- see conftest.py for how yads_mcp.client is
patched."""

import pytest


@pytest.fixture
def seeded_discovery():
    from yads.database import engine
    from sqlmodel import Session, select, delete
    from yads.models import (Tenant, DiscoverySession, DiscoveryCandidate,
                             BrandWatch, ShadowDomainCandidate)

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()

        sess = session.exec(
            select(DiscoverySession).where(DiscoverySession.name == "mcp-wave5-session",
                                           DiscoverySession.tenant_id == tenant.id)
        ).first()
        if not sess:
            sess = DiscoverySession(tenant_id=tenant.id, name="mcp-wave5-session",
                                    seed_domains=["musterbank.de"], status="completed")
            session.add(sess); session.commit(); session.refresh(sess)

        session.exec(delete(DiscoveryCandidate).where(DiscoveryCandidate.session_id == sess.id))
        session.commit()
        for dom, score, status in [("mcp-shadow1.musterbank.uk", 0.9, "pending"),
                                   ("mcp-shadow2.musterbank.uk", 0.4, "accepted")]:
            session.add(DiscoveryCandidate(session_id=sess.id, domain=dom,
                        source_scanner="dns_scanner", relevance_score=score, status=status))

        bw = session.exec(
            select(BrandWatch).where(BrandWatch.keyword == "mcpwave5brand",
                                     BrandWatch.tenant_id == tenant.id)
        ).first()
        if not bw:
            bw = BrandWatch(tenant_id=tenant.id, keyword="mcpwave5brand", active=True)
            session.add(bw); session.commit(); session.refresh(bw)

        session.exec(delete(ShadowDomainCandidate).where(ShadowDomainCandidate.brand_watch_id == bw.id))
        session.commit()
        for dom, status in [("mcpwave5brand-x.com", "new"), ("mcpwave5brand-y.net", "confirmed")]:
            session.add(ShadowDomainCandidate(brand_watch_id=bw.id, tenant_id=tenant.id,
                        discovered_domain=dom, source="ct_log", status=status))
        session.commit()
        return {"session_id": sess.id, "brand_watch_id": bw.id}


def test_list_discovery_sessions_tool(seeded_discovery):
    from yads_mcp.server import list_discovery_sessions
    names = {s["name"] for s in list_discovery_sessions()["items"]}
    assert "mcp-wave5-session" in names


def test_get_discovery_session_tool(seeded_discovery):
    from yads_mcp.server import get_discovery_session
    result = get_discovery_session(seeded_discovery["session_id"])
    assert result["name"] == "mcp-wave5-session"


def test_get_discovery_session_tool_not_found(seeded_discovery):
    from yads_mcp.server import get_discovery_session
    with pytest.raises(RuntimeError, match="404"):
        get_discovery_session(99999999)


def test_list_discovery_candidates_tool(seeded_discovery):
    from yads_mcp.server import list_discovery_candidates
    domains = {c["domain"] for c in list_discovery_candidates(seeded_discovery["session_id"])["items"]}
    assert {"mcp-shadow1.musterbank.uk", "mcp-shadow2.musterbank.uk"} <= domains


def test_list_brand_watches_tool(seeded_discovery):
    from yads_mcp.server import list_brand_watches
    bw = next((x for x in list_brand_watches()["items"] if x["keyword"] == "mcpwave5brand"), None)
    assert bw is not None and bw["candidate_count"] >= 2


def test_list_shadow_domains_tool(seeded_discovery):
    from yads_mcp.server import list_shadow_domains
    domains = {s["discovered_domain"] for s in list_shadow_domains()["items"]}
    assert {"mcpwave5brand-x.com", "mcpwave5brand-y.net"} <= domains


def test_list_shadow_domains_tool_filter_status(seeded_discovery):
    from yads_mcp.server import list_shadow_domains
    result = list_shadow_domains(status="confirmed")
    assert all(s["status"] == "confirmed" for s in result["items"])
