"""Shared assistant core: tool registry, per-turn cache and cards, the tool loop, context window, Clef rule guard.

Trip and Decision plug their action tools and CURRENT CONTEXT blocks into it (src/agents/assistant/registry.py).
"""

from .registry import REGISTRY, Registry, Tool, action_tool, context_block, read_tool
from .context import HISTORY_DROP, HISTORY_KEEP, context_message, last_shown, window
from .guard import Guarded, Verdict, check as check_rules, reply as rule_reply
from .loop import ASSISTANT_CALLS, Chat, ChatSettings, LoopHost, langchain_chat, run_loop
from .turn import TurnCore, public

__all__ = ["Guarded", "Verdict", "check_rules", "rule_reply", "ASSISTANT_CALLS", "Chat", "ChatSettings", "LoopHost", "langchain_chat", "run_loop", "HISTORY_DROP", "HISTORY_KEEP", "context_message", "last_shown", "window", "REGISTRY", "Registry", "Tool", "TurnCore", "action_tool", "context_block", "public", "read_tool"]
