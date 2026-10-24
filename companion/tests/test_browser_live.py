"""Opt-in real-browser fixture acceptance; no account/profile or external site."""
import os
from pathlib import Path

import pytest

from companion.browser import execute_actions
from companion.policy import ApprovalRequired, AttentionRequired, DomainPolicy


@pytest.mark.skipif(os.getenv("DEREK_BROWSER_ACCEPTANCE") != "1", reason="Opt in with DEREK_BROWSER_ACCEPTANCE=1; requires installed Chrome")
def test_real_chrome_semantic_workflow_and_gates(tmp_path):
    from playwright.sync_api import sync_playwright
    url = "https://example.com/"
    html = Path(__file__).with_name("browser_fixture.html").read_text(encoding="utf-8")
    domains = DomainPolicy(["example.com"], lambda *a, **k: [(2, 1, 6, "", ("93.184.216.34", 443))])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True, args=["--disable-background-networking"])
        try:
            context = browser.new_context(service_workers="block", accept_downloads=False)
            context.route("**/*", lambda r: r.fulfill(status=200, content_type="text/html", body=html) if r.request.url == url else r.abort())
            page = context.new_page()
            guard = {"expected_url": url, "expected_text": "Automation test page"}
            actions = [
                {"type": "navigate", "url": url},
                {"type": "wait", "target": {"by": "text", "value": "Ready for work"}, "timeout_ms": 2000},
                {"type": "fill", "target": {"by": "label", "value": "Project name"}, "value": "Derek fixture", **guard},
                {"type": "select", "target": {"by": "label", "value": "Priority"}, "value": "high", **guard},
                {"type": "click", "target": {"by": "role", "value": "button", "name": "Save project"}, **guard},
                {"type": "scroll", "target": {"by": "test_id", "value": "result"}},
                {"type": "read", "target": {"by": "test_id", "value": "result"}},
            ]
            before, completed = [], []
            result = execute_actions(page, actions, domains, before_mutation=before.append, checkpoint=completed.append)
            assert result["observations"][0]["text"] == "Saved locally"
            assert page.get_by_label("Project name").input_value() == "Derek fixture"
            assert page.get_by_label("Priority").input_value() == "high"
            assert before == [2, 3, 4] and completed[-1] == 7
            with pytest.raises(ApprovalRequired):
                execute_actions(page, [{**actions[4], "target": {"by": "role", "value": "button", "name": "Pay now"}}], domains)
            assert page.get_by_test_id("result").inner_text() == "Saved locally"
            with pytest.raises(AttentionRequired):
                execute_actions(page, [{**actions[4], "expected_url": url + "unexpected"}], domains)
            page.set_content('<body>Automation test page<button>Save project</button><button>Save project</button></body>')
            with pytest.raises(AttentionRequired):
                execute_actions(page, [actions[4]], domains)
            page.set_content('<body>Enter verification code<input autocomplete="one-time-code"></body>')
            with pytest.raises(AttentionRequired):
                execute_actions(page, [{"type": "read"}], domains)
        finally:
            browser.close()
