"""A place's introduction (docs/CORPUS.md, Giới thiệu địa điểm): a short summary and a guide's story told from the
corpus' own evidence, every sentence with its sources. Offline. Public API:

    Library(city, root=None)                     -> what the evidence is read from (web Documents, search, names)
    pack(lib, record, city_name, cfg)            -> [evidence item]   (numbered e1, e2, ...)
    check(line, items, cfg)                      -> reason | None     (code gate of one sentence)
    build(city, only=, limit=, root=)            -> stats             (async; CLI `intro build`)
    load(city, root=None)                        -> {fid: introduction}
    build_posts(city, only=, root=)              -> stats             (async; CLI `intro posts`: editorial posts, 3D places)
"""

from .evidence import Library, pack
from .gate import check
from .posts import build as build_posts
from .run import build, intro_dir, load

__all__ = ["Library", "build", "build_posts", "check", "intro_dir", "load", "pack"]
