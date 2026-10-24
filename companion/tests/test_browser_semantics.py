from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from assistant.contracts import BrowserAction, validate_workflow
from companion.browser import execute_actions, resolve_target
from companion.policy import AttentionRequired, PolicyError
from companion.tests.test_browser import page_fixture


@pytest.mark.parametrize("by,method", [("label", "get_by_label"), ("text", "get_by_text"), ("placeholder", "get_by_placeholder"), ("test_id", "get_by_test_id")])
def test_semantic_locators_use_exact_names(by, method):
    page = Mock()
    resolve_target(page, {"target": {"by": by, "value": "Search"}})
    getattr(page, method).assert_called_once_with("Search", **({} if by == "test_id" else {"exact": True}))


def test_role_click_preserves_risk_page_and_checkpoint_checks():
    page, target, domains, action = page_fixture(button_text="Save")
    action.pop("selector")
    action["target"] = {"by": "role", "value": "button", "name": "Save"}
    page.get_by_role.return_value = target
    before, checkpoints = [], []
    execute_actions(page, [action], domains, before_mutation=before.append, checkpoint=checkpoints.append)
    page.get_by_role.assert_called_with("button", name="Save", exact=True)
    target.click.assert_called_once()
    assert before == [0] and checkpoints == [1, 1]
    target.count.return_value = 2
    with pytest.raises(AttentionRequired):
        execute_actions(page, [action], domains)
    assert target.click.call_count == 1


def test_wait_scroll_and_read_are_bounded_and_observed():
    page, target, domains, _ = page_fixture(button_text="Save")
    page.get_by_text.return_value = target
    actions = [{"type": kind, "target": {"by": "text", "value": "Save"}, "timeout_ms": 750} for kind in ["wait", "scroll", "read"]]
    result = execute_actions(page, actions, domains)
    target.wait_for.assert_called_once_with(state="visible", timeout=750)
    target.scroll_into_view_if_needed.assert_called_once()
    assert result["observations"][0]["text"] == "Save"
    with pytest.raises(PolicyError):
        execute_actions(page, [{**actions[0], "timeout_ms": 60000}], domains)


@pytest.mark.parametrize("action", [
    {"type": "click", "target": {"by": "role", "value": "button"}},
    {"type": "read", "selector": "body", "target": {"by": "text", "value": "Hi"}},
    {"type": "wait", "selector": "body", "timeout_ms": 60000},
    {"type": "click", "target": {"by": "text", "value": "Pay"}},
])
def test_contract_rejects_incomplete_or_ambiguous_actions(action):
    with pytest.raises(ValidationError):
        BrowserAction.model_validate(action)


def test_read_body_default_and_semantic_target_cannot_escape_domain_review():
    assert BrowserAction(type="read").model_dump()["selector"] is None
    with pytest.raises(ValueError, match="outside"):
        validate_workflow({"allowed_tools": ["browser.run"], "allowed_domains": ["example.com"],
            "steps": [{"tool": "browser.run", "args": {"actions": [{"type": "click", "target": {"by": "role", "value": "button", "name": "Save"}, "expected_url": "https://evil.com/", "expected_text": "Ready"}]}}]})
