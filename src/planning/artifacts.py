"""JSON snapshots of offered search results; replay must not rerun a timed search."""

from dataclasses import fields, is_dataclass
from datetime import date

from .conditions import DayCond
from .model import Day, DayResult, Item, Place, Violation
from .schedule import DayCtx
from .settings import Settings
from .travel import Travel

_TYPES = {cls.__name__: cls for cls in (DayCond, Day, DayResult, Item, Place, Violation, DayCtx, Settings, Travel)}


def encode(value):
    if is_dataclass(value):
        return {'$type': type(value).__name__, 'fields': {
            f.name: encode(getattr(value, f.name)) for f in fields(value) if f.init}}
    if isinstance(value, date):
        return {'$date': value.isoformat()}
    if isinstance(value, (tuple, set, frozenset)):
        return {'$sequence': type(value).__name__, 'items': [encode(v) for v in value]}
    if isinstance(value, dict):
        return {'$map': [[encode(k), encode(v)] for k, v in value.items()]}
    if isinstance(value, list):
        return [encode(v) for v in value]
    return value


def decode(value):
    if isinstance(value, list):
        return [decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    if '$type' in value:
        return _TYPES[value['$type']](**{k: decode(v) for k, v in value['fields'].items()})
    if '$date' in value:
        return date.fromisoformat(value['$date'])
    if '$sequence' in value:
        return {'tuple': tuple, 'set': set, 'frozenset': frozenset}[value['$sequence']](decode(value['items']))
    if '$map' in value:
        return {decode(k): decode(v) for k, v in value['$map']}
    raise ValueError('invalid planning search snapshot')
