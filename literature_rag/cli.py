"""Command-line interface: litrag search / import / health."""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import import_zotero
from .search import SOURCES, search


def _slim(p) -> dict:
    """Token-safe paper dict: no abstract (that's the expensive field)."""
    return {
        "doi": p.doi,
        "title": p.title,
        "year": p.year,
        "journal": p.journal,
        "citations": p.citations,
        "authors": p.authors,
        "sources": p.sources,
    }


def _print_papers(papers, as_json: bool) -> None:
    if as_json:
        print(json.dumps([_slim(p) for p in papers], ensure_ascii=False, indent=2))
        return
    for i, p in enumerate(papers, 1):
        authors = ", ".join(p.authors[:3]) + (", et al." if len(p.authors) > 3 else "")
        print(f"{i}. {p.title}")
        print(f"   DOI: {p.doi}  |  {p.year}  |  {p.journal or ''}  |  cites: {p.citations}  |  src: {','.join(p.sources)}")
        if authors:
            print(f"   AUTH: {authors}")
        if p.abstract:
            print(f"   ABS: {p.abstract[:200]}")


def cmd_search(args) -> None:
    papers = search(
        keywords=args.keywords,
        top=args.top,
        sources=args.sources.split(",") if args.sources else None,
        min_citations=args.min_citations,
        mailto=args.mailto,
    )
    _print_papers(papers, args.json)


def cmd_import(args) -> None:
    if args.backend == "local":
        ok, info = import_zotero.check_plugin()
        if not ok:
            print(f"error: write-endpoint plugin not reachable: {info}", file=sys.stderr)
            print("Install zotero-write-endpoint and ensure Zotero is running with the local API enabled.", file=sys.stderr)
            sys.exit(1)
        results = import_zotero.import_dois(args.dois, backend="local", collection=args.collection, timeout=args.timeout)
    else:
        library_id = args.library_id or os.environ.get("ZOTERO_LIBRARY_ID")
        api_key = args.api_key or os.environ.get("ZOTERO_API_KEY")
        if not library_id or not api_key:
            print("error: --library-id/--api-key (or ZOTERO_LIBRARY_ID/ZOTERO_API_KEY) required for web backend", file=sys.stderr)
            sys.exit(1)
        results = import_zotero.import_dois(args.dois, backend="web", library_id=library_id, api_key=api_key, timeout=args.timeout)

    if args.json:
        print(json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2))
    else:
        for r in results:
            print(f"{r.status:10s} {r.doi}  {r.message}")


def cmd_health(args) -> None:
    import requests

    def check(name, url):
        try:
            r = requests.get(url, timeout=8, headers={"User-Agent": "litrag/0.1"})
            return f"OK (HTTP {r.status_code})"
        except Exception as e:  # noqa: BLE001
            return f"FAIL: {e}"

    print("Zotero local API  :", check("local", "http://127.0.0.1:23119/connector/ping"))
    ok, info = import_zotero.check_plugin()
    print("Write plugin      :", ("OK: " + info) if ok else ("FAIL: " + info))
    ds_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    print("DeepSeek key      :", ("OK (env set)" if ds_key else "MISSING (set DEEPSEEK_API_KEY or ANTHROPIC_AUTH_TOKEN)"))
    source_urls = {
        "crossref": "https://api.crossref.org/works?rows=1",
        "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search?query=test&limit=1",
        "openalex": "https://api.openalex.org/works?per-page=1",
        "arxiv": "http://export.arxiv.org/api/query?search_query=all:test&max_results=1",
    }
    for name, url in source_urls.items():
        print(f"{name:18s}:", check(name, url))


def cmd_collections(args) -> None:
    from . import zotero_api
    try:
        cols = zotero_api.list_collections()
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    if args.json:
        print(json.dumps(cols, ensure_ascii=False, indent=2))
    else:
        for c in cols:
            parent = f"  <- {c['parent']}" if c.get("parent") else ""
            print(f"{c['key']:10s}  {c['name']}{parent}")


