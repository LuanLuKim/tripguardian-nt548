"""python -m corpus {login <source> | <source> <phase> | judge <phase> | navigate <plan|compare> | local <extract|group> | review | aggregate | serving | snapshot | index | views <climate|calendar|restricted|all> | pulse} --city <key>

Phases per source, each reading only earlier phases' files: tiktok search -> list -> filter -> crawl, then per Maps
place place_search -> place_filter -> place_crawl -> asr -> asr_check -> asr_alt -> (asr_check again) -> place_verify
-> place_poi -> poi_crawl -> (asr, asr_check, place_verify again) -> clips -> comments_crawl (comments only for
place_verify's "yes" videos); gmaps search -> filter -> counts -> list -> crawl -> relevant -> qc -> observe; `all` runs them in order. judge dedup -> status -> audit (corpus.judge) runs after
observe and before aggregate. gmaps resolve (nominees from `navigate compare` -> Maps lookup -> search/<city>/resolve.jsonl, then filter -> counts -> list gate them) runs before filter. web search -> documents (SearXNG, no browser) writes video URLs, discover slugs and
Documents under data/web/<city>/.
"""

import argparse
import asyncio
import pathlib

from .crawl.common import browser
from .aggregate import run as aggregate_run
from .serving import run as serving_run
from . import build, judge, navigate, pulse, views
from .review import server as review_server
from .crawl.gmaps import counts as gmaps_counts, crawl as gmaps_crawl, filter as gmaps_filter, listing as gmaps_list, qc as gmaps_qc, relevant as gmaps_relevant, extremes as gmaps_extremes, keywords as gmaps_keywords, visit as gmaps_visit, services as gmaps_services, search as gmaps_search, stay_price as gmaps_stay_price, resolve as gmaps_resolve
from .observe import gmaps as gmaps_observe
from .observe.gmaps import photos as gmaps_photo_observe
from .observe.gmaps import styles as gmaps_style_observe
from .observe.gmaps import scenes as gmaps_photo_scenes
from .observe.gmaps import menu_read as gmaps_menu_read
from .observe.gmaps import dish_check as gmaps_dish_check
from .observe import tiktok as tiktok_observe
from .crawl.gmaps import photos as gmaps_photos
from .crawl.gmaps import menu as gmaps_menu
from .crawl.official import pages as official_pages
from .observe import official as official_observe
from .observe import reports as reports_observe
from .crawl.web import discover as web_discover, documents as web_documents
from .crawl import gflights, gtravel, tripcom
from .crawl.tiktok import (asr as tiktok_asr, asr_alt as tiktok_asr_alt, asr_check as tiktok_asr_check,
                           comments_crawl as tiktok_comments_crawl, crawl as tiktok_crawl,
                           filter as tiktok_filter, listing as tiktok_list, place_verify as tiktok_place_verify,
                           place_crawl as tiktok_place_crawl, place_filter as tiktok_place_filter, place_poi as tiktok_place_poi,
                           poi_crawl as tiktok_poi_crawl, clips as tiktok_clips, web_videos as tiktok_web_videos,
                           place_search as tiktok_place_search, search as tiktok_search)

