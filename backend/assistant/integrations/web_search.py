"""Keyless public search discovery; source fetches still use the research policy."""

from .errors import ConfigError, ProviderError, UnsafeURLError
from .model_base import _topic


def public_search(query):
    query = _topic(query)
    try:
        from ddgs import DDGS
    except ImportError:
        raise ConfigError("Install project requirements to enable public web search with local models.") from None
    try:
        results = DDGS(timeout=15).text(query, max_results=6, backend="auto")
    except Exception:
        raise ProviderError("Public web search is unavailable or rate limited. Local chat still works; retry research later.") from None
    from .research import resolve_public_url
    sources, claims, seen = [], [], set()
    for item in results[:6]:
        url = item.get("href", "")
        if not isinstance(url, str) or url in seen:
            continue
        try:
            resolve_public_url(url)
        except (ValueError, UnsafeURLError):
            continue
        seen.add(url)
        title, snippet = str(item.get("title", url))[:500], str(item.get("body", ""))[:1500]
        sources.append({"url": url, "title": title})
        if snippet.strip():
            claims.append({"text": snippet, "source_urls": [url]})
    if not sources:
        raise ProviderError("Public search returned no usable sources. No current facts were inferred from local-model memory.")
    return {"text": "Unverified public search snippets; independently check the linked pages.\n\n" +
            "\n\n".join(f"{item['text']}\n{item['source_urls'][0]}" for item in claims),
            "sources": sources, "claims": claims, "search_suggestions_html": ""}
