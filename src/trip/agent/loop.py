"""The Trip agent loop: the shared tool loop (agents.assistant.loop) with Trip's rules (agent/rules.py)."""

from agents.assistant.loop import ASSISTANT_CALLS, MAX_TOOL_FAILS, Chat, ChatSettings, Visible, persisted, run_loop
from agents.assistant.loop import langchain_chat as shared_chat

from ..infrastructure.settings import Settings
from .rules import CLAIM, NOTE_HEADS, REPLY_NOTE, RETRY_NOTE, UNMAPPED_TEXT_NOTE

__all__ = ["ASSISTANT_CALLS", "CLAIM", "MAX_TOOL_FAILS", "NOTE_HEADS", "REPLY_NOTE", "RETRY_NOTE", "UNMAPPED_TEXT_NOTE",
           "Chat", "Visible", "langchain_chat", "persisted", "run_loop"]


def langchain_chat(cfg: Settings) -> Chat:
    """The shared chat on Trip's settings: the service tier is sent only while the assistant is on."""
    return shared_chat(ChatSettings(total_s=cfg.total_s, max_tokens=cfg.max_tokens, cache_key="trip_turn",
                                    service_tier=cfg.assistant.service_tier if cfg.assistant.enabled else ""))
