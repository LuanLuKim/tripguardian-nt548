"""planning.proposal: the typed boundary of a model proposal. "Tối ưu lịch" no longer asks a model
(test_planning_optimize.py); the schema stays for the sessions whose log replays a `recommend` proposal."""

import pytest
from plan_fixtures import CFG


def test_wrapper_uses_structured_schema_and_stream_deadlines():
    import asyncio
    from dataclasses import replace
    from planning.proposal import run_proposal
    from agents import AgentError
    async def valid(fields):
        yield '{"fingerprint":"f","variant_id":"v1","acts":[],"reasons":[]}'
    assert asyncio.run(run_proposal({}, CFG, valid)).variant_id == 'v1'
    async def slow(fields):
        await asyncio.sleep(.05)
        yield '{}'
    with pytest.raises(AgentError):
        asyncio.run(run_proposal({}, replace(CFG, first_token_s=.001, total_s=.01), slow))

