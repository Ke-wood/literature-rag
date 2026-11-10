"""HTTP helpers with direct-then-proxy fallback.

China deployments: most academic APIs (Crossref / OpenAlex / Semantic Scholar /
DeepSeek) are reachable *directly* and a local proxy (Clash) can be flaky, while
arXiv is often blocked direct but reachable via a healthy proxy. Rather than pick
one path (and silently lose a source), we try direct first and fall back to the
system proxy, returning whichever succeeds.
"""
from __future__ import annotations

import requests

_DIRECT = {"http": None, "https": None}


def _fallback(method, url: str, **kwargs):
    last = None
    # direct first, then system proxy (proxies=None -> env/registry proxy)
    for proxies in (_DIRECT, None):
        try:
            return method(url, proxies=proxies, **kwargs)
        except requests.RequestException as e:  # noqa: BLE001 - keep the last error, try next path
            last = e
    raise last


def get_with_fallback(url: str, params=None, headers=None, timeout: int = 15, **kwargs):
    return _fallback(requests.get, url, params=params, headers=headers, timeout=timeout, **kwargs)


def post_with_fallback(url: str, json=None, headers=None, timeout: int = 30, **kwargs):
    return _fallback(requests.post, url, json=json, headers=headers, timeout=timeout, **kwargs)
