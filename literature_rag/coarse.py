"""Coarse filter: keyword search -> md table (abstract + machine translation).

The returned `summary_rows` are AI-facing and contain no abstract/translation;
the md file is for human screening only.
"""
from __future__ import annotations

import os
import re
from datetime import datetime

from . import translate
from .search import search

_SLUG_RE = re.compile(r"[^\w一-鿿-]+")


def _slugify(s: str) -> str:
    return _SLUG_RE.sub("-", s.strip()).strip("-")[:40] or "search"


def _esc(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def _as_list(keywords) -> list[str]:
    return list(keywords) if isinstance(keywords, (list, tuple)) else [keywords]


def coarse(keywords, out_dir: str = "litrag_coarse", top: int = 30,
           min_citations: int = 0, mailto: str = "",
           translate_enabled: bool = True) -> tuple[str, list[dict]]:
    """Run a coarse search and write an md table.

    Returns (md_path, summary_rows) where summary_rows has only
    {i, title, doi, year, citations} — no abstract or translation.
    """
    kw = _as_list(keywords)
    papers = search(kw, top=top, min_citations=min_citations, mailto=mailto)

    os.makedirs(out_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    fname = f"粗筛-{_slugify(' '.join(kw))}-{ts}.md"
    md_path = os.path.join(out_dir, fname)

    lines = [
        "| 序号 | 文献名称 | DOI | 年份 | 引用数 | 摘要 | 摘要翻译 |",
        "|---|---|---|---|---|---|---|",
    ]
    summary_rows: list[dict] = []
    for i, p in enumerate(papers, 1):
        abstract_cn = translate.translate(p.abstract) if translate_enabled else ""
        lines.append(
            f"| {i} | {_esc(p.title)} | {p.doi or ''} | {p.year or ''} | "
            f"{p.citations} | {_esc(p.abstract)} | {_esc(abstract_cn)} |"
        )
        summary_rows.append({
            "i": i,
            "title": p.title,
            "doi": p.doi,
            "year": p.year,
            "citations": p.citations,
        })

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# 粗筛列表：" + " ".join(kw) + "\n\n")
        f.write("> 人工筛选：在「序号」列前加 √ 标记要入库的条目。\n\n")
        f.write("\n".join(lines) + "\n")

    return md_path, summary_rows
