"""Dependency status reports process memory without attempting recovery."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.agents import mcp_integration
from src.main import app
from src.services import storage


@pytest.mark.parametrize("storage_ready", [False, True])
@pytest.mark.parametrize("mcp_ready", [False, True])
def test_dependency_status_reads_memory_only(monkeypatch, storage_ready, mcp_ready):
    callback = MagicMock()
    create_storage = MagicMock(side_effect=AssertionError("storage must not be contacted"))
    create_mcp = MagicMock(side_effect=AssertionError("MCP must not be contacted"))
    monkeypatch.setattr(storage, "_service", object() if storage_ready else None)
    monkeypatch.setattr(storage, "_failure_callback", callback)
    monkeypatch.setattr(storage, "_create_storage_service", create_storage)
    monkeypatch.setattr(mcp_integration, "_tools", [object()] if mcp_ready else [])
    monkeypatch.setattr(mcp_integration, "MultiServerMCPClient", create_mcp)

    # Do not enter the client as a context manager: lifespan startup is not
    # part of this read-only endpoint and must not initialize dependencies.
    response = TestClient(app).get("/health/dependencies")
    assert response.status_code == 200
    assert response.json() == {
        "scope": "process_memory_only",
        "storage_initialized": storage_ready,
        "mcp_tools_loaded": mcp_ready,
    }
    callback.assert_not_called()
    create_storage.assert_not_called()
    create_mcp.assert_not_called()
