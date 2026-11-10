"""One-stop pipeline: search -> dedup -> screen -> continuous DOI list.

The orchestrating Claude session makes ONE call and reads a slim report — it
never sees abstracts. Full data (with abstracts) is written to an archive dir
for the human; the stdout report carries only {doi, year, cites, title, verdict}.

Pipeline:
  1. search   multi-source (Crossref / Semantic Scholar / OpenAlex / arXiv)
  2. dedup    drop DOIs already in the local Zotero library
  3. screen   DeepSeek reads abstracts, returns include/exclude/uncertain
  4. persist  archives/<slug>/papers.json (full) + screen.json (verdicts)
  5. report   slim stdout + the final continuous DOI list (include only)
  6. import   optional --write: import include DOIs into a collection
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime

from . import import_zotero, zotero_api
from .screen import screen as screen_papers
from .search import search

_SLUG_RE = re.compile(r"[^\w一-鿿-]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("-", s.strip()).strip("-")[:40] or "search"


def run(keywords, collection: str | None = None, top: int = 40,
        min_citations: int = 0, sources: list[str] | None = None,
        mailto: str = "", write: bool = False, criteria: str | None = None,
        archive_dir: str = "archives", backend: str = "local",
        timeout: int = 120, api_key=None, model=None, base_url=None) -> dict:
    query = " ".join(keywords) if isinstance(keywords, (list, tuple)) else keywords

    # 1. search
    papers = search(query, top=top, min_citations=min_citations, sources=sources, mailto=mailto)

    # 2. dedup against the library
    existing: set[str] = set()
    try:
        existing = zotero_api.list_existing_dois()
    except Exception as e:  # noqa: BLE001 - dedup is best-effort
        print(f"[dedup] 读取库内已有 DOI 失败（跳过去重）：{e}", file=sys.stderr)
    before = len(papers)
    papers = [p for p in papers if p.doi not in existing]
    dropped = before - len(papers)

    # 3. screen via DeepSeek (abstracts never reach this process's stdout)
    if papers:
        try:
            verdicts = screen_papers(papers, topic=query, criteria=criteria,
                                     api_key=api_key, model=model, base_url=base_url)
        except Exception as e:  # noqa: BLE001 - degrade to all-uncertain
            print(f"[screen] DeepSeek 筛选失败，全部标 uncertain：{e}", file=sys.stderr)
            verdicts = [{"doi": p.doi, "title": p.title, "verdict": "uncertain",
                         "reason": str(e)[:100]} for p in papers]
    else:
        verdicts = []

    include = [v for v in verdicts if v["verdict"] == "include"]
    uncertain = [v for v in verdicts if v["verdict"] == "uncertain"]
    excluded = len(verdicts) - len(include) - len(uncertain)

    # 4. persist full data to archive (for the human, not the AI)
    slug = _slugify(query)
    arc = os.path.join(archive_dir, slug)
    os.makedirs(arc, exist_ok=True)
    with open(os.path.join(arc, "papers.json"), "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in papers], f, ensure_ascii=False, indent=2)
    with open(os.path.join(arc, "screen.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"topic": query, "ts": datetime.now().strftime("%Y%m%d-%H%M%S")},
                   "results": verdicts}, f, ensure_ascii=False, indent=2)

    # 5. slim report (no abstracts in stdout)
    by_doi = {p.doi: p for p in papers}

    def _line(v):
        p = by_doi.get(v["doi"])
        return f"{v['doi']}  {p.year if p else ''}  {p.citations if p else 0}c  {(v['title'] or '')[:40]}"

    print(f"检索 {before} → 去重剔除 {dropped} → 剩 {len(papers)}；include {len(include)} / uncertain {len(uncertain)} / exclude {excluded}")
    print(f"完整数据（含摘要）→ {arc}/")
    print()
    print(f"—— 建议入库（include, {len(include)}）——")
    for v in include:
        print("  " + _line(v))
    if uncertain:
        print(f"—— 待人工复核（uncertain, {len(uncertain)}）——")
        for v in uncertain:
            print("  " + _line(v))

    include_dois = [v["doi"] for v in include if v["doi"]]
    print()
    print(f"—— 连续 DOI（{len(include_dois)} 个）——")
    print("\n".join(include_dois))

    # 6. optional import
    import_results = []
    if write and include_dois:
        print()
        print("[import] 入库中…")
        import_results = import_zotero.import_dois(
            include_dois, backend=backend, collection=collection, timeout=timeout)
        for r in import_results:
            print(f"{r.status:10s} {r.doi}  {r.message}")

    return {
        "archive": arc,
        "papers": len(papers),
        "include_dois": include_dois,
        "uncertain": uncertain,
        "import_results": import_results,
    }
