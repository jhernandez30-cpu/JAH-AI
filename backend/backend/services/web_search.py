from __future__ import annotations

import os
from typing import Any


WEB_SEARCH_UNCONFIGURED_MESSAGE = (
    "La Busqueda inteligente esta activada, pero todavia no hay una API de busqueda web configurada."
)


def configured_provider() -> tuple[str, str]:
    provider = os.getenv("WEB_SEARCH_PROVIDER", "tavily").strip().lower()
    keys = {
        "tavily": os.getenv("TAVILY_API_KEY", "").strip(),
        "serpapi": os.getenv("SERPAPI_API_KEY", "").strip(),
        "brave": os.getenv("BRAVE_API_KEY", "").strip(),
        "bing": os.getenv("BING_SEARCH_API_KEY", "").strip(),
    }
    key = keys.get(provider, "")
    if key:
        return provider, key
    for fallback_provider, fallback_key in keys.items():
        if fallback_key:
            return fallback_provider, fallback_key
    return provider, ""


def web_search_configured() -> bool:
    return bool(configured_provider()[1])


async def _request_json(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    try:
        import httpx
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Instala httpx para usar busqueda web.") from exc

    timeout = float(os.getenv("WEB_SEARCH_TIMEOUT", "12"))
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {}


def _clean_results(results: list[dict[str, Any]], max_results: int) -> list[dict[str, Any]]:
    clean: list[dict[str, Any]] = []
    for item in results:
        title = str(item.get("title") or item.get("name") or "").strip()
        url = str(item.get("url") or item.get("link") or "").strip()
        snippet = str(item.get("snippet") or item.get("description") or item.get("content") or "").strip()
        if not (title or url or snippet):
            continue
        clean.append(
            {
                "title": title or url,
                "url": url,
                "snippet": snippet[:800],
                "source": "web",
            }
        )
        if len(clean) >= max_results:
            break
    return clean


async def _search_tavily(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    data = await _request_json(
        "POST",
        "https://api.tavily.com/search",
        json={
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        },
    )
    return _clean_results(data.get("results") or [], max_results)


async def _search_serpapi(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    data = await _request_json(
        "GET",
        "https://serpapi.com/search.json",
        params={"engine": "google", "q": query, "api_key": api_key, "num": max_results, "hl": "es"},
    )
    return _clean_results(data.get("organic_results") or [], max_results)


async def _search_brave(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    data = await _request_json(
        "GET",
        "https://api.search.brave.com/res/v1/web/search",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params={"q": query, "count": max_results, "search_lang": "es"},
    )
    web = data.get("web") if isinstance(data.get("web"), dict) else {}
    return _clean_results(web.get("results") or [], max_results)


async def _search_bing(query: str, api_key: str, max_results: int) -> list[dict[str, Any]]:
    data = await _request_json(
        "GET",
        "https://api.bing.microsoft.com/v7.0/search",
        headers={"Ocp-Apim-Subscription-Key": api_key},
        params={"q": query, "count": max_results, "mkt": "es-US"},
    )
    web_pages = data.get("webPages") if isinstance(data.get("webPages"), dict) else {}
    return _clean_results(web_pages.get("value") or [], max_results)


async def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    clean_query = str(query or "").strip()
    if not clean_query:
        return []
    provider, api_key = configured_provider()
    if not api_key:
        return []

    try:
        if provider == "serpapi":
            return await _search_serpapi(clean_query, api_key, max_results)
        if provider == "brave":
            return await _search_brave(clean_query, api_key, max_results)
        if provider == "bing":
            return await _search_bing(clean_query, api_key, max_results)
        return await _search_tavily(clean_query, api_key, max_results)
    except Exception:
        return []
