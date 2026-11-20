"""Production regressions for scoped dates and explicit sightseeing hours."""
from datetime import date

import pytest

from trip import TripState, compile_search_input
from trip.api.engine import Engine
from trip.domain import readiness
from trip.domain.guard import record_fact
from trip.domain.prepass import prepass
from trip.domain.required import tabs
from trip.infrastructure.sessions import SessionStore
from trip_fixtures import ScriptedChat
from test_redesign_gate import build
from test_trip_r7 import understand

MULTI = ('Cả nhà mình gồm 2 người lớn, bé 6 tuổi và mẹ mình 65 tuổi, tổng 4 người, '
         'đi Đà Lạt 4 ngày từ 20/11, ô tô có tài xế, mẹ đi chậm nên tránh dốc, '
         'ngày 22/11 mẹ ăn chay, ăn tối sớm trước 6h, mình 9h sáng mới bắt đầu, '
         'ngân sách tầm 900 nghìn một người một ngày.')
FAMILY = ('Nhà chị 4 người gồm chị, chồng, bé 6 tuổi và mẹ chồng 65 tuổi, '
          'đi Đà Lạt 20-22/11 ô tô thuê tài xế. Mẹ đi chậm và ngày 22/11 là ngày rằm '
          'nên mẹ ăn chay cả ngày hôm đó, hai ngày kia ăn bình thường nha.')
CLOUD = 'Nhóm mình muốn săn mây sáng 28/11, còn việc dậy lúc 5:30 thì chưa biết.'


@pytest.fixture
def e(catalog, cfg, tmp_path):
    return Engine(catalog, cfg, SessionStore(tmp_path), ScriptedChat(), today=lambda: date(2026, 11, 4))


@pytest.mark.parametrize('text', [MULTI, FAMILY])
def test_prod_diet_resolves_after_trip_dates(e, text):
    st = understand(e, TripState(), text)
    assert st.start_date.value == date(2026, 11, 20)
    rule, = compile_search_input(st).context.diet_days
    assert (rule.date, rule.subject, rule.member.lower()) == (date(2026, 11, 22), 'member', 'mẹ')
    assert st.diet_requests[0].lunar_day is None
    assert not any(h.feature == 'vegetarian_options' for h in st.hard)


def test_diet_waits_for_dates_then_re_resolves_year(e):
    st = understand(e, TripState(), 'Mẹ ăn chay ngày 22/11.')
    st = understand(e, st, 'Đi Đà Lạt 20-23/11/2026.', turn=2)
    assert [r.date for r in st.diet_days] == [date(2026, 11, 22)]
    st = understand(e, st, 'Đổi sang 20-23/11/2027.', turn=3)
    assert [r.date for r in st.diet_days] == [date(2027, 11, 22)]


def test_separate_people_keep_their_own_diet_dates(e):
    st = understand(e, build(), 'Mẹ ăn chay ngày 21/11, bố ăn chay ngày 22/11.')
    assert {(r.member.lower(), r.date) for r in st.diet_days} == {
        ('mẹ', date(2026, 11, 21)), ('bố', date(2026, 11, 22))}


def test_activity_date_is_kept_as_wish_without_moving_trip(e):
    st = understand(e, build(), 'Mình muốn săn mây sáng 28/11.')
    assert st.start_date.value == date(2026, 11, 20)
    assert any('28/11' in u.phrase for u in st.unmapped)


def test_explicit_solar_year_is_not_changed(e):
    st = understand(e, build(), 'Mẹ ăn chay ngày 22/11/2026.')
    st = understand(e, st, 'Đổi sang 20-23/11/2027.', turn=2)
    assert st.diet_requests[0].date == date(2026, 11, 22)
    assert st.diet_days == ()


def test_unresolved_diet_does_not_repeat_without_progress_but_stays_fail_closed(e, cfg):
    st = understand(e, build(), 'Mẹ ăn chay ngày rằm.')
    assert any(t.qid == 'care' for t in tabs(st, cfg))
    st = understand(e, st, 'Sao cũng được em nhé.', turn=2)
    assert not any(t.qid == 'care' for t in tabs(st, cfg))
    assert 'care' in dict(readiness.missing(st))
    st = understand(e, st, 'Ngày 22/11.', turn=3)
    assert [r.date for r in st.diet_days] == [date(2026, 11, 22)]


def test_skip_diet_gate_does_not_repeat_or_waive_constraint(e, cfg):
    from trip.api.engine import TurnInput
    sid = e.create('first', 'nothing')['id']
    session = e.store.get(sid)
    session.state = understand(e, build(), 'Mẹ ăn chay ngày rằm.')
    session.card = None
    e.store.save(session)
    e.turn(sid, TurnInput(kind='deck', answers={'care': ['skip']}), lambda *_: None)
    st = e.store.get(sid).state
    assert not any(t.qid == 'care' for t in tabs(st, cfg))
    assert 'care' in dict(readiness.missing(st))
    assert st.diet_requests


def test_same_diet_subject_answer_is_not_progress(e, cfg):
    st = understand(e, build(), 'Mẹ ăn chay ngày rằm.')
    st = understand(e, st, 'Mẹ.', turn=2)
    assert st.meta.diet_stalled
    assert not any(t.qid == 'care' for t in tabs(st, cfg))


