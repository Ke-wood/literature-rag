"""Semantic Scholar Graph API source."""
from __future__ import annotations

import time

from .._http import get_with_fallback
from ..models import Paper, normalize_doi

BASE = "https://api.semanticscholar.org/graph/v1/paper/search"


def search(query: str, limit: int = 20, timeout: int = 15) -> list[Paper]:
    params = {
        "query": query,
        "limit": limit,
        "fields": "externalIds,title,abstract,year,venue,authors,citationCount,url,fieldsOfStudy",
    }
    r = get_with_fallback(BASE, params=params, timeout=timeout)
    for attempt in range(3):
        if r.status_code != 429:
            break
        time.sleep(1.2 * (2 ** attempt))  # unauthenticated limit ~1 rps
        r = get_with_fallback(BASE, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json().get("data", []) or []

    papers: list[Paper] = []
    for it in data:
        doi = normalize_doi((it.get("externalIds") or {}).get("DOI"))
        if not doi:
            continue
        authors = [a.get("name", "") for a in (it.get("authors") or []) if a.get("name")]
        keywords = [k for k in (it.get("fieldsOfStudy") or []) if k][:3]
        papers.append(Paper(
            doi=doi,
            title=it.get("title") or "",
            authors=authors,
            year=it.get("year"),
            journal=it.get("venue"),
            abstract=it.get("abstract"),
            citations=int(it.get("citationCount") or 0),
            source="semantic_scholar",
            sources=["semantic_scholar"],
            url=it.get("url"),
            relevance=0.0,  # no numeric score; rank fallback fills it
            keywords=keywords,
        ))
    return papers
