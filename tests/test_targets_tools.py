"""Covers the Target & Asset Management tool group."""

import pytest


def test_list_targets_tool_returns_shape():
    from yads_mcp.server import list_targets
    result = list_targets()
    assert "targets" in result
    assert "total" in result


def test_add_and_get_target_tool():
    from yads_mcp.server import add_target, get_target
    added = add_target(domain="yads-mcp-wave2-fixture.example.com")
    assert added["domain"] == "yads-mcp-wave2-fixture.example.com"

    fetched = get_target(target_id=added["id"])
    assert fetched["domain"] == "yads-mcp-wave2-fixture.example.com"


def test_list_targets_tool_filters_by_domain_search():
    from yads_mcp.server import add_target, list_targets
    add_target(domain="yads-mcp-wave2-search-fixture.example.com")
    result = list_targets(domain_search="wave2-search-fixture")
    domains = [t["domain"] for t in result["targets"]]
    assert "yads-mcp-wave2-search-fixture.example.com" in domains


def test_bulk_delete_and_undo_tools():
    from yads_mcp.server import add_target, bulk_delete_targets, undo_bulk_delete_targets

    added = add_target(domain="yads-mcp-wave2-delete-fixture.example.com")
    result = bulk_delete_targets(target_ids=[added["id"]], confirm=True)
    assert result["deleted_count"] == 1
    assert result["undo_batch"]

    undo_result = undo_bulk_delete_targets(undo_batch=result["undo_batch"])
    assert undo_result["restored_count"] == 1


def test_bulk_delete_requires_confirm_tool():
    from yads_mcp.server import add_target, bulk_delete_targets
    import pytest

    added = add_target(domain="yads-mcp-wave2-delete-noconfirm.example.com")
    with pytest.raises(RuntimeError, match="400"):
        bulk_delete_targets(target_ids=[added["id"]], confirm=False)


def test_bulk_archive_and_restore_tools():
    from yads_mcp.server import add_target, bulk_archive_targets, restore_target

    added = add_target(domain="yads-mcp-wave2-archive-fixture.example.com")
    result = bulk_archive_targets(target_ids=[added["id"]])
    assert result["archived_count"] == 1

    restored = restore_target(target_id=added["id"])
    assert restored["is_archived"] is False


def test_archive_dead_targets_tool():
    from yads_mcp.server import archive_dead_targets
    result = archive_dead_targets()
    assert "archived_count" in result


def test_bulk_blocklist_tool():
    from yads_mcp.server import add_target, bulk_blocklist_targets

    added = add_target(domain="yads-mcp-wave2-blocklist-fixture.example.com")
    result = bulk_blocklist_targets(target_ids=[added["id"]], confirm=True)
    assert result["blocklisted_count"] == 1
    assert result["archived_count"] == 1