def test_stalled_diet_cannot_be_reasked_by_agent(e):
    from trip.agent.tools import TurnTools
    st = understand(e, build(), 'Mẹ ăn chay ngày rằm.')
    st = understand(e, st, 'Sao cũng được em nhé.', turn=2)
    tools = TurnTools(st, 'Sao cũng được em nhé.', 2, e.catalog, e.today())
    with pytest.raises(ValueError, match='unchanged'):
        tools._ask_required({'topic': 'care', 'question': 'Ngày nào mẹ ăn chay?'})


def test_find_tool_persists_nested_spans_and_cache_hit(knowledge, e):
    from trip.agent.tools import TurnTools
    tools = TurnTools(TripState(), 'Quán bánh căn nào ngon thật của người địa phương vậy bạn?',
                      2, knowledge.catalog, e.today(), knowledge=knowledge)
    tools._find_places({'criteria': {'groups': ['cafe']}})
    tools._find_places({'criteria': {'groups': ['cafe']}})
    assert any('stage=knowledge ' in s for s in tools.timings)
    assert any('t_find reuse=1' in s for s in tools.timings)
    assert any('find_criteria ' in s for s in tools.timings)


def test_camping_activity_date_does_not_move_trip(e):
    st = understand(e, TripState(), 'Nhóm mình 8 người đi Đà Lạt 27-28/11, thuê xe 16 chỗ từ TP.HCM.')
    st = understand(e, st, CLOUD, turn=2)
    assert st.start_date.value == date(2026, 11, 27)
    assert st.days.value == 2
    assert not any(p.field == 'start_date' for p in prepass(CLOUD, e.today()).proposals)
    updated, note = record_fact(st, 'start_date', 'set', '2026-11-28', '28/11', 'said', CLOUD, 2, e.catalog)
    assert updated.start_date.value == st.start_date.value
    assert note.startswith('refused:')


@pytest.mark.parametrize('text,hour', [
    ('9h sáng bắt đầu.', '09:00'),
    ('mình 9h sáng mới bắt đầu', '09:00'),
    ('Sáng 6h mỗi ngày mình dậy đi.', '06:00'),
    ('2h chiều bắt đầu.', '14:00'),
])
def test_explicit_start_is_user_confirmed(e, text, hour):
    st = understand(e, build(drop=('checkin_at',)), text)
    assert st.checkin_at.value == hour and st.checkin_at.source == 'user'
    assert readiness.boundary_answered(st, 'start')
    if 'mỗi ngày' in text:
        assert st.frame.day_start.value == hour and st.frame.day_start.source == 'user'


def test_retrieval_trace_preserves_results_and_reports_stages(knowledge):
    from corpus.retrieval import trace_reads
    lines = []
    with trace_reads(lines.append):
        first = knowledge.find({'groups': ['cafe'], 'sort': 'fit'}, TripState())
        second = knowledge.find({'groups': ['cafe'], 'sort': 'fit'}, TripState())
    assert first == second
    for stage in ('knowledge', 'reads', 'warm', 'filter', 'semantic', 'card'):
        assert any(f'stage={stage} ' in line for line in lines)
    assert any('stage=warm ' in line and 'cache_hit=1' in line for line in lines)


def test_dish_normalization_is_lazy_and_only_for_filtered_places(retrieval, monkeypatch):
    import importlib
    module = importlib.import_module('corpus.retrieval.find')
    calls = []
    original = module.menu.key_for
    monkeypatch.setattr(module.menu, 'key_for', lambda *args: (calls.append(args), original(*args))[1])
    retrieval.find({'groups': ['cafe']})
    assert calls == []
    retrieval.find({'groups': ['cafe'], 'dish': 'bánh căn'})
    # The query and candidate names may normalize, but excluded groups never do.
    first = len(calls)
    retrieval.find({'groups': ['cafe'], 'dish': 'bánh căn'})
    assert all(args[0] == 'bánh căn' for args in calls[first:])


def test_dish_normalization_reuses_identical_names(retrieval, monkeypatch):
    import importlib
    module = importlib.import_module('corpus.retrieval.find')
    original = module.menu.key_for
    seen = set()
    repeated = []
    def counted(text, accented=False):
        key = (text, accented)
        if key in seen:
            repeated.append(key)
        seen.add(key)
        return original(text, accented)
    monkeypatch.setattr(module.menu, 'key_for', counted)
    monkeypatch.setattr(module.menu, 'rows_of', lambda rec: [('menu', ['Bánh căn', 'Bánh căn'])])
    retrieval.find({'groups': ['cafe']})
    assert not repeated


@pytest.mark.parametrize('quote', ['7h xuất phát', '8h xuất phát', 'sáng 8h đi'])
def test_departure_is_not_sightseeing_start(e, quote):
    st = understand(e, build(drop=('checkin_at',)), quote)
    assert not st.checkin_at.known
    st, note = record_fact(st, 'frame.arrive', 'set', '2026-11-20T07:00',
                           quote, 'said', quote, 2, e.catalog)
    assert not st.checkin_at.known and not st.frame.arrive.known
    assert note.startswith('refused:')
    st, note = record_fact(st, 'checkin_at', 'set', '07:00', quote, 'said', quote, 2, e.catalog)
    assert not st.checkin_at.known
    assert note.startswith('refused:')
