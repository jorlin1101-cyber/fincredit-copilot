"""Recovery of optional startup dependencies and S3 error classification."""

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.services.dependency_recovery import DependencyRecovery, retry_dependency
from src.services.storage import StorageService


@pytest.mark.parametrize("code", ["403", "429", "502", "AccessDenied"])
def test_bucket_errors_are_not_treated_as_missing(code):
    client = MagicMock()
    client.head_bucket.side_effect = ClientError({"Error": {"Code": code}}, "HeadBucket")
    service = StorageService.__new__(StorageService)
    service._client = client
    service._bucket = "documents"

    with pytest.raises(ClientError):
        service._ensure_bucket()
    client.create_bucket.assert_not_called()


@pytest.mark.parametrize("code", ["404", "NoSuchBucket", "NotFound"])
def test_missing_bucket_is_created(code):
    client = MagicMock()
    client.head_bucket.side_effect = ClientError({"Error": {"Code": code}}, "HeadBucket")
    service = StorageService.__new__(StorageService)
    service._client = client
    service._bucket = "documents"
    service._ensure_bucket()
    client.create_bucket.assert_called_once_with(Bucket="documents")


@pytest.mark.asyncio
async def test_retry_recovers_after_transient_failures():
    initialize = AsyncMock(side_effect=[RuntimeError("unavailable"), None])
    with patch("src.services.dependency_recovery.asyncio.sleep", new_callable=AsyncMock) as sleep:
        await retry_dependency("MCP", initialize)
    assert initialize.await_count == 2
    assert [call.args[0] for call in sleep.await_args_list] == [5.0, 10.0]


@pytest.mark.asyncio
async def test_retry_propagates_shutdown_cancellation():
    initialize = AsyncMock()
    with patch("src.services.dependency_recovery.asyncio.sleep", side_effect=asyncio.CancelledError):
        with pytest.raises(asyncio.CancelledError):
            await retry_dependency("MCP", initialize)
    initialize.assert_not_awaited()


@pytest.mark.asyncio
async def test_retry_stops_after_five_attempts():
    initialize = AsyncMock(side_effect=RuntimeError("still unavailable"))
    with patch("src.services.dependency_recovery.asyncio.sleep", new_callable=AsyncMock) as sleep:
        await retry_dependency("MCP", initialize)
    assert initialize.await_count == 5
    assert [call.args[0] for call in sleep.await_args_list] == [5.0, 10.0, 20.0, 40.0, 60.0]


@pytest.mark.asyncio
async def test_recovery_is_single_flight_and_rearmed_only_after_cooldown():
    manager = DependencyRecovery(cooldown=600)
    initialize = AsyncMock(side_effect=RuntimeError("unavailable"))
    manager.register("MCP", initialize, failed=True)
    with (
        patch("src.services.dependency_recovery.asyncio.sleep", new_callable=AsyncMock),
        patch("src.services.dependency_recovery.time.monotonic", return_value=1000) as now,
    ):
        manager.request_recovery("MCP")
        first_task = manager._tasks["MCP"]
        manager.request_recovery("MCP")
        assert manager._tasks["MCP"] is first_task
        await first_task
        assert initialize.await_count == 5
        manager.request_recovery("MCP")
        assert manager._tasks["MCP"] is first_task
        now.return_value = 1600
        manager.request_recovery("MCP")
        second_task = manager._tasks["MCP"]
        assert second_task is not first_task
        await second_task
        assert initialize.await_count == 10
        await manager.shutdown()
        manager.request_recovery("MCP", failed=True)
        assert manager._tasks["MCP"] is second_task


@pytest.mark.asyncio
async def test_retry_cancels_in_flight_mcp_initialization():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def initialize():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    with patch("src.services.dependency_recovery.asyncio.sleep", new_callable=AsyncMock):
        task = asyncio.create_task(retry_dependency("MCP", initialize))
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert stopped.is_set()


