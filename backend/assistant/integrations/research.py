"""Planner -> researcher -> independent evidence verifier -> constrained writer.

Semantic Scholar Academic Graph v1 is called only when include_academic is true.
Untrusted research fetches use public IP pinning and revalidate every redirect.
Reachability is not corroboration: two distinct registrable domains must contain
evidence supporting the claim. This is automated evidence checking, not a truth
guarantee. Inaccessible, ambiguous, or unsupported claims remain unverified.
"""

from __future__ import annotations

import ipaddress
import os
import re
import socket
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit, urlunsplit

from .errors import ProviderError, UnsafeURLError

MAX_SOURCE_BYTES = 1_000_000
MAX_SOURCES = 18


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _normalise(text):
    return " ".join(str(text).split())


def resolve_public_url(url: str) -> tuple[str, str, str]:
    """Return original host, pinned URL, SNI host; no second DNS resolution."""
    if not isinstance(url, str) or len(url) > 4096 or any(ord(c) < 33 for c in url):
        raise UnsafeURLError("Invalid public URL.")
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").rstrip(".").encode("idna").decode("ascii")
        port = parsed.port
    except (ValueError, UnicodeError) as exc:
        raise UnsafeURLError("Invalid public URL.") from exc
    if parsed.scheme not in {"http", "https"} or not host or parsed.username or parsed.password:
        raise UnsafeURLError("Only public HTTP and HTTPS URLs without credentials are allowed.")
    if port not in {None, 80 if parsed.scheme == "http" else 443}:
        raise UnsafeURLError("Only default web ports are allowed.")
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")) or "%" in host:
        raise UnsafeURLError("Local network addresses are blocked.")
    port = port or (443 if parsed.scheme == "https" else 80)
    try:
        addresses = {record[4][0] for record in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)}
    except OSError as exc:
        raise UnsafeURLError("Source hostname could not be resolved.") from exc
    if not addresses:
        raise UnsafeURLError("Source hostname has no public address.")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        mapped = getattr(ip, "ipv4_mapped", None)
        if not ip.is_global or ip.is_multicast or (mapped and not mapped.is_global):
            raise UnsafeURLError("Private, reserved, and local network addresses are blocked.")
    address = sorted(addresses)[0]
    authority = f"[{address}]" if ":" in address else address
    pinned = urlunsplit((parsed.scheme, authority, parsed.path or "/", parsed.query, ""))
    return host, pinned, host


def safe_fetch(url: str, max_bytes=MAX_SOURCE_BYTES) -> dict:
    """Read a bounded public HTML/text resource. No cookies, proxies, or auth.

    httpcore's sni_hostname request extension verifies the original hostname
    while connecting to the validated numeric IP, closing DNS-rebinding gaps.
    """
    import httpx

    max_bytes = min(max(int(max_bytes), 1), MAX_SOURCE_BYTES)
    current = url
    deadline = time.monotonic() + 25
    with httpx.Client(timeout=httpx.Timeout(8, connect=5), follow_redirects=False, trust_env=False) as client:
        for _ in range(5):
            host, pinned, sni = resolve_public_url(current)
            if time.monotonic() >= deadline:
                raise ProviderError("Source fetch exceeded its time limit.")
            with client.stream("GET", pinned, headers={"Host": host, "User-Agent": "LilyLeoX-Research/1.0", "Accept": "text/html,text/plain"},
                               extensions={"sni_hostname": sni}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ProviderError("Source returned an invalid redirect.")
                    current = urljoin(current, location)
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml+xml")):
                    raise ProviderError("Source is not readable HTML or text.")
                content_length = response.headers.get("content-length", "")
                if content_length.isdigit() and int(content_length) > max_bytes:
                    raise ProviderError("Source exceeds the download limit.")
                body = bytearray()
                for part in response.iter_bytes():
                    if time.monotonic() >= deadline or len(body) + len(part) > max_bytes:
                        raise ProviderError("Source exceeds the time or download limit.")
                    body.extend(part)
                text = bytes(body).decode(response.encoding or "utf-8", errors="replace")
                if "html" in content_type:
                    parser = _TextParser()
                    parser.feed(text)
                    text = " ".join(parser.parts)
                return {"url": current, "text": _normalise(text)[:100000], "reachable": True}
    raise ProviderError("Source exceeded the redirect limit.")


def academic_search(query: str) -> list[dict]:
    import httpx

    key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "")
    headers = {"x-api-key": key} if key else {}
    try:
        response = httpx.get("https://api.semanticscholar.org/graph/v1/paper/search", params={"query": query[:500], "limit": 5,
                            "fields": "title,url,abstract,year,externalIds"}, headers=headers, timeout=15, follow_redirects=False)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ProviderError("Semantic Scholar search is unavailable.") from exc
    return [{"url": item.get("url", ""), "title": item.get("title", ""), "abstract": (item.get("abstract") or "")[:3000]}
            for item in data.get("data", [])[:5] if isinstance(item, dict) and item.get("url", "").startswith("https://")]


