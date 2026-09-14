"""WebSocket response streaming keeps the final safety decision authoritative."""

from types import SimpleNamespace

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk

from src.core.config import settings
from src.main import app
from src.routes import _chat_handler, chat


class EventGraph:
    def __init__(self, events):
        self.events = events

    async def astream_events(self, *_args, **_kwargs):
        for event in self.events:
            yield event


def _event(kind, node, data):
    return {"event": kind, "metadata": {"langgraph_node": node}, "data": data}


def _connect(monkeypatch, events, *, output_shield=False):
    monkeypatch.setattr(chat, "get_agent", lambda *_args, **_kwargs: EventGraph(events))
    monkeypatch.setattr(
        chat,
        "get_conversation_service",
        lambda: SimpleNamespace(is_initialized=False, checkpointer=None),
    )
    monkeypatch.setattr(
        _chat_handler,
        "get_safety_checker",
        (lambda: object()) if output_shield else (lambda: None),
    )
    monkeypatch.setattr(settings, "OUTPUT_SHIELD_DISABLED", False)
    return TestClient(app)


def test_public_answer_arrives_in_chunks_before_done(monkeypatch):
    events = [
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="申请")}),
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="材料")}),
        _event("on_chain_end", "agent", {"output": {"messages": [AIMessage(content="申请材料")]}}),
    ]
    client = _connect(monkeypatch, events)
    with client.websocket_connect("/api/chat") as ws:
        ws.send_json({"type": "message", "content": "需要什么材料？"})
        assert ws.receive_json() == {"type": "token", "content": "申请"}
        assert ws.receive_json() == {"type": "token", "content": "材料"}
        assert ws.receive_json() == {"type": "done", "content": "申请材料"}


def test_thinking_and_tool_text_never_appear_in_preview(monkeypatch):
    events = [
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="<thi")}),
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="nk>hidden</think>答")}),
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="案[tool()]")}),
        _event(
            "on_chain_end",
            "agent",
            {"output": {"messages": [AIMessage(content="<think>hidden</think>答案[tool()]")]}},
        ),
    ]
    client = _connect(monkeypatch, events)
    with client.websocket_connect("/api/chat") as ws:
        ws.send_json({"type": "message", "content": "问题"})
        assert ws.receive_json() == {"type": "token", "content": "答"}
        assert ws.receive_json() == {"type": "token", "content": "案"}
        assert ws.receive_json() == {"type": "done", "content": "答案"}


def test_tool_draft_is_reset_before_final_answer(monkeypatch):
    events = [
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="先查一下")}),
        _event(
            "on_chain_end",
            "agent",
            {"output": {"messages": [AIMessage(content="先查一下", tool_calls=[{"name": "lookup", "args": {}, "id": "1"}])]}},
        ),
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="已查到结果")}),
        _event("on_chain_end", "agent", {"output": {"messages": [AIMessage(content="已查到结果")]}}),
    ]
    client = _connect(monkeypatch, events)
    with client.websocket_connect("/api/chat") as ws:
        ws.send_json({"type": "message", "content": "问题"})
        assert ws.receive_json() == {"type": "token", "content": "先查一下"}
        assert ws.receive_json() == {"type": "reset"}
        assert ws.receive_json() == {"type": "token", "content": "已查到结果"}
        assert ws.receive_json() == {"type": "done", "content": "已查到结果"}


def test_active_output_shield_blocks_preview(monkeypatch):
    events = [
        _event("on_chat_model_stream", "agent", {"chunk": AIMessageChunk(content="未经审核的回答")}),
        _event("on_chain_end", "agent", {"output": {"messages": [AIMessage(content="未经审核的回答")]}}),
        _event("on_chain_end", "output_shield", {"output": {"messages": [AIMessage(content="安全拒绝")]}}),
    ]
    client = _connect(monkeypatch, events, output_shield=True)
    with client.websocket_connect("/api/chat") as ws:
        ws.send_json({"type": "message", "content": "问题"})
        assert ws.receive_json() == {"type": "done", "content": "安全拒绝"}
