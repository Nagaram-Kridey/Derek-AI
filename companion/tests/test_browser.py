from unittest.mock import Mock
import pytest
from companion.browser import execute_actions
from companion.policy import ApprovalRequired, AttentionRequired, DomainPolicy

def page_fixture(body_text="Ready", button_text="Pay now"):
    body=Mock();body.inner_text.return_value=body_text
    target=Mock();target.inner_text.return_value=button_text
    target.get_attribute.return_value=None
    target.count.return_value=1;target.is_visible.return_value=True;target.is_enabled.return_value=True
    absent=Mock();absent.all.return_value=[]
    page=Mock();page.url="https://example.com/"
    page.locator.side_effect=lambda selector: body if selector=="body" else target if selector=="#action" else absent
    policy=DomainPolicy(["example.com"],lambda *a,**kw:[(2,1,6,"",("93.184.216.34",443))])
    action={"type":"click","selector":"#action","expected_url":page.url,"expected_text":"Ready"}
    return page,target,policy,action

def test_detected_money_action_cannot_self_authorize():
    page,target,policy,action=page_fixture()
    with pytest.raises(ApprovalRequired):execute_actions(page,[action],policy)
    target.click.assert_not_called()

def test_approval_is_consumed_once_at_its_checkpoint():
    page,target,policy,action=page_fixture()
    checkpoints=[]
    with pytest.raises(ApprovalRequired):execute_actions(page,[action,action],policy,approved_risk="payment",checkpoint=checkpoints.append)
    assert target.click.call_count==1 and max(checkpoints)==1

def test_challenge_or_wrong_page_stops_without_click():
    page,target,policy,action=page_fixture("Enter verification code")
    with pytest.raises(AttentionRequired):execute_actions(page,[action],policy)
    target.click.assert_not_called()
    page,target,policy,action=page_fixture(button_text="Save")
    action["expected_url"]="https://example.com/another"
    with pytest.raises(AttentionRequired):execute_actions(page,[action],policy)
    target.click.assert_not_called()