@pytest.mark.asyncio
async def test_cancelled_storage_worker_cannot_publish_late_singleton():
    from src.services import storage

    started, release, finished = threading.Event(), threading.Event(), threading.Event()

    def initialize(_cfg):
        started.set()
        release.wait(timeout=2)
        finished.set()
        return object()

    with patch.object(storage, "_service", None), patch.object(storage, "_create_storage_service", initialize):
        task = asyncio.create_task(storage.async_init_storage_service(MagicMock()))
        assert await asyncio.to_thread(started.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        release.set()
        assert await asyncio.to_thread(finished.wait, 1)
        assert storage._service is None


@pytest.mark.asyncio
@pytest.mark.parametrize("code,should_recover", [("NoSuchBucket", True), ("403", True), ("NoSuchKey", False)])
async def test_runtime_storage_download_failure_signals_without_hiding_error(code, should_recover):
    from src.services import storage

    callback = MagicMock()
    client = MagicMock()
    client.get_object.side_effect = ClientError({"Error": {"Code": code}}, "GetObject")
    service = StorageService.__new__(StorageService)
    service._client = client
    service._bucket = "documents"
    with patch.object(storage, "_failure_callback", callback), patch.object(storage, "_failure_loop", asyncio.get_running_loop()):
        with pytest.raises(ClientError) as error:
            await service.download_file("100/1/file.pdf")
    assert error.value.response["Error"]["Code"] == code
    assert callback.call_count == int(should_recover)


@pytest.mark.asyncio
async def test_uninitialized_storage_getter_signals_recovery_in_event_loop():
    from src.services import storage

    callback = MagicMock()
    with patch.object(storage, "_service", None), patch.object(storage, "_failure_callback", callback), patch.object(storage, "_failure_loop", asyncio.get_running_loop()):
        with pytest.raises(storage.StorageUnavailableError):
            storage.get_storage_service()
    callback.assert_called_once()


def test_uninitialized_storage_getter_does_not_schedule_without_event_loop():
    from src.services import storage

    callback = MagicMock()
    with patch.object(storage, "_service", None), patch.object(storage, "_failure_callback", callback):
        with pytest.raises(storage.StorageUnavailableError):
            storage.get_storage_service()
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_uninitialized_storage_getter_does_not_schedule_on_different_loop():
    from src.services import storage

    callback = MagicMock()

    async def call_getter():
        with pytest.raises(storage.StorageUnavailableError):
            storage.get_storage_service()

    with patch.object(storage, "_service", None), patch.object(storage, "_failure_callback", callback), patch.object(storage, "_failure_loop", asyncio.get_running_loop()):
        await asyncio.to_thread(asyncio.run, call_getter())
    callback.assert_not_called()


def test_invalidating_underwriter_leaves_other_graphs_alone():
    from src.agents import registry

    with patch.dict(registry._graphs, {"underwriter-assistant": ("old", 1), "other": ("ok", 1)}, clear=True):
        with patch.dict(registry._last_check, {"underwriter-assistant": 1, "other": 1}, clear=True):
            registry.invalidate_agent_cache("underwriter-assistant")
            assert "underwriter-assistant" not in registry._graphs
            assert "underwriter-assistant" not in registry._last_check
            assert registry._graphs["other"] == ("ok", 1)


@pytest.mark.asyncio
async def test_lifespan_recovers_both_dependencies_and_rebuilds_graph():
    from src import main
    from src.agents import registry

    storage_ready = asyncio.Event()
    mcp_ready = asyncio.Event()
    storage_attempts = 0
    mcp_attempts = 0

    async def storage_init(_settings):
        nonlocal storage_attempts
        storage_attempts += 1
        if storage_attempts == 1:
            raise RuntimeError("storage cold")
        storage_ready.set()

    async def mcp_init(*_args, **_kwargs):
        nonlocal mcp_attempts
        mcp_attempts += 1
        if mcp_attempts == 1:
            raise RuntimeError("mcp cold")
        mcp_ready.set()

    conversation = MagicMock()
    conversation.initialize = AsyncMock()
    conversation.shutdown = AsyncMock()
    with (
        patch("src.services.conversation.get_conversation_service", return_value=conversation),
        patch("src.services.storage.async_init_storage_service", side_effect=storage_init),
        patch("src.services.extraction.init_extraction_service"),
        patch.object(main, "init_mcp_client", side_effect=mcp_init),
        patch.object(main, "shutdown_mcp_client", new_callable=AsyncMock) as shutdown_mcp,
        patch.object(main, "_auto_seed", new_callable=AsyncMock),
        patch.object(main, "log_safety_status"),
        patch.object(main, "init_mlflow_tracing"),
        patch.object(main, "log_observability_status"),
        patch("src.services.dependency_recovery.asyncio.sleep", new_callable=AsyncMock),
        patch.dict(registry._graphs, {"underwriter-assistant": ("old", 1)}, clear=True),
    ):
        async with main.lifespan(main.app):
            await asyncio.wait_for(storage_ready.wait(), timeout=1)
            await asyncio.wait_for(mcp_ready.wait(), timeout=1)
            assert "underwriter-assistant" not in registry._graphs
        shutdown_mcp.assert_awaited_once()
        conversation.shutdown.assert_awaited_once()
    assert storage_attempts == mcp_attempts == 2


def test_existing_underwriter_websocket_uses_updated_graph_for_next_message(monkeypatch):
    from fastapi.testclient import TestClient
    from langchain_core.messages import AIMessage

    from src.core.config import settings
    from src.main import app
    from src.routes import _chat_handler

    class Graph:
        def __init__(self, answer):
            self.answer = answer

        async def astream_events(self, *_args, **_kwargs):
            yield {
                "event": "on_chain_end",
                "metadata": {"langgraph_node": "agent"},
                "data": {"output": {"messages": [AIMessage(content=self.answer)]}},
            }

    state = SimpleNamespace(graph=Graph("old"))
    recovery = MagicMock()
    monkeypatch.setattr(settings, "AUTH_DISABLED", True)
    monkeypatch.setattr(app.state, "dependency_recovery", recovery, raising=False)
    monkeypatch.setattr(_chat_handler, "get_agent", lambda *_args, **_kwargs: state.graph)
    monkeypatch.setattr(
        _chat_handler, "get_conversation_service",
        lambda: SimpleNamespace(is_initialized=False, checkpointer=None),
    )
    monkeypatch.setattr(_chat_handler, "_build_application_context", AsyncMock(return_value=""))
    monkeypatch.setattr(_chat_handler, "get_safety_checker", lambda: object())
    with TestClient(app).websocket_connect("/api/underwriter/chat") as ws:
        ws.send_json({"type": "message", "content": "first"})
        assert ws.receive_json() == {"type": "done", "content": "old"}
        state.graph = Graph("new")
        ws.send_json({"type": "message", "content": "second"})
        assert ws.receive_json() == {"type": "done", "content": "new"}
    assert recovery.request_recovery.call_count == 2
