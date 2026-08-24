"""Covers yads_mcp.client.client()'s env-var validation."""

import os
import pytest


def test_client_raises_without_yads_url(monkeypatch):
    monkeypatch.delenv("YADS_URL", raising=False)
    monkeypatch.setenv("YADS_API_KEY", "test-key")
    from yads_mcp.client import client, YadsConfigError
    with pytest.raises(YadsConfigError, match="YADS_URL"):
        client()


def test_client_raises_without_yads_api_key(monkeypatch):
    monkeypatch.setenv("YADS_URL", "http://localhost:8000")
    monkeypatch.delenv("YADS_API_KEY", raising=False)
    from yads_mcp.client import client, YadsConfigError
    with pytest.raises(YadsConfigError, match="YADS_API_KEY"):
        client()


def test_client_builds_httpx_client_with_correct_headers(monkeypatch):
    monkeypatch.setenv("YADS_URL", "http://localhost:8000")
    monkeypatch.setenv("YADS_API_KEY", "test-key")
    from yads_mcp.client import client
    c = client()
    assert c.headers["X-API-Key"] == "test-key"
    assert str(c.base_url) == "http://localhost:8000"
    c.close()
