"""Multi-source literature search: concurrent fetch, dedupe, merge, rank."""
from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Paper
from .sources import arxiv, crossref, openalex, semantic_scholar

SOURCES = {
    "crossref": crossref.search,
    "semantic_scholar": semantic_scholar.search,
    "openalex": openalex.search,
    "arxiv": arxiv.search,
}


def search(
    keywords: str | list[str],
    top: int = 20,
    sources: list[str] | None = None,
    min_citations: int = 0,
    mailto: str = "",
    timeout: int = 15,
) -> list[Paper]:
    """Search all (or selected) sources, merge by DOI, and rank."""
    query = " ".join(keywords) if isinstance(keywords, (list, tuple)) else keywords
    source_names = [s for s in (sources or list(SOURCES)) if s in SOURCES]

    results: dict[str, list[Paper]] = {}
    with ThreadPoolExecutor(max_workers=max(len(source_names), 1)) as ex:
        future_map = {ex.submit(SOURCES[name], query): name for name in source_names}
        for fut in as_completed(future_map):
            name = future_map[fut]
            try:
                results[name] = fut.result()
            except Exception:
                results[name] = []  # a single failing source must not block the rest

    merged = list(_merge(results).values())
    merged = [p for p in merged if p.citations >= min_citations]
    merged.sort(key=_score, reverse=True)
    return merged[:top]


def _merge(results: dict[str, list[Paper]]) -> dict[str, Paper]:
    merged: dict[str, Paper] = {}
    for source, papers in results.items():
        n = len(papers)
        for idx, p in enumerate(papers):
            key = p.doi
            if key is None:
                continue
            if key not in merged:
                p.sources = [source]
                if p.relevance == 0.0:
                    p.relevance = max(0.0, 1.0 - idx / max(n, 1))
                merged[key] = p
            else:
                existing = merged[key]
                if source not in existing.sources:
                    existing.sources.append(source)
                if not existing.abstract and p.abstract:
                    existing.abstract = p.abstract
                if p.citations > existing.citations:
                    existing.citations = p.citations
                if not existing.journal and p.journal:
                    existing.journal = p.journal
                if not existing.year and p.year:
                    existing.year = p.year
                if not existing.authors and p.authors:
                    existing.authors = p.authors
                existing.relevance = max(existing.relevance, p.relevance)
    return merged


def _score(p: Paper) -> float:
    cit = math.log1p(p.citations) / math.log1p(1000)  # log-scaled citations ~[0,1]
    return 0.5 * cit + 0.5 * (p.relevance or 0.0)
