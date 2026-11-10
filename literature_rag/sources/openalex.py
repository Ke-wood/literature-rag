"""OpenAlex source."""
from __future__ import annotations

from .._http import get_with_fallback
from ..models import Paper, normalize_doi

BASE = "https://api.openalex.org/works"


def _rebuild_abstract(inv: dict | None) -> str | None:
    """Rebuild plain text from OpenAlex's abstract_inverted_index."""
    if not inv:
        return None
    pos: dict[int, str] = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)) or None


def search(query: str, per_page: int = 25, mailto: str = "", timeout: int = 15) -> list[Paper]:
    params = {"search": query, "per-page": per_page}
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": f"litrag/0.1 (mailto:{mailto or 'litrag@example.com'})"}
    r = get_with_fallback(BASE, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    results = r.json().get("results", []) or []

    papers: list[Paper] = []
    for it in results:
        doi = normalize_doi(it.get("doi"))
        if not doi:
            continue
        authors = []
        for a in it.get("authorships", []) or []:
            nm = (a.get("author") or {}).get("display_name")
            if nm:
                authors.append(nm)
        journal = None
        src = (it.get("primary_location") or {}).get("source") or {}
        journal = src.get("display_name")
        keywords = [c.get("display_name") for c in (it.get("concepts") or []) if c.get("display_name")][:3]
        papers.append(Paper(
            doi=doi,
            title=it.get("title") or "",
            authors=authors,
            year=it.get("publication_year"),
            journal=journal,
            abstract=_rebuild_abstract(it.get("abstract_inverted_index")),
            citations=int(it.get("cited_by_count") or 0),
            source="openalex",
            sources=["openalex"],
            url=it.get("doi"),
            relevance=min(float(it.get("relevance_score") or 0.0), 1.0),
            keywords=keywords,
        ))
    return papers
