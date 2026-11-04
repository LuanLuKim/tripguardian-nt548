"""Late physical limits preserve choices and travel through public module contracts with explicit warnings."""
import pytest

from decision import Data, Engine, Store, Tools, load_settings
from fixtures import hard, si, srec


@pytest.mark.parametrize('value, status', [('present', 'fail'), (None, 'unknown')])
def test_late_health_keeps_selection_and_warns_in_planning_handoff(value, status):
    record = srec('hill', name='Đồi đã chọn', features={'long_walk': value} if value else {})
    tools = Tools(Engine(Data([record]), load_settings(), Store(None)))
    created = tools.create({'search_input': si().model_dump(mode='json')})
    sid = created['id']
    tools.apply(sid, 'act', {'type': 'select', 'place_id': 'hill'}, lambda *_: None)
    search = si(hard_filters=[hard('long_walk', 'present')]).model_dump(mode='json')
    rebased = tools.rebase(sid, {'search_input': search})
    assert rebased['view']['selected'] == ['hill']
    output = tools.apply(sid, 'confirm', {'for_planning': True}, lambda *_: None)
    chosen = next(p for p in output['confirmed'] if p['id'] == 'hill')
    flags = ' '.join(chosen['flags'])
    assert 'Đồi đã chọn' in flags
    assert ('chưa xác minh được' if status == 'unknown' else 'không đáp ứng') in flags
    assert 'Lịch trình' in flags
    assert output['trip_context']['hard_filters'][0]['unknown_policy'] == 'exclude'
