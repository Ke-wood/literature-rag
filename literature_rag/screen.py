"""Screen papers by abstract via DeepSeek — Claude never reads the abstracts.

This is the token-saving core of the pipeline: the (cheap) DeepSeek model reads
every abstract and returns only ``{doi, verdict, reason}``, so the orchestrating
Claude session sees verdicts instead of hundreds of abstracts.

Config (env vars, all optional with sane defaults):
- DEEPSEEK_API_KEY   default: $ANTHROPIC_AUTH_TOKEN (reuses the Claude Code key)
- DEEPSEEK_MODEL     default: deepseek-v4-flash
- DEEPSEEK_BASE_URL  default: https://api.deepseek.com/anthropic
  (Anthropic Messages API format; the same endpoint Claude Code talks to.)
"""
from __future__ import annotations

import json
import os

from ._http import post_with_fallback

DEFAULT_BASE_URL = "https://api.deepseek.com/anthropic"
DEFAULT_MODEL = "deepseek-v4-flash"
CHUNK = 20          # papers per request (thinking disabled → larger chunks amortize fixed prompt cost)
MAX_ABS = 800       # chars of abstract sent per paper (venue/authors/keywords added to compensate)
MAX_TOKENS = 8192   # enough for the reasoning phase + the JSON verdicts

_VERDICTS = {"include", "exclude", "uncertain"}


def _cfg(api_key=None, model=None, base_url=None) -> tuple[str, str, str]:
    key = api_key or os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not key:
        raise RuntimeError(
            "缺少 DeepSeek key：请设置 DEEPSEEK_API_KEY（或 ANTHROPIC_AUTH_TOKEN）"
        )
    model = model or os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL)
    base = (base_url or os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
    return key, model, base


def screen(papers, topic: str, api_key=None, model=None, base_url=None,
           criteria: str | None = None, timeout: int = 180) -> list[dict]:
    """Screen a list of Paper objects; return [{doi, title, verdict, reason}]."""
    key, model, base = _cfg(api_key, model, base_url)
    out: list[dict] = []
    for i in range(0, len(papers), CHUNK):
        chunk = papers[i:i + CHUNK]
        out.extend(_screen_chunk(chunk, topic, key, model, base, criteria, timeout))
    return out


def _call(key, model, base, prompt, timeout) -> str:
    """POST to DeepSeek and return the concatenated text blocks."""
    resp = post_with_fallback(
        f"{base}/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
            "thinking": {"type": "disabled"},  # non-reasoning: answer directly, no budget blown on thinking
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    body = resp.json()
    content = body.get("content") or []
    text = ""
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text += block.get("text", "")
    return text


def _screen_chunk(papers, topic, key, model, base, criteria, timeout) -> list[dict]:
    lines = []
    for n, p in enumerate(papers, 1):
        abs_ = (p.abstract or "").strip()
        if len(abs_) > MAX_ABS:
            abs_ = abs_[:MAX_ABS] + "…"
        auth = ", ".join(p.authors[:2]) if p.authors else ""
        kw = ", ".join(p.keywords[:3]) if getattr(p, "keywords", None) else ""
        meta = f"[{p.journal or '?'}] {auth}" + (f" [{kw}]" if kw else "")
        lines.append(f"{n}. {p.title}\n   {meta}\n   {abs_ or '（无摘要）'}")
    criteria_line = criteria or "与主题直接相关（研究对象 / 化合物 / 介质 / 方法学）"
    prompt = (
        "你是文献筛选专家。判断下面每篇论文是否与主题相关，只输出 JSON。\n"
        f"主题：{topic}\n"
        f"筛选标准：{criteria_line}\n\n"
        + "\n".join(lines)
        + '\n\n只输出一个 JSON 对象：{"results":[{"i":1,"verdict":"include","reason":"一句话中文理由"}]}'
        "\nverdict 只能是 include / exclude / uncertain。"
    )

    text = _call(key, model, base, prompt, timeout)
    results = _parse_results(text)
    if not results and papers:
        # transient empty/truncated reply (flaky proxy) — retry once
        text = _call(key, model, base, prompt, timeout)
        results = _parse_results(text)
    if not results and papers:
        raise RuntimeError(
            f"DeepSeek 返回无法解析（{len(papers)} 篇），回复前 200 字：{text[:200]!r}"
        )

    by_i = {int(r.get("i")): r for r in results if r.get("i") is not None}
    out = []
    for n, p in enumerate(papers, 1):
        r = by_i.get(n, {})
        verdict = str(r.get("verdict", "uncertain")).strip().lower()
        if verdict not in _VERDICTS:
            verdict = "uncertain"
        out.append({
            "doi": p.doi,
            "title": p.title,
            "verdict": verdict,
            "reason": str(r.get("reason", ""))[:30],
        })
    return out


def _parse_results(text: str) -> list[dict]:
    """Tolerantly extract {"results": [...]} from a model text reply."""
    text = text.strip()
    # strip code fences if present
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
    try:
        data = json.loads(text)
    except ValueError:
        # try to salvage the first JSON object/array inside the text
        start = text.find("{")
        if start == -1:
            start = text.find("[")
        if start == -1:
            return []
        depth = 0
        for i in range(start, len(text)):
            c = text[i]
            if c in "{[":
                depth += 1
            elif c in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(text[start:i + 1])
                    except ValueError:
                        return []
                    break
        else:
            return []
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    if isinstance(data, list):
        return data
    return []
