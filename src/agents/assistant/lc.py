"""A turn's registered tools as LangChain tools."""

import json
import logging

from langchain_core.tools import BaseTool, tool

from .turn import TurnCore

log = logging.getLogger(__name__)


def langchain_tools(turn: TurnCore) -> list[BaseTool]:
    """This turn's tools as LangChain tools. Each takes its input model as the schema, so a call with an unknown key
    or a wrong type is refused before it runs; the rules themselves stay in the turn's `run`. What the model's call
    returns is also what the user may see first: its places go out as cards (TurnCore.model_called)."""
    def make(name: str) -> BaseTool:
        spec = turn.tool(name)

        def run_tool(**args) -> str:
            args = {k: v for k, v in args.items() if v is not None}  # an optional field left out is absent, not None
            try:
                return json.dumps(turn.model_called(name, turn.run(name, args), args), ensure_ascii=False)
            except Exception as e:  # a bug in a tool must not kill the turn: the model reads it and goes on
                log.exception("tool %s crashed", name)
                turn.log.append(f"tool_crash {name} {type(e).__name__}")
                return json.dumps({"error": f"internal error in {name}; try another way or reply without it"},
                                  ensure_ascii=False)
        return tool(name, args_schema=spec.model, description=spec.description)(run_tool)
    return [make(n) for n in turn.tool_names()]
