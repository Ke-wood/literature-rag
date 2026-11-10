"""Write papers into Zotero.

Two backends:
- "local" (default): POST to the community `zotero-write-endpoint` plugin running
  inside Zotero's local server (127.0.0.1:23119). Fully local, no account/key.
- "web": Zotero Web API via pyzotero. Requires ZOTERO_LIBRARY_ID + ZOTERO_API_KEY.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import requests

from .zotero_api import resolve_collection

LOCAL_API = "http://127.0.0.1:23119"
WRITE_ENDPOINT = f"{LOCAL_API}/zotero-write"


@dataclass
class ImportResult:
    doi: str
    status: str      # "added" | "duplicate" | "error"
    message: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def check_plugin(timeout: int = 5) -> tuple[bool, str]:
    """Return (reachable, version_or_error) for the write-endpoint plugin."""
    try:
        r = requests.get(f"{WRITE_ENDPOINT}/version", timeout=timeout)
        if r.status_code == 200:
            return True, r.text.strip()
        return False, f"HTTP {r.status_code}"
    except Exception as e:  # noqa: BLE001 - surface any connection error
        return False, str(e)


def import_dois(
    identifiers: list[str],
    backend: str = "local",
    collection: str | None = None,
    library_id: str | None = None,
    api_key: str | None = None,
    timeout: int = 120,
) -> list[ImportResult]:
    """Import a list of identifiers (DOI, ISBN, PMID, arXiv id) into Zotero."""
    if backend == "web":
        return _import_web(identifiers, library_id, api_key, collection)
    return _import_local(identifiers, collection, timeout)


def _import_local(identifiers: list[str], collection: str | None, timeout: int) -> list[ImportResult]:
    col_key = None
    if collection:
        try:
            col_key = resolve_collection(collection)
        except Exception as e:  # noqa: BLE001
            return [ImportResult(i, "error", f"collection: {e}") for i in identifiers]
    results: list[ImportResult] = []
    for ident in identifiers:
        try:
            body: dict = {"identifiers": [ident]}
            if col_key:
                body["collections"] = [col_key]
            r = requests.post(f"{WRITE_ENDPOINT}/add-by-identifier", json=body, timeout=timeout)
            results.append(_parse_local_result(ident, r))
        except Exception as e:  # noqa: BLE001
            results.append(ImportResult(ident, "error", str(e)))
    return results


def _parse_local_result(ident: str, r: requests.Response) -> ImportResult:
    if r.status_code != 200:
        if r.status_code in (409, 400):
            return ImportResult(ident, "duplicate", f"HTTP {r.status_code}: {r.text[:200]}")
        return ImportResult(ident, "error", f"HTTP {r.status_code}: {r.text[:200]}")
    try:
        data = r.json()
    except ValueError:
        return ImportResult(ident, "added", "")
    # Plugin returns {results: [{identifier, ok, keys, title, error}]}.
    results = data.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if first.get("ok") is False:
            return ImportResult(ident, "error", str(first.get("error") or "unknown error")[:300])
        keys = first.get("keys") or []
        if not keys:
            return ImportResult(ident, "duplicate", "already in library (no new item)")
        title = first.get("title")
        return ImportResult(ident, "added", f"{title} [{keys[0]}]" if title else keys[0])
    return ImportResult(ident, "added", "")


def _import_web(
    identifiers: list[str],
    library_id: str | None,
    api_key: str | None,
    collection: str | None,
) -> list[ImportResult]:
    try:
        from pyzotero import zotero
    except ImportError:
        return [ImportResult(i, "error", "pyzotero not installed; `pip install 'literature-rag[web]'`") for i in identifiers]
    if not library_id or not api_key:
        return [ImportResult(i, "error", "missing library_id/api_key for web backend") for i in identifiers]

    zot = zotero.Zotero(library_id, "user", api_key)
    col_key = None
    if collection:
        try:
            col_key = _resolve_web_collection(zot, collection)
        except Exception as e:  # noqa: BLE001
            return [ImportResult(i, "error", f"collection: {e}") for i in identifiers]
    results: list[ImportResult] = []
    for ident in identifiers:
        # Web API only reliably resolves a DOI via the journalArticle DOI field.
        if ident.startswith("arxiv:"):
            results.append(ImportResult(ident, "error", "arXiv ids unsupported via web backend; use --backend local"))
            continue
        try:
            kwargs = {"collections": [col_key]} if col_key else {}
            zot.create_items([{"itemType": "journalArticle", "DOI": ident}], **kwargs)
            results.append(ImportResult(ident, "added", "created (metadata resolves on next sync)"))
        except Exception as e:  # noqa: BLE001
            results.append(ImportResult(ident, "error", str(e)))
    return results


def _resolve_web_collection(zot, spec: str) -> str:
    """Resolve a collection name/key to its key via the Web API (top-level only)."""
    for c in zot.collections():
        key = c.get("key")
        name = (c.get("data") or {}).get("name", "")
        if key == spec or name == spec or name.lower() == spec.lower():
            return key
    raise ValueError(f"collection '{spec}' not found in top-level collections (web backend)")
