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
