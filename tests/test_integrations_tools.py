"""Covers the Integrations / Webhooks / Notifications tool group (Wave 6),
against the real in-process YADS app -- see conftest.py for client patching.
Also verifies the tools never surface integration secrets."""

import pytest


@pytest.fixture
def seeded_integrations():
    from yads.database import engine
    from sqlmodel import Session, select, delete
    from yads.models import Tenant, Webhook, ReportSubscription, IntegrationConfig

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        session.exec(delete(Webhook).where(Webhook.tenant_id == tenant.id))
        session.exec(delete(ReportSubscription).where(ReportSubscription.tenant_id == tenant.id))
        session.exec(delete(IntegrationConfig).where(IntegrationConfig.tenant_id == tenant.id))
        session.commit()
        session.add(Webhook(
            tenant_id=tenant.id,
            url="https://hooks.slack.com/services/T0/B0/MCPWAVE6SECRETTOKEN",
            event_types=["vuln_found"], is_active=True,
        ))
        session.add(ReportSubscription(
            tenant_id=tenant.id, name="MCP Monthly", report_type="compliance",
            recipients=["dpo@example.com"], frequency="monthly", is_active=True,
        ))
        session.add(IntegrationConfig(
            tenant_id=tenant.id, integration_type="jira",
            config={"api_token": "MCPWAVE6-JIRA-SECRET", "url": "https://jira"},
            is_active=True,
        ))
        session.commit()


def test_list_webhooks_tool_masks_secret(seeded_integrations):
    from yads_mcp.server import list_webhooks
    result = list_webhooks()
    wh = result["items"][0]
    assert "hooks.slack.com" in wh["url_masked"]
    assert "MCPWAVE6SECRETTOKEN" not in str(result)


def test_list_report_subscriptions_tool(seeded_integrations):
    from yads_mcp.server import list_report_subscriptions
    sub = next((s for s in list_report_subscriptions()["items"] if s["name"] == "MCP Monthly"), None)
    assert sub is not None and sub["report_type"] == "compliance"


def test_list_integrations_tool_no_secrets(seeded_integrations):
    from yads_mcp.server import list_integrations
    result = list_integrations()
    jira = next((i for i in result["items"] if i["integration_type"] == "jira"), None)
    assert jira is not None and jira["is_active"] is True
    assert "config" not in jira
    assert "MCPWAVE6-JIRA-SECRET" not in str(result)