def cmd_coarse(args) -> None:
    from .coarse import coarse
    md_path, rows = coarse(
        keywords=args.keywords,
        out_dir=args.out,
        top=args.top,
        min_citations=args.min_citations,
        mailto=args.mailto,
        translate_enabled=not args.no_translate,
    )
    if args.json:
        print(json.dumps({"md_path": md_path, "rows": rows}, ensure_ascii=False, indent=2))
    else:
        print(f"粗筛表格已生成：{md_path}")
        print(f"共 {len(rows)} 条，请打开文件人工筛选（在「序号」列加 √ 标记要入库的条目）。\n")
        print("序号 | 年份 | 引用 | 标题 | DOI")
        for r in rows:
            print(f"{r['i']:3d} | {str(r['year'] or ''):4} | {r['citations']:4d} | {r['title'][:60]} | {r['doi']}")


def cmd_run(args) -> None:
    from .run import run
    run(
        keywords=args.keywords,
        collection=args.collection,
        top=args.top,
        min_citations=args.min_citations,
        sources=args.sources.split(",") if args.sources else None,
        mailto=args.mailto,
        write=args.write,
        criteria=args.criteria,
        archive_dir=args.archive_dir,
        backend=args.backend,
        timeout=args.timeout,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="litrag", description="Keyword -> DOI -> Zotero import")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("search", help="search literature by keywords")
    p.add_argument("keywords", nargs="+", help="search keywords")
    p.add_argument("--top", type=int, default=20)
    p.add_argument("--sources", type=str, default=None, help=f"comma-separated subset of {list(SOURCES)}")
    p.add_argument("--min-citations", type=int, default=0)
    p.add_argument("--mailto", type=str, default="", help="email for Crossref/OpenAlex polite pool")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("import", help="import DOIs/identifiers into Zotero")
    p.add_argument("dois", nargs="+", help="DOIs (or ISBN/PMID/arXiv ids) to import")
    p.add_argument("--backend", choices=["local", "web"], default="local")
    p.add_argument("--collection", type=str, default=None, help="target collection (name or key); list via `litrag collections`")
    p.add_argument("--timeout", type=int, default=120, help="seconds to wait for Zotero to resolve metadata")
    p.add_argument("--library-id", type=str, default=None)
    p.add_argument("--api-key", type=str, default=None)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("collections", help="list Zotero collections")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_collections)

    p = sub.add_parser("coarse", help="coarse filter: write an md table (abstract + machine translation) for manual screening")
    p.add_argument("keywords", nargs="+", help="search keywords")
    p.add_argument("--out", type=str, default="litrag_coarse", help="output directory for the md file")
    p.add_argument("--top", type=int, default=30)
    p.add_argument("--min-citations", type=int, default=0)
    p.add_argument("--mailto", type=str, default="")
    p.add_argument("--no-translate", action="store_true", help="skip machine translation (faster; 摘要翻译 column left empty)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_coarse)

    p = sub.add_parser("run", help="one-stop: search -> dedup -> DeepSeek screen -> continuous DOI list (token-cheap)")
    p.add_argument("keywords", nargs="+", help="search keywords (3-5 English words recommended)")
    p.add_argument("--collection", type=str, default=None, help="target collection (name or key) for --write")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--min-citations", type=int, default=0)
    p.add_argument("--sources", type=str, default=None, help=f"comma-separated subset of {list(SOURCES)}")
    p.add_argument("--mailto", type=str, default="")
    p.add_argument("--criteria", type=str, default=None, help="extra screening criteria in Chinese")
    p.add_argument("--archive-dir", type=str, default="archives", help="where full data (with abstracts) is written")
    p.add_argument("--write", action="store_true", help="import include DOIs into --collection after screening")
    p.add_argument("--backend", choices=["local", "web"], default="local")
    p.add_argument("--timeout", type=int, default=120)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("health", help="check Zotero + plugin + source connectivity")
    p.set_defaults(func=cmd_health)

    return parser


def main(argv: list[str] | None = None) -> None:
    _force_utf8()
    args = build_parser().parse_args(argv)
    args.func(args)


def _force_utf8() -> None:
    """Windows consoles/pipes default to GBK; force UTF-8 so non-ASCII titles print."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001 - non-TextIOWrapper streams
            pass


if __name__ == "__main__":
    main()
