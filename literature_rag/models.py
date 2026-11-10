"""Shared data model and DOI normalization."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_DOI_URL_RE = re.compile(r"^https?://(dx\.)?doi\.org/", re.IGNORECASE)
_ARXIV_DOI_RE = re.compile(r"^10\.48550/arxiv\.(\d+\.\d+)(v\d+)?$")
_ARXIV_VER_RE = re.compile(r"v\d+$")


def normalize_doi(doi: str | None) -> str | None:
    """Normalize a DOI string: strip URL prefixes and lowercase.

    DataCite DOIs of arXiv papers (``10.48550/arxiv.<id>``) are collapsed to
    ``arxiv:<id>`` so they dedupe against the arXiv source's own ids.
    """
    if not doi:
        return None
    d = _DOI_URL_RE.sub("", doi.strip()).lower()
    if not d:
        return None
    m = _ARXIV_DOI_RE.match(d)
    if m:
        return "arxiv:" + m.group(1)
    return d


def arxiv_id(doi: str | None) -> str | None:
    """Return a bare arXiv id (version suffix stripped) from an ``arxiv:`` key."""
    if not doi:
        return None
    return _ARXIV_VER_RE.sub("", doi)


@dataclass
class Paper:
    """A single bibliographic result, unified across sources."""

    doi: str | None          # normalized DOI, or "arxiv:<id>" when no DOI
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    journal: str | None = None
    abstract: str | None = None
    citations: int = 0
    source: str = ""              # primary source name
    sources: list[str] = field(default_factory=list)  # every source that matched
    url: str | None = None
    relevance: float = 0.0        # source relevance in ~[0,1]; 0.0 = unset
    keywords: list[str] = field(default_factory=list)  # topic tags (OpenAlex concepts / S2 fieldsOfStudy)

    def to_dict(self) -> dict:
        return {
            "doi": self.doi,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "journal": self.journal,
            "abstract": self.abstract,
            "citations": self.citations,
            "source": self.source,
            "sources": self.sources,
            "url": self.url,
            "relevance": self.relevance,
            "keywords": self.keywords,
        }
