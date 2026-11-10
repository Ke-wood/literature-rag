"""Crossref REST API source."""
from __future__ import annotations

import re

from .._http import get_with_fallback
from ..models import Paper, normalize_doi

BASE = "https://api.crossref.org/works"

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_COMPONENT_RE = re.compile(r"/(fig|figure|table|suppl|supp|appendix|schema|scheme)[-_.]", re.IGNORECASE)

# Work types worth importing; excludes components/journals/issues/etc.
_WORK_TYPES = {
    "journal-article", "proceedings-article", "posted-content", "book",
    "book-chapter", "monograph", "report", "dataset", "peer-review",
    "reference-entry", "dissertation", "standard",
}


def _clean_abstract(text: str | None) -> str | None:
    if not text:
        return None
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip() or None


def search(query: str, rows: int = 20, mailto: str = "", timeout: int = 15) -> list[Paper]:
    params = {
        "query.bibliographic": query,
        "rows": rows,
        "select": "DOI,title,author,container-title,published,is-referenced-by-count,abstract,score,URL,type",
    }
    if mailto:
        params["mailto"] = mailto
    headers = {"User-Agent": f"litrag/0.1 (mailto:{mailto or 'litrag@example.com'})"}
    r = get_with_fallback(BASE, params=params, headers=headers, timeout=timeout)
    r.raise_for_status()
    items = r.json().get("message", {}).get("items", []) or []

    papers: list[Paper] = []
    for it in items:
        doi = normalize_doi(it.get("DOI"))
        if not doi:
            continue
        if it.get("type") not in _WORK_TYPES:
            continue
        if _COMPONENT_RE.search(doi):
            continue
        title = (it.get("title") or [""])[0] or ""
        authors = []
        for a in it.get("author", []) or []:
            nm = (a.get("family") or "") + ((" " + a.get("given")) if a.get("given") else "")
            if nm.strip():
                authors.append(nm.strip())
        year = None
        pub = it.get("published") or {}
        if pub.get("date-parts"):
            year = pub["date-parts"][0][0]
        journal = (it.get("container-title") or [None])[0]
        score = float(it.get("score") or 0.0)
        papers.append(Paper(
            doi=doi,
            title=title,
            authors=authors,
            year=year,
            journal=journal,
            abstract=_clean_abstract(it.get("abstract")),
            citations=int(it.get("is-referenced-by-count") or 0),
            source="crossref",
            sources=["crossref"],
            url=it.get("URL"),
            relevance=min(score / 100.0, 1.0),
        ))
    return papers
