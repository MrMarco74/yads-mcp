"""Thin HTTP client for YADS's /api/v1 surface.

Authenticates with the X-API-Key header yads.auth.deps.get_api_key expects,
the same scoped-key pattern already used by the existing /api/v1/dast/scan
and /api/v1/findings routes.
"""

import os

import httpx


class YadsConfigError(RuntimeError):
    pass


def client() -> httpx.Client:
    url = os.environ.get("YADS_URL")
    api_key = os.environ.get("YADS_API_KEY")
    if not url:
        raise YadsConfigError("YADS_URL is not set (e.g. https://yads.example.com)")
    if not api_key:
        raise YadsConfigError("YADS_API_KEY is not set (create one via POST /api-keys/ with the scopes this agent needs)")
    return httpx.Client(base_url=url.rstrip("/"), headers={"X-API-Key": api_key}, timeout=30.0)
