"""Pet access is a venue restriction, not a preference that a relaxed pick can override."""

from requirements import hard_result

REQUIREMENT = {'feature': 'pets', 'op': 'ne', 'value': 'not_allowed', 'unknown_policy': 'flag', 'scope': 'all'}
UNKNOWN_TEXT = 'chưa rõ có cho mang thú cưng không'


def filters(trip_context: dict) -> list[dict]:
    hard = [{**f, 'scope': 'all'} if f['feature'] == 'pets' else f
            for f in trip_context.get('hard_filters') or []]
    if 'pet' in (trip_context.get('context', {}).get('companions') or []) and not any(
            f['feature'] == 'pets' and f['op'] == 'ne' and f['value'] == 'not_allowed' for f in hard):
        hard.append(REQUIREMENT)
    return hard


def warnings(places, hard: list[dict]) -> list[dict]:
    if not any(f['feature'] == 'pets' for f in hard):
        return []
    out = []
    for p in places:
        result = hard_result(p.rec, REQUIREMENT, p.activity, p.kind)[0]
        if result == 'unknown':
            out.append({'code': 'pets_unknown', 'place_id': p.id,
                        'text': f'{p.name}: {UNKNOWN_TEXT}. Hãy hỏi địa điểm trước khi đến.'})
        elif result == 'fail':
            resolution = 'Bỏ nơi này khỏi lịch hoặc chọn nơi cho mang thú cưng; không thể nới quy định của địa điểm.'
            out.append({'code': 'plan_violation', 'place_id': p.id, 'rule': 'hard', 'feature': 'pets', 'resolution': resolution,
                        'text': f'{p.name}: nơi này cấm thú cưng; bạn vẫn có thể chốt nếu muốn. {resolution}'})
    return out