PHASES = {  # source -> phase -> (run, needs a browser)
    "tiktok": {"search": (tiktok_search.run, True), "list": (tiktok_list.run, False), "filter": (tiktok_filter.run, False),
               "crawl": (tiktok_crawl.run, True), "place_search": (tiktok_place_search.run, True),
               "place_filter": (tiktok_place_filter.run, False), "place_crawl": (tiktok_place_crawl.run, True),
               "asr": (tiktok_asr.run, False), "asr_check": (tiktok_asr_check.run, False),
               "asr_alt": (tiktok_asr_alt.run, False),
               "place_verify": (tiktok_place_verify.run, False), "place_poi": (tiktok_place_poi.run, False),
               "poi_crawl": (tiktok_poi_crawl.run, True), "web_videos": (tiktok_web_videos.run, True),
               "clips": (tiktok_clips.run, False),
               "comments_crawl": (tiktok_comments_crawl.run, True),
               "observe": (tiktok_observe.run, False)},
    "gmaps": {"search": (gmaps_search.run, True), "stay_search": (gmaps_search.run_stay, True), "resolve": (gmaps_resolve.run, True), "filter": (gmaps_filter.run, False), "counts": (gmaps_counts.run, True),
              "list": (gmaps_list.run, False), "svc_search": (gmaps_services.run_search, True), "svc_list": (gmaps_services.run_list, False), "svc_place": (gmaps_services.run_place, True), "stay_price": (gmaps_stay_price.run, True),
              "crawl": (gmaps_crawl.run, True), "relevant": (gmaps_relevant.run, True), "extremes": (gmaps_extremes.run, True),
              "keywords": (gmaps_keywords.run, True), "visit": (gmaps_visit.run, True),
              "photos": (gmaps_photos.run, True), "menu": (gmaps_menu.run, True), "qc": (gmaps_qc.run, False),
              "observe": (gmaps_observe.run, False), "photo_observe": (gmaps_photo_observe.run, False),
              "style_observe": (gmaps_style_observe.run, False), "photo_scenes": (gmaps_photo_scenes.run, False),
              "menu_read": (gmaps_menu_read.run, False), "dish_check": (gmaps_dish_check.run, False)},
    "official": {"pages": (official_pages.run, True), "observe": (official_observe.run, False)},
    "reports": {"observe": (reports_observe.run, False)},  # travellers' reports -> evidence (corpus.observe.reports)
    "web": {"search": (web_discover.run, False), "documents": (web_documents.run, False)},  # SearXNG (corpus.crawl.web)
    "gtravel": {"price": (gtravel.run, True)},   # Google Travel price for the trip dates -> data/gtravel/<city>/
    "gflights": {"offers": (gflights.run, True)},  # Google Flights offers into the city -> data/gflights/<city>/
    "tripcom": {"price": (tripcom.run, False)},  # Trip.com price cross-check, plain HTTP -> data/tripcom/<city>/
}


SHARDABLE = {"place_search", "place_crawl", "comments_crawl"}  # tiktok phases that split their todo list by --shard for a second account