def registrable_domain(url: str) -> str:
    import tldextract

    host = urlsplit(url).hostname or ""
    extractor = tldextract.TLDExtract(suffix_list_urls=(), include_psl_private_domains=True)
    result = extractor(host)
    # Unknown suffixes and numeric addresses cannot establish independence.
    return result.top_domain_under_public_suffix if result.suffix else ""


def _evidence_window(text, claim, maximum=7000):
    if len(text) <= maximum:
        return text
    words = sorted(set(re.findall(r"[A-Za-z]{5,}", claim)), key=len, reverse=True)
    positions = [text.lower().find(word.lower()) for word in words[:12]]
    positions = [pos for pos in positions if pos >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - 1000)
    return text[start:start + maximum]


def run_research(topic: str, gateway, include_academic=True) -> dict:
    from .gemini import _topic

    topic = _topic(topic)
    queries = gateway.plan_research(topic)[:3]
    sources, claims, errors, search_suggestions = {}, [], [], []
    for query in queries:
        result = gateway.grounded_search(query)
        if result.get("search_suggestions_html"):
            search_suggestions.append(result["search_suggestions_html"])
        for source in result.get("sources", [])[:MAX_SOURCES]:
            if isinstance(source, dict) and isinstance(source.get("url"), str) and len(sources) < MAX_SOURCES:
                sources.setdefault(source["url"], {"url": source["url"], "title": str(source.get("title") or source["url"])[:500]})
        for claim in result.get("claims", [])[:12]:
            if isinstance(claim, dict) and isinstance(claim.get("text"), str) and claim["text"].strip() and len(claims) < 20:
                if claim["text"] not in {c["text"] for c in claims}:
                    claims.append({"text": claim["text"][:3000], "source_urls": list(dict.fromkeys(u for u in claim.get("source_urls", []) if isinstance(u, str)))[:8]})
    if include_academic:
        try:
            for paper in academic_search(topic):
                if len(sources) < MAX_SOURCES:
                    sources.setdefault(paper["url"], {"url": paper["url"], "title": paper["title"], "kind": "academic"})
                if paper["abstract"] and len(claims) < 20:
                    claims.append({"text": paper["abstract"], "source_urls": [paper["url"]]})
        except ProviderError as exc:
            errors.append(str(exc))

    fetched = {}
    for url, source in sources.items():
        try:
            evidence = safe_fetch(url)
            fetched[url] = evidence
            source.update({"reachable": True, "resolved_url": evidence["url"], "domain": registrable_domain(evidence["url"])})
        except Exception as exc:
            # A single inaccessible site should not destroy the research job.
            source.update({"reachable": False, "error": "Source blocked by public-network policy." if isinstance(exc, UnsafeURLError) else "Source could not be independently retrieved."})

    findings = []
    for claim in claims:
        known_urls = [url for url in claim["source_urls"] if url in sources]
        evidence = [{"url": url, "text": _evidence_window(fetched[url]["text"], claim["text"])} for url in known_urls if url in fetched]
        judgments = []
        if evidence and hasattr(gateway, "verify_evidence"):
            try:
                judgments = gateway.verify_evidence(claim["text"], evidence)
            except ProviderError:
                pass
        # A deterministic exact occurrence is also useful for simple atomic
        # claims, but never infer support from reachability or word overlap.
        if not judgments:
            judgments = [{"url": item["url"], "supports": True, "quote": claim["text"]}
                         for item in evidence if _normalise(claim["text"]).casefold() in _normalise(item["text"]).casefold()]
        supporting, excerpts, domains = [], [], set()
        for judgment in judgments:
            url = judgment.get("url")
            quote = _normalise(judgment.get("quote", ""))
            if (judgment.get("supports") is True and url in known_urls and url in fetched and len(quote) >= 12
                    and quote.casefold() in _normalise(fetched[url]["text"]).casefold()):
                supporting.append(url)
                excerpts.append({"url": url, "quote": quote[:1200]})
                domain = sources[url].get("domain")
                if domain:
                    domains.add(domain)
        verified = len(domains) >= 2
        findings.append({"text": claim["text"], "source_urls": known_urls, "verified": verified,
                         "verification_status": "verified" if verified else "unverified",
                         "supporting_source_urls": list(dict.fromkeys(supporting)), "evidence": excerpts,
                         "verification_reason": "Supporting evidence from two independent domains." if verified else "Fewer than two independent domains supplied supporting evidence."})
    written = gateway.write_report(topic, findings)
    # Only our verifier's findings/citations are returned; the writer cannot
    # replace them with invented items, source links, or verification statuses.
    return {"title": topic, "executive_summary": written.get("executive_summary", ""), "key_findings": findings,
            "next_steps": written.get("next_steps", []), "sources": list(sources.values()),
            "citations": [{"url": source["url"], "title": source["title"]} for source in sources.values()],
            "errors": errors, "search_suggestions_html": search_suggestions}
