"""The assistant's tools for what the user shows or pastes: photo_identify, photo_similar, place_photos, link_resolve,
more_like_shown (docs/TRIP_UNDERSTANDING.md §20). Registered in agents.assistant like every read tool; the work is
infrastructure.perceive.Perceiver (set on Knowledge by api/tools.py). A photo is a record the engine made when it arrived
(turn.photos): the picture is never kept."""

from __future__ import annotations

from agents.assistant import read_tool

from .tool_schemas import LinkResolve, MoreLikeShown, PhotoIdentify, PhotoSimilar, PlacePhotos

GROUP = "perceive"
SHOWN = 6  # places a photo_similar / more_like_shown result carries (and shows as cards)


def _perceiver(turn):
    perceiver = getattr(turn.knowledge, "perceiver", None)
    if perceiver is None:
        raise ValueError("photos and links cannot be read now: ask the user for the place name")
    return perceiver


def _ids_of(key: str):
    """Cards of a result: the ids in result[key] (a list of cards)."""
    return lambda turn, result: [p["id"] for p in result.get(key) or () if isinstance(p, dict) and p.get("id")]


def _identity_cards(turn, result: dict) -> list[str]:
    place = result.get("place")
    return [place["id"]] if isinstance(place, dict) and place.get("id") else []


@read_tool(PhotoIdentify, group=GROUP, cards=_identity_cards)
def photo_identify(turn, inp: PhotoIdentify) -> dict:
    return _perceiver(turn).photo_identify(turn.photos, inp.photo_id, turn.state)


@read_tool(PhotoSimilar, group=GROUP, cards=_ids_of("places"))
def photo_similar(turn, inp: PhotoSimilar) -> dict:
    return _perceiver(turn).photo_similar(turn.photos, inp.photo_id, turn.state, inp.criteria, SHOWN)


@read_tool(PlacePhotos, group=GROUP, place_args=("id",), cards=lambda turn, r: [r["id"]] if r.get("photos") else [])
def place_photos(turn, inp: PlacePhotos) -> dict:
    out = _perceiver(turn).place_photos(inp.id, inp.scene)
    if out.get("photos") and inp.scene:
        turn.scene_first[inp.id] = inp.scene  # the card shows that scene's photo first
    return out


@read_tool(LinkResolve, group=GROUP, cards=lambda turn, r: [r["place"]["id"]] if isinstance(r.get("place"), dict) else
           [p["id"] for p in r.get("places") or () if isinstance(p, dict) and p.get("id")])
def link_resolve(turn, inp: LinkResolve) -> dict:
    return _perceiver(turn).link_resolve(inp.url, turn.state)


@read_tool(MoreLikeShown, group="places", cards=_ids_of("places"), cache=False)
def more_like_shown(turn, inp: MoreLikeShown) -> dict:
    return _perceiver(turn).more_like_shown(turn.shown_log, turn.state, inp.turn, inp.criteria_delta, SHOWN)