def run(source: str, phase: str, city: str, headed: bool, limit: int | None = None, wait_relevant: bool = False,
        profile: str | None = None, shard: tuple[int, int] | None = None) -> None:
    for p in PHASES[source] if phase == "all" else (phase,):
        fn, browser_phase = PHASES[source][p]
        if browser_phase and source == "tiktok":
            out = fn(city, headed, profile_name=profile, **({"shard": shard} if p in SHARDABLE else {}),
                     **({"limit": limit} if p in ("place_crawl", "poi_crawl", "web_videos") else {}))
        elif source == "gmaps" and p in ("crawl", "relevant", "extremes", "keywords", "photos", "menu", "visit", "svc_search", "svc_place"):
            out = fn(city, headed, **({"limit": limit} if p in ("extremes", "keywords", "photos", "menu", "visit", "svc_search", "svc_place") else {}),
                     shard=shard, profile_name=profile)
        elif browser_phase and p in ("photos", "extremes", "keywords", "visit", "pages", "stay_price", "price", "resolve", "offers"):
            out = fn(city, headed, limit=limit)
        elif browser_phase:
            out = fn(city, headed)
        elif p == "observe" and source == "gmaps":
            out = fn(city, limit=limit, wait_relevant=wait_relevant)
        elif p in ("style_observe", "photo_scenes", "menu_read", "dish_check"):
            out = fn(city, limit=limit, shard=shard)
        elif p in ("observe", "photo_observe"):
            out = fn(city, limit=limit)
        elif source in ("web", "tripcom"):
            out = fn(city, limit=limit)
        elif source == "tiktok" and p in ("asr", "asr_alt", "asr_check", "place_verify"):
            out = fn(city, shard=shard)
        else:
            out = fn(city)
        if asyncio.iscoroutine(out):
            asyncio.run(out)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m corpus")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("login")
    lp.add_argument("source", choices=list(browser.LOGIN_URL))
    lp.add_argument("--profile", help="second browser profile name, e.g. tiktok2, for a second account")
    rp = sub.add_parser("review", help="local page for the items that need a person")
    rp.add_argument("--city", default="dalat")
    rp.add_argument("--port", type=int, default=8765)
    vp = sub.add_parser("views", help="global views for a city: climate (Open-Meteo), calendar (holidays + lunar), restricted (Overpass) -> data/<city>/views/")
    vp.add_argument("view", choices=[*views.VIEWS, "all"])
    vp.add_argument("--city", default="dalat")
    sub.add_parser("pulse", help="Nhịp Đà Lạt: dated signals of the crawled data -> data/<city>/pulse/ (run every 24 h)").add_argument("--city", default="dalat")
    sub.add_parser("aggregate", help="every source's observations -> data/intel/places/").add_argument("--city", default="dalat")
    sub.add_parser("serving", help="intel -> data/serving/places.json for Place Decision").add_argument("--city", default="dalat")
    sub.add_parser("stay_prices", help="newest dated lodging prices -> data/serving/stay_prices/<city>.json").add_argument("--city", default="dalat")
    sub.add_parser("flight_offers", help="newest crawled flights -> data/serving/flight_offers/<city>.json").add_argument("--city", default="dalat")
    sub.add_parser("snapshot", help="data/serving/places.json -> data/snapshot/<version>/ (what online reads)").add_argument("--city", default="dalat")
    np = sub.add_parser("normalize", help="normalize saved inputs; optionally build and publish an offline release")
    np.add_argument("--city", default="dalat")
    np.add_argument("--rebuild", action="store_true")
    np.add_argument("--publish", action="store_true")
    ip = sub.add_parser("index", help="semantic index: per-place vectors (GPU) -> data/index/<version>/ (docs/CORPUS.md)")
    ip.add_argument("phase", nargs="?", default="all", choices=["vectors", "compile", "all"])
    ip.add_argument("--city", default="dalat")
    ip.add_argument("--kinds", nargs="*", default=None, help="vectors: photos frames spans (default: all)")
    bp = sub.add_parser("build", help="incremental build: qc -> observe -> judge -> aggregate -> serving")
    bp.add_argument("--city", default="dalat")
    bp.add_argument("--every", type=float, help="repeat the build every N minutes (while crawls add data)")
    bp.add_argument("--skip", nargs="*", default=[], help='steps to leave out, e.g. "tiktok" or "gmaps qc"')
    navp = sub.add_parser("navigate", help="sol decides what to mine for a city (plan), code diffs it against the corpus (compare) -> data/<city>/navigate/")
    navp.add_argument("phase", choices=["plan", "compare"])
    navp.add_argument("--city", default="dalat")
    navp.add_argument("--map", type=pathlib.Path, help="compare: a mining map file (default: the latest, data/<city>/navigate/mining_map.json)")
    navp.add_argument("--no-latest", action="store_true", help="plan: write only mining_map_<ts>.json, leave mining_map.json (what web search reads) as it is")
    lcp = sub.add_parser("local", help="web Documents -> LocalClaim: extract (Extractor) then group (code: gate, sources, sol's claims) -> data/<city>/local/")
    lcp.add_argument("phase", choices=["extract", "group"])
    lcp.add_argument("--city", default="dalat")
    lcp.add_argument("--limit", type=int, help="extract: only the first N Documents")
    lcp.add_argument("--docs", type=pathlib.Path, help="extract: a text file of doc_ids, one per line")
    lcp.add_argument("--parallel", type=int, default=4, help="extract: concurrent Extractor calls")
    lcp.add_argument("--map", type=pathlib.Path, help="group: a mining map file for sol's general claims (default: the latest)")
    gp = sub.add_parser("gsearch", help="Google web search through the browser -> data/gsearch/<city>/")
    gp.add_argument("phase", choices=["run"])
    gp.add_argument("--query", action="append", default=[], help="one query; repeat for more")
    gp.add_argument("--from-file", help="a text file, one query per line (# comments, blank lines skipped)")
    gp.add_argument("--pages", type=int, default=1, help="result pages per query (page 2 = results 11-20)")
    gp.add_argument("--city", default="dalat")
    gp.add_argument("--headed", action="store_true")
    gp.add_argument("--profile", default="gmaps_a", help="browser profile = a signed-in Google account (.browser/<name>)")
    jp = sub.add_parser("judge", help="the Judge model labels claims, place status, duplicate places")
    jp.add_argument("phase", choices=[*judge.PHASES, "all"])
    jp.add_argument("--city", default="dalat")
    jp.add_argument("--limit", type=int, help="audit: only the first N calls")
    for source, phases in PHASES.items():
        sp = sub.add_parser(source)
        sp.add_argument("phase", choices=[*phases, "all"])
        sp.add_argument("--city", default="dalat")
        sp.add_argument("--headed", action="store_true")
        sp.add_argument("--limit", type=int, help="observe / photos: only the first N places; place_crawl: only N videos per run; "
                                                  "poi_crawl: only N places per run; gmaps resolve: only N nominees per run; web_videos: only N videos per run; web search: only N queries per run; "
                                                  "web documents: only N pages per run")
        sp.add_argument("--wait-relevant", action="store_true",
                        help="gmaps observe: skip places whose relevant reviews are not crawled yet")
        if source == "tiktok":
            sp.add_argument("--profile", help="second browser profile name, e.g. tiktok2, for a second account "
                                               "(login it first: `python -m corpus login tiktok --profile tiktok2`)")
            sp.add_argument("--shard", help="i/n: only this process's 1/n share of the todo list, for "
                                             "place_search/place_crawl run in parallel under a second --profile; asr / asr_alt: one GPU each; asr_check / place_verify: one process per Gemma endpoint")
        if source == "gmaps":  # one Python process saturates one core at ~8 tabs: browser phases split across processes
            sp.add_argument("--profile", help="crawl / relevant / extremes / keywords / photos: browser profile, one copy per process")
            sp.add_argument("--shard", help="i/n: this process's 1/n share of the todo list (crawl / relevant / extremes / keywords / photos / style_observe)")
    args = ap.parse_args()
    if args.cmd == "normalize" and args.publish and not args.rebuild:
        ap.error("--publish requires --rebuild")
    try:
        if args.cmd == "login":
            asyncio.run(browser.login(args.source, args.profile))
        elif args.cmd == "review":
            review_server.run(args.city, args.port)
        elif args.cmd == "views":
            views.run(args.view, args.city)
        elif args.cmd == "pulse":
            pulse.run(args.city)
        elif args.cmd == "aggregate":
            aggregate_run(args.city)
        elif args.cmd == "normalize":
            import json
            if args.rebuild:
                from .releases import rebuild
                result = rebuild(args.city, publish=args.publish)
                print(json.dumps({"release_id": result["release_id"], "quality": result["quality"]}, ensure_ascii=False))
            else:
                from .normalize import normalize
                result = normalize(args.city)
                print(json.dumps({"normalization_id": result.id, "summary": result.manifest["summary"]}, ensure_ascii=False))
        elif args.cmd == "serving":
            serving_run(args.city)
        elif args.cmd == "stay_prices":
            from .serving import stay_prices
            print(stay_prices.publish(args.city)["stats"])
        elif args.cmd == "flight_offers":
            from .serving import flight_offers
            print(flight_offers.publish(args.city)["stats"])
        elif args.cmd == "snapshot":
            from .snapshot import compile_snapshot
            compile_snapshot(args.city)
        elif args.cmd == "index":
            from . import index
            if args.phase in ("vectors", "all"):
                index.embed_vectors(tuple(args.kinds) if args.kinds else index.vectors.KINDS)
            if args.phase in ("compile", "all"):
                index.compile_index(args.city)
        elif args.cmd == "build":
            build.run(args.city, args.every, set(args.skip))
        elif args.cmd == "gsearch":
            from .crawl import gsearch
            queries = list(args.query)
            if args.from_file:
                from pathlib import Path
                lines = Path(args.from_file).read_text(encoding="utf-8").splitlines()
                queries += [x.strip() for x in lines if x.strip() and not x.strip().startswith("#")]
            if not queries:
                ap.error("gsearch run needs --query or --from-file")
            gsearch.run(args.city, queries, args.pages, args.headed, args.profile)
        elif args.cmd == "local":
            from . import local
            if args.phase == "extract":
                docs = [x.strip() for x in args.docs.read_text(encoding="utf-8").splitlines() if x.strip()] if args.docs else None
                asyncio.run(local.run_extract(args.city, limit=args.limit, docs=docs, parallel=args.parallel))
            else:
                local.run_group(args.city, map_path=args.map)
        elif args.cmd == "navigate":
            if args.phase == "plan":
                result = asyncio.run(navigate.plan(args.city, latest=not args.no_latest))
                print(f"navigate plan {args.city}: {len(result.aspects)} aspects, {len(result.general_claims)} general claims, "
                      f"{len(result.rejected)} rejected (model {result.model})")
            else:
                mining_map = navigate.load_map(args.city, args.map)
                if mining_map is None:
                    raise SystemExit(f"no mining map for {args.city}: run `python -m corpus navigate plan --city {args.city}` first")
                print(navigate.table(navigate.compare_map(args.city, mining_map)))
        elif args.cmd == "judge":
            for name in ("dedup", "status", "audit") if args.phase == "all" else (args.phase,):
                fn = judge.PHASES[name]
                asyncio.run(fn(args.city, limit=args.limit) if name == "audit" else fn(args.city))
        else:
            shard = None
            if getattr(args, "shard", None):
                i, n = (int(x) for x in args.shard.split("/"))
                shard = (i, n)
            run(args.cmd, args.phase, args.city, args.headed, args.limit, args.wait_relevant,
                getattr(args, "profile", None), shard)
    except (browser.LoginRequired, navigate.NavigateError) as e:
        raise SystemExit(str(e))


if __name__ == "__main__":
    main()
