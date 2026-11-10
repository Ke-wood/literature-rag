"""Machine translation of abstracts.

Two backends, chosen automatically:

1. OpenAI-compatible chat endpoint (defaults to SiliconFlow's *free* Qwen model)
   — reliable and direct-reachable in China, zero per-abstract cost. Requires a
   free key in ``LITRAG_TRANSLATE_KEY`` or ``SILICONFLOW_API_KEY``.
2. translatepy (free online scraping, Google etc.) — used only when no API key is
   configured; often blocked in China, so every call is hard-timed-out.

Endpoint/model are overridable via ``LITRAG_TRANSLATE_BASE_URL`` /
``LITRAG_TRANSLATE_MODEL`` (e.g. point them at DeepSeek or any other
OpenAI-compatible service).

The AI (Claude) never reads source or translated abstracts; translation happens
programmatically here and the result only lands in the coarse md for the human.
"""
from __future__ import annotations

import os
import threading

_translator = None

DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"


def _api_key() -> str | None:
    return os.environ.get("LITRAG_TRANSLATE_KEY") or os.environ.get("SILICONFLOW_API_KEY")


def _get_translator():
    global _translator
    if _translator is None:
        from translatepy import Translator  # imported lazily; only fallback needs it
        _translator = Translator()
    return _translator


def _translate_via_api(text: str, timeout: float) -> str:
    """Translate via an OpenAI-compatible chat completions endpoint."""
    key = _api_key()
    base = os.environ.get("LITRAG_TRANSLATE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("LITRAG_TRANSLATE_MODEL", DEFAULT_MODEL)
    from ._http import post_with_fallback
    resp = post_with_fallback(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": "你是专业翻译。把用户输入的英文摘要翻译成简体中文，只输出译文本身，不要任何解释、不要原文、不要引号。"},
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": 2048,
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    content = (body.get("choices") or [{}])[0].get("message", {}).get("content", "")
    return (content or "").strip()


def translate(text: str | None, dest: str = "Chinese (Simplified)", timeout: float = 20.0) -> str:
    """Translate `text` to `dest`. Returns '' on failure, timeout, or empty input.

    Uses the OpenAI-compatible endpoint when a translation key is configured,
    else falls back to translatepy (hard-timed-out on a daemon thread).
    """
    if not text or not text.strip():
        return ""
    if _api_key():
        try:
            return _translate_via_api(text, timeout)
        except Exception:
            return ""
    return _translate_py(text, dest, timeout)


def _translate_py(text: str, dest: str, timeout: float) -> str:
    try:
        tr = _get_translator()
    except Exception:
        return ""
    box: dict = {}

    def _work() -> None:
        try:
            box["result"] = tr.translate(text, dest)
        except Exception:
            box["result"] = None

    t = threading.Thread(target=_work, daemon=True)
    t.start()
    t.join(timeout)

    result = box.get("result")
    if result is None:
        return ""
    try:
        return (result.result or "").strip()
    except Exception:
        return ""
