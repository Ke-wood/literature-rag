"""Read-only Zotero local API helpers (collections)."""
from __future__ import annotations

import requests

LOCAL_API = "http://127.0.0.1:23119"
COLLECTIONS_URL = f"{LOCAL_API}/api/users/0/collections"
ITEMS_URL = f"{LOCAL_API}/api/users/0/items"


def list_collections(timeout: int = 8) -> list[dict]:
    """Return [{"key", "name", "parent"}] for every collection in the local library."""
    r = requests.get(COLLECTIONS_URL, timeout=timeout)
    r.raise_for_status()
    payload = r.json()
    items = payload if isinstance(payload, list) else payload.get("items", [])
    out: list[dict] = []
    for c in items:
        data = c.get("data") or {}
        out.append({
            "key": c.get("key"),
            "name": data.get("name", ""),
            "parent": data.get("parentCollection") or None,
        })
    return out


def resolve_collection(spec: str, timeout: int = 8) -> str:
    """Resolve a collection name or key to its key (raises ValueError if not found)."""
    cols = list_collections(timeout)
    for c in cols:
        if c["key"] == spec:
            return spec
    for c in cols:
        if c["name"] == spec:
            return c["key"]
    for c in cols:
        if c["name"].lower() == spec.lower():
            return c["key"]
    raise ValueError(f"collection '{spec}' not found; available: {[c['name'] for c in cols]}")


def list_existing_dois(timeout: int = 20, limit: int = 100) -> set[str]:
    """Return the set of normalized DOIs already in the local Zotero library.

    Used for dedup before screening so known papers don't waste screening tokens.
    """
    from .models import normalize_doi

    dois: set[str] = set()
    start = 0
    while True:
        r = requests.get(
            ITEMS_URL,
            params={"format": "json", "limit": limit, "start": start},
            timeout=timeout,
        )
        r.raise_for_status()
        items = r.json()
        if isinstance(items, dict):
            items = items.get("items", [])
        if not items:
            break
        for it in items:
            doi = (it.get("data") or {}).get("DOI")
            if doi:
                d = normalize_doi(doi)
                if d:
                    dois.add(d)
        if len(items) < limit:
            break
        start += limit
        if start > 50000:  # safety cap: a huge library won't loop forever
            break
    return dois
