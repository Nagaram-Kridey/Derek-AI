from unittest.mock import patch
from types import SimpleNamespace
from pathlib import Path
import pytest
from docx import Document
from assistant.integrations.docs import generate_report
from assistant.integrations.research import resolve_public_url, run_research
from assistant.integrations.errors import UnsafeURLError
from assistant.integrations.gemini import GeminiGateway

@pytest.mark.parametrize("url", ["https://localhost/", "http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "https://user:pass@example.com/", "file:///etc/passwd", "http://example.com:8080"])
def test_research_blocks_ssrf(url):
    with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 80))]):
        with pytest.raises(UnsafeURLError):
            resolve_public_url(url)

def test_source_domain_count_requires_actual_support():
    from assistant.integrations import research
    gateway = SimpleNamespace(plan_research=lambda t: [t], grounded_search=lambda q: {"sources": [{"url": "https://a.org/x", "title": "A"}, {"url": "https://b.org/x", "title": "B"}], "claims": [{"text": "The moon orbits Earth.", "source_urls": ["https://a.org/x", "https://b.org/x"]}]}, write_report=lambda t,f: {"executive_summary": "Summary", "next_steps": []})
    with patch.object(research, "safe_fetch", side_effect=lambda url: {"url": url, "text": "The moon orbits Earth.", "reachable": True}):
        result = run_research("Moon", gateway, False)
    assert result["key_findings"][0]["verified"]
    with patch.object(research, "safe_fetch", side_effect=lambda url: {"url": url, "text": "Unrelated content", "reachable": True}):
        result = run_research("Moon", gateway, False)
    assert not result["key_findings"][0]["verified"]

def test_subdomains_do_not_establish_independence():
    from assistant.integrations.research import registrable_domain
    assert registrable_domain("https://a.example.com") == registrable_domain("https://b.example.com")

def test_report_formats_and_labels(tmp_path):
    output = generate_report({"title": "Research", "executive_summary": "Summary", "key_findings": [{"text": "Uncertain finding", "verified": False, "source_urls": ["https://example.com"]}], "sources": [{"url": "https://example.com", "title": "Source", "reachable": True}], "next_steps": ["Verify"]}, tmp_path)
    assert Path(output["pdf"]).read_bytes().startswith(b"%PDF")
    text = "\n".join(p.text for p in Document(output["docx"]).paragraphs)
    assert "Unverified: Uncertain finding" in text and "https://example.com" in text

def test_gemini_call_and_grounding_contract():
    gateway = GeminiGateway("test", "test-model")
    with patch.object(gateway, "_generate", return_value=SimpleNamespace(text="", function_calls=[SimpleNamespace(name="schedule_task", args={"name": "Reminder"})])):
        result = gateway.chat([{"role": "user", "content": "Reminder"}], [])
    assert result["tool_calls"][0]["name"] == "schedule_task"

def test_calendar_owned_scope_and_no_delete_tool():
    from assistant.integrations.calendar import build_auth_url
    from assistant.contracts import SCHEMAS
    from urllib.parse import parse_qs, urlsplit
    url = build_auth_url("client", "http://localhost/callback", "unpredictable-oauth-state-1234567890")
    assert parse_qs(urlsplit(url).query)["scope"] == ["https://www.googleapis.com/auth/calendar.events.owned"]
    assert "calendar.delete" not in SCHEMAS
