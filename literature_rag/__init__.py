"""literature_rag: keyword -> DOI -> Zotero import."""

from .models import Paper, normalize_doi
from .search import search
from .import_zotero import import_dois, check_plugin

__version__ = "0.1.0"

__all__ = ["Paper", "normalize_doi", "search", "import_dois", "check_plugin"]
