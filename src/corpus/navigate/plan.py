"""Phase `navigate plan`: one sol call per city, from the city name and area alone, gated into data/<city>/navigate/.

sol is not shown the corpus, the ontology or any query (that is the point: compare.py checks what it proposes against
what we hold). The map it returns is a proposal; nothing here reaches the ontology, the config or the corpus.
"""

from datetime import UTC, datetime

from ..llm import NAVIGATOR_PLAN
from .common import NavigateError, city_info, navigate_dir, stamp, write_json
from .schema import GeneralClaim, MiningMap, parse_answer

LATEST = "mining_map.json"


def map_path(city: str, name: str = LATEST):
    return navigate_dir(city) / name


def load_map(city: str, path=None) -> MiningMap | None:
    """The latest mining map of the city (or the file at `path`), None when there is none yet."""
    path = path or map_path(city)
    if not path.exists():
        return None
    return MiningMap.model_validate_json(path.read_text(encoding="utf-8"))


def general_claims(city: str) -> list[GeneralClaim]:
    """sol's general knowledge of the city in the latest map, each claim `source = "model"` (corpus P4 gives the
    status confirmed / contradicted / unverified; it never turns one into a fact about a venue)."""
    m = load_map(city)
    return m.general_claims if m else []


async def plan(city: str, *, client=None, model: str | None = None, now: datetime | None = None,
               latest: bool = True) -> MiningMap:
    """Ask sol for the city's mining map, gate it, write `mining_map_<ts>.json` and (when `latest`) `mining_map.json`.
    A map with no valid aspect raises NavigateError and never replaces the latest one."""
    name, area = city_info(city)
    if client is None:
        client, model = NAVIGATOR_PLAN.role.client()
    if not model:
        raise NavigateError("plan needs the model name that answers (the NAVIGATOR role gives it)")
    now = now or datetime.now(UTC)
    answer = await NAVIGATOR_PLAN.ask(client, model, city=name, area=f"{area[0]},{area[1]} to {area[2]},{area[3]}")
    result = parse_answer(city, answer, answer.get("_model", model), now.isoformat(timespec="seconds"))
    out = navigate_dir(city)
    write_json(out / f"mining_map_{stamp(now)}.json", result.model_dump(mode="json"))
    if not result.aspects:
        raise NavigateError(f"sol returned no valid aspect ({len(result.rejected)} rejected); see the stamped map in {out}")
    if latest:
        write_json(out / LATEST, result.model_dump(mode="json"))
    return result
