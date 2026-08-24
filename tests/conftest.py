"""Points yads_mcp.client at an in-process YADS FastAPI app (via Starlette's
TestClient, which bridges httpx's sync API the same way a real network
client would be used) instead of a real network address, and provisions a
throwaway API key with every Wave-1 scope -- so these tests exercise the
real request/response shapes without needing a separately-running YADS
deployment. Requires the same test Postgres/Redis stack as the yads repo's
own tests/conftest.py (docker-compose.test.yml, ports 5433/6380).

YADS_MCP_TEST_REPO_ROOT can override where the yads package is imported
from -- during the SDD run that produced this file, the Wave-1 API
endpoints this server wraps only existed in a not-yet-merged git worktree,
not in the sibling yads checkout's default branch. Once merged, the plain
sibling-relative default below is correct and the override is unnecessary.
"""

import os
import sys
import uuid
from pathlib import Path

import pytest

_override = os.environ.get("YADS_MCP_TEST_REPO_ROOT")
YADS_REPO_ROOT = Path(_override) if _override else Path(__file__).resolve().parents[2] / "yads"
sys.path.insert(0, str(YADS_REPO_ROOT))

# yads.api.main mounts StaticFiles using a path relative to the process cwd
# (e.g. "yads/api/static"), matching how the yads repo's own test suite is
# always invoked from its repo root. Since yads-mcp's tests run from a
# different repo root, match that expectation here.
os.chdir(YADS_REPO_ROOT)

os.environ.setdefault("DATABASE_URL", "postgresql://yads_test:yads_test@localhost:5433/yads_test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-yads-testing-32chars!")
os.environ.setdefault("MFA_ENABLED", "false")
os.environ.setdefault("AUTH_MODE", "local")
os.environ.setdefault("METRICS_ENABLED", "false")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_DIR", "/tmp/yads-mcp-test-logs")
os.environ.setdefault("WORKER_MODE", "standalone")
os.environ.setdefault("YADS_ENCRYPTION_KEY", "test-encryption-key-bsi-compliant-123!")
os.environ.setdefault("YADS_ADMIN_USER", "admin")
os.environ.setdefault("YADS_ADMIN_PASS", "test-admin-password-for-yads-testing!")

from starlette.testclient import TestClient  # noqa: E402

from yads.api.main import app as yads_app  # noqa: E402
from yads.auth.security import create_access_token, generate_api_key  # noqa: E402

import yads_mcp.client as yads_client_module  # noqa: E402


@pytest.fixture(autouse=True)
def _patch_client(request, monkeypatch):
    # tests/test_client.py (Task 9) exercises yads_mcp.client.client()'s own
    # env-var validation logic against a real (unpatched) YADS_URL/
    # YADS_API_KEY -- leave it alone so this fixture's tenant/app patching
    # doesn't shadow the behavior it's specifically testing.
    if request.node.module.__name__.rsplit(".", 1)[-1] == "test_client":
        yield
        return

    login = TestClient(yads_app, raise_server_exceptions=False)

    from yads.database import engine
    from sqlmodel import Session, select
    from yads.models import Tenant, APIKey

    with Session(engine) as session:
        # NOTE: Tenant has no `slug` column in this yads schema version (the
        # brief assumed one); this fixture instead looks up/creates by
        # `.name`, matching the yads repo's own tests/conftest.py pattern.
        tenant = session.exec(select(Tenant).where(Tenant.name == "yads-mcp Test Tenant")).first()
        if not tenant:
            tenant = Tenant(name="yads-mcp Test Tenant")
            session.add(tenant)
            session.commit()
            session.refresh(tenant)

        plain_key, prefix, key_hash = generate_api_key()
        key_row = APIKey(
            tenant_id=tenant.id,
            name=f"yads-mcp-test-{uuid.uuid4().hex[:8]}",
            key_prefix=prefix,
            key_hash=key_hash,
            scopes=["read", "write", "scan_execute", "destructive"],
        )
        session.add(key_row)
        session.commit()

    def _fake_client():
        return TestClient(yads_app, headers={"X-API-Key": plain_key}, raise_server_exceptions=False)

    monkeypatch.setattr(yads_client_module, "client", _fake_client)
    import yads_mcp.server as server_module
    monkeypatch.setattr(server_module, "client", _fake_client)
    yield
