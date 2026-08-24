"""Covers the Tagging & Organization tool group."""

import pytest


@pytest.fixture
def owned_target_id():
    # Create a target directly via the DB the way the yads repo's own test
    # fixtures do -- a find-or-create by domain via a scan trigger is
    # heavier than needed here.
    from yads.database import engine
    from sqlmodel import Session, select
    from yads.models import Target, Tenant

    with Session(engine) as session:
        # NOTE: Tenant has no `slug` column in this yads schema version; look
        # up/create by `.name`, matching the exact tenant name that
        # tests/conftest.py's `_patch_client` fixture already creates/uses
        # ("yads-mcp Test Tenant"), so we attach to the same tenant the
        # patched API key belongs to instead of creating a second one.
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        existing = session.exec(select(Target).where(Target.domain == "yads-mcp-tags-fixture.example.com")).first()
        if existing:
            return existing.id
        target = Target(domain="yads-mcp-tags-fixture.example.com", tenant_id=tenant.id, tags=[])
        session.add(target)
        session.commit()
        session.refresh(target)
        return target.id


def test_tags_list_tool():
    from yads_mcp.server import tags_list
    result = tags_list()
    assert isinstance(result, list)


def test_tags_add_and_remove_tool(owned_target_id):
    from yads_mcp.server import tags_add_to_target, tags_remove_from_target

    result = tags_add_to_target(target_id=owned_target_id, tag="sedoparking")
    assert "sedoparking" in result

    result = tags_remove_from_target(target_id=owned_target_id, tag="sedoparking")
    assert "sedoparking" not in result


def test_tags_bulk_assign_tool(owned_target_id):
    from yads_mcp.server import tags_bulk_assign
    result = tags_bulk_assign(target_ids=[owned_target_id], tags=["bulk-tag"], action="add")
    assert result["updated"] == 1


def test_tags_bulk_add_by_ids_tool(owned_target_id):
    from yads_mcp.server import tags_bulk_add_by_ids
    result = tags_bulk_add_by_ids(target_ids=[owned_target_id], tag="bulk-tag-2")
    assert result["updated"] >= 1


def test_tags_delete_globally_tool(owned_target_id):
    from yads_mcp.server import tags_add_to_target, tags_delete_globally
    tags_add_to_target(target_id=owned_target_id, tag="delete-me-via-mcp")
    result = tags_delete_globally(tag_name="delete-me-via-mcp", confirm=True)
    assert result["removed_from"] >= 1


def test_tags_delete_globally_rejects_confirm_false():
    from yads_mcp.server import tags_delete_globally
    with pytest.raises(RuntimeError, match="400"):
        tags_delete_globally(tag_name="irrelevant-tag", confirm=False)
