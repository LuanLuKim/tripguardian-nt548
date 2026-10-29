"""Phase price: Trip.com's price for the trip dates, a cross-check on Google Travel -> data/tripcom/<city>/.

The city's hotel list URL honours the dates (checkin / checkout / adult) and is server-rendered, so a plain HTTP GET
is enough: no browser, no login, no evasion. A call returns only ~12 popular hotels in shuffled order (keyword and
paging parameters are ignored), so each date is asked `calls_per_date` times and the hotels are merged. Hotels are
matched to the corpus lodging by name and distance (common.lodging.match); the rest go to unmatched.jsonl. Writes
observations.jsonl, unmatched.jsonl, runs.jsonl, errors.jsonl.
"""

import random
import time
from collections.abc import Callable

import httpx

from ..common import lodging
from ..common.files import append_jsonl, data_dir, load_config, log_error, now
from .parser import Hotel, parse_list

SOURCE = "tripcom"
LIST = "https://vn.trip.com/hotels/list?city={city_id}&checkin={checkin}&checkout={checkout}&adult={adults}&crn=1&curr=VND"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36",
           "Accept-Language": "vi-VN,vi;q=0.9"}


def list_url(city_id: int, stay: lodging.Stay) -> str:
    return LIST.format(city_id=city_id, checkin=stay.checkin.isoformat(), checkout=stay.checkout.isoformat(), adults=stay.adults)


def observation(hotel: Hotel, m: lodging.Match, stay: lodging.Stay) -> dict:
    """A matched hotel's observation. A price counts only for the dates asked: Trip.com states the offer's own dates."""
    ok = hotel.price_total_vnd and hotel.checkin == stay.checkin.isoformat() and hotel.nights == stay.nights
    total, night = (hotel.price_total_vnd, hotel.price_night_vnd) if ok else (None, None)
    return {"fid": m.fid, "price_total_vnd": total, "price_night_vnd": night, "currency": "VND",
            "available": True if total else None, "stay_date": stay.checkin.isoformat(), "nights": stay.nights,
            "adults": stay.adults, "observed_at": now(), "source": SOURCE, "url": hotel.url,
            "matched_name": hotel.name, "match_score": m.score}


def fetch(url: str, timeout: float) -> str:
    r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
    r.raise_for_status()
    return r.text


def run(city: str, limit: int | None = None, get: Callable[[str, float], str] = fetch, sleep=time.sleep) -> dict:
    cfg = lodging.settings(city)
    tc = cfg["tripcom"]
    if city not in tc["city_ids"]:
        raise SystemExit(f"config lodging_price.tripcom.city_ids has no {city!r}")
    city_name = load_config(city)[0]
    root = data_dir() / SOURCE / city
    stays, corpus = lodging.stay_dates(cfg), lodging.load_stays(city)
    calls = [s for s in stays for _ in range(tc["calls_per_date"])][:limit]
    stats = {"calls": 0, "hotels": 0, "matched": 0, "priced": 0, "unmatched": 0, "errors": 0}
    done: set[tuple[str, str, int]] = set()
    t0 = time.monotonic()
    for stay in calls:
        url = list_url(tc["city_ids"][city], stay)
        try:
            hotels = parse_list(get(url, tc["timeout_s"]))
            if not hotels:
                raise ValueError("no hotelList in the page")
        except Exception as e:
            stats["errors"] += 1
            log_error(root, f"{stay.checkin}+{stay.nights}", "list", e)
            sleep(random.uniform(*tc["pause_s"]))
            continue
        stats["calls"] += 1
        for h in hotels:
            key = (h.id, stay.checkin.isoformat(), stay.nights)
            if key in done:
                continue
            done.add(key)
            stats["hotels"] += 1
            m = lodging.match(h.name, h.lat, h.lng, corpus, city_name, cfg["match"])
            if m.fid is None:
                stats["unmatched"] += 1
                lodging.append_unmatched(SOURCE, city, {"hotel_id": h.id, "name": h.name, "lat": h.lat, "lng": h.lng,
                                                         "stay_date": stay.checkin.isoformat(), "nights": stay.nights,
                                                         "price_total_vnd": h.price_total_vnd, "url": h.url,
                                                         "best_score": m.score})
                continue
            obs = observation(h, m, stay)
            lodging.append_observation(SOURCE, city, obs)
            stats["matched"] += 1
            stats["priced"] += bool(obs["price_night_vnd"])
        sleep(random.uniform(*tc["pause_s"]))
    stats["seconds"] = round(time.monotonic() - t0, 1)
    append_jsonl(root / "runs.jsonl", {"at": now(), **stats})
    print(f"tripcom price {city}: {stats}")
    return stats
