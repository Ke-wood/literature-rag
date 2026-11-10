"""arXiv Atom API source (preprints / CS coverage)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from .._http import get_with_fallback
from ..models import Paper, arxiv_id, normalize_doi

BASE = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}


def _local(tag: str) -> str:
    return tag.split("}")[-1]


def search(query: str, max_results: int = 10, timeout: int = 15) -> list[Paper]:
    params = {"search_query": f"all:{query}", "max_results": max_results}
    r = get_with_fallback(BASE, params=params, timeout=timeout)
    r.raise_for_status()
    root = ET.fromstring(r.text)

    papers: list[Paper] = []
    for entry in root.findall("a:entry", NS):
        raw_id = None
        doi = None
        title = ""
        authors: list[str] = []
        year = None
        abstract = ""
        url = None

        for child in entry:
            tag = _local(child.tag)
            if tag == "id":
                url = (child.text or "").strip() or None
                if url:
                    raw_id = url.split("/abs/")[-1]
            elif tag == "title":
                title = " ".join((child.text or "").split())
            elif tag == "summary":
                abstract = " ".join((child.text or "").split())
            elif tag == "author":
                name = ""
                for c in child:
                    if _local(c.tag) == "name":
                        name = c.text or ""
                if name:
                    authors.append(name)
            elif tag == "published":
                if child.text:
                    try:
                        year = int(child.text[:4])
                    except ValueError:
                        pass
            elif tag == "doi":
                doi = normalize_doi(child.text)

        key = doi
        if not key and raw_id:
            key = "arxiv:" + arxiv_id(raw_id)  # strip "vN" version suffix
        if not key:
            continue

        papers.append(Paper(
            doi=key,
            title=title,
            authors=authors,
            year=year,
            journal="arXiv",
            abstract=abstract or None,
            citations=0,
            source="arxiv",
            sources=["arxiv"],
            url=url,
            relevance=0.0,
        ))
    return papers
