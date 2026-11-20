"""Planning & Validation: confirmed places -> checked itineraries (docs/PLANNING.md).

python -m planning build <decision_output.json>
python -m planning variants <decision_output.json> [--weather forecast.json]
python -m planning lodging <decision_output.json> [--weather forecast.json]
python -m planning serve [--port 8768]
"""

from importlib import import_module

_EXPORTS = {
    "build_plan": ("build", "build_plan"), "render_text": ("build", "render_text"),
    "Engine": ("engine", "Engine"), "TripIncomplete": ("engine", "TripIncomplete"), "Store": ("session", "Store"),
    "run_server": ("server", "run"), "Settings": ("settings", "Settings"),
    "load_settings": ("settings", "load"),
    "fork_readonly": ("read", "fork_readonly"),
    **{name: ("variants", name) for name in ("build_lodging_variants", "build_variants", "render_lodging_variants", "render_variants")},
    "Tools": ("tools", "Tools"), "create_engine": ("tools", "create_engine"),
    "PlanningProposal": ("proposal", "PlanningProposal"), "run_proposal": ("proposal", "run_proposal"),
    "EveStore": ("eve", "Store"), "eve_runner": ("eve", "eve_runner"), "run_eve": ("eve", "run_eve"),
    "expert_runner": ("expert", "expert_runner"), "warm_workers": ("overload", "warm"),
}

__all__ = list(_EXPORTS)


def __getattr__(name):
    # Spawned scheduling workers need the clock, not the server's chat / retrieval runtime.
    if name not in _EXPORTS:
        raise AttributeError(name)
    module, attribute = _EXPORTS[name]
    value = getattr(import_module(f".{module}", __name__), attribute)
    globals()[name] = value
    return value
