import pytest
from trip_fixtures import MONDAY_CLOSED, rec

from trip.api import engine
from trip.infrastructure.catalog import Catalog
from trip.infrastructure.settings import Settings


@pytest.fixture(autouse=True)
def no_live_turn_log(tmp_path, monkeypatch):
    """Tests write their turns to a temp file, never to the live logs/run/trip_turns.log."""
    monkeypatch.setattr(engine, "TURN_LOG", tmp_path / "trip_turns.log")


@pytest.fixture
def records():
    quiet = [rec(i, f"Quán Yên Tĩnh Số {i}", {"noise": ("quiet", 5), "long_stay_chill": ("present", 4),
                                               "crowd": ("low", 3)}) for i in range(1, 7)]
    loud = [rec(i, f"Quán Nhạc Sống {i}", {"noise": ("loud", 5), "live_music": ("present", 6),
                                            "crowd": ("high", 4)}) for i in range(7, 13)]
    steep = [rec(i, f"Đồi Dốc Cao {i}", {"steep_or_stairs": ("present", 3), "scenic_view": ("present", 9),
                                          "photo_spot": ("present", 4)}) for i in range(13, 17)]
    flat = [rec(17, "Vườn Phẳng Lặng Xanh", {"steep_or_stairs": ("absent", 2), "scenic_view": ("present", 3)},
                hours=MONDAY_CLOSED)]
    other = [rec(i, f"Chợ Phiên Đêm {i}", {"local_specialty_food": ("present", 5)}) for i in range(18, 22)]
    return quiet + loud + steep + flat + other


@pytest.fixture
def catalog(records):
    return Catalog.from_records(records, n_min=1, videos={"7565853238147255573": "0x11:0x1"})


@pytest.fixture
def cfg():
    return Settings(n_min=1, top_k=4, enough_factor=1.0)


# ---------- the Đà Lạt assistant (plan 2026-10-28-trip-decision-chatbot) ----------

@pytest.fixture
def served_records():
    from trip_fixtures import served
    return [served("0xa:0x1", "Cà Phê Đồi Thông Xanh", {"kids": "suitable", "scenic_view": "present"}, voices=90),
            served("0xb:0x1", "Quán Nhạc Ồn Ào", {"kids": "unsuitable"}, voices=80, lat=11.95, lng=108.45),
            served("0xc:0x1", "Tiệm Chưa Rõ Trẻ Em", {"scenic_view": "present"}, voices=70),
            served("0xd:0x1", "Đồi Chè Cầu Đất Farm", {"kids": "suitable"}, group="nature", category="Đồi chè",
                   lat=11.86, lng=108.56, voices=60),
            served("0xe:0x1", "Khách Sạn Đồi Chè", {}, group="stay", category="Khách sạn", voices=50),
            served("0xf:0x1", "Len Shop", {}, voices=10)]  # "lên" in a message must not find it


@pytest.fixture
def served_catalog(served_records):
    return Catalog.from_records([], 1, evidence={r["id"]: r for r in served_records})


@pytest.fixture
def retrieval(served_records):
    from unittest.mock import MagicMock
    from corpus import load_ontology
    from corpus.retrieval import RetrievalEngine
    from corpus.snapshot import Region
    return RetrievalEngine(_index=None, _snapshot=MagicMock(), _region=Region.from_records(served_records),
                           _ontology=load_ontology(), release_id="r-test")


@pytest.fixture
def make_knowledge(retrieval, served_catalog):
    from trip.infrastructure.knowledge import Knowledge, LiveTools

    def make(live=LiveTools()):
        return Knowledge(retrieval, served_catalog, live, ("Chợ Đà Lạt", 11.9429, 108.4372))
    return make


@pytest.fixture
def knowledge(make_knowledge):
    from trip.infrastructure.knowledge import LiveTools
    weather = lambda lat, lng, days: {d: {"rain_prob": 0.4, "rain_mm": 2.5, "source": "open-meteo",  # noqa: E731
                                          "fetched_at": "2026-10-28T08:00:00Z"} for d in days}
    matrix = lambda pts: {"minutes": [[0, 25], [25, 0]], "source": "osrm", "fetched_at": "2026-10-28T08:00:00Z"}  # noqa: E731
    return make_knowledge(LiveTools(weather=weather, matrix=matrix))


@pytest.fixture
def knowledge_no_live(make_knowledge):
    return make_knowledge(None)


@pytest.fixture
def kids_hard_state():
    from trip.domain.state import Evidence, Hard, TripState
    return TripState(hard=(Hard(feature="kids", op="ne", value="unsuitable", unknown_policy="exclude",
                                evidence=(Evidence(turn=1, quote="đi với bé 3 tuổi"),)),))


@pytest.fixture
def turn_tools(knowledge, served_catalog, tmp_path):
    from datetime import date
    from trip.agent.tools import TurnTools
    from trip.domain.state import TripState

    def make(assistant=True, state=None, text="Gợi ý quán cà phê view đồi", know=knowledge):
        return TurnTools(state or TripState(), text, 1, served_catalog, date(2026, 10, 28), knowledge=know,
                         assistant=assistant, gaps=tmp_path / "gaps.jsonl")
    return make


@pytest.fixture
def turn_tools_slow_weather(make_knowledge, served_catalog, tmp_path):
    import time
    from datetime import date
    from trip.agent.tools import TurnTools
    from trip.domain.state import TripState
    from trip.infrastructure.knowledge import LiveTools

    def slow(lat, lng, days):
        time.sleep(0.6)
        return {d: {"rain_prob": 0.7, "source": "open-meteo", "fetched_at": "2026-10-28T08:00:00Z"} for d in days}
    return TurnTools(TripState(), "mai có mưa không", 1, served_catalog, date(2026, 10, 28),
                     knowledge=make_knowledge(LiveTools(weather=slow)), assistant=True, gaps=tmp_path / "gaps.jsonl")


@pytest.fixture
def make_assistant(served_catalog, knowledge, tmp_path):
    """An Engine with the assistant on, over the served-record fixture; make(chat) -> Engine."""
    from datetime import date
    from trip.api.engine import Engine
    from trip.infrastructure.sessions import SessionStore
    from trip.infrastructure.settings import Assistant

    def make(chat, assistant=True):
        cfg = Settings(n_min=1, top_k=4, enough_factor=1.0, assistant=Assistant(enabled=assistant),
                       gaps_path=str(tmp_path / "gaps.jsonl"))
        return Engine(served_catalog, cfg, SessionStore(None), chat, today=lambda: date(2026, 10, 28),
                      knowledge=knowledge)
    return make
