from unittest.mock import Mock, patch
from urllib.request import HTTPRedirectHandler
from desktop.session import NoRedirect, ORIGIN, workspace_url


def test_handoff_falls_back_without_stored_credential():
    with patch('desktop.session.read_owner_token',return_value=None),patch('desktop.session.build_opener') as opener:
        assert workspace_url()==ORIGIN
        opener.assert_not_called()


def test_handoff_url_has_only_one_time_code_and_redirects_disabled():
    response=Mock()
    response.read.return_value=b'{"code":"' + b'x'*43 + b'"}'
    opened=Mock();opened.open.return_value.__enter__=Mock(return_value=response);opened.open.return_value.__exit__=Mock(return_value=False)
    with patch('desktop.session.read_owner_token',return_value='a'*40),patch('desktop.session.build_opener',return_value=opened) as build:
        url=workspace_url()
    assert 'a'*40 not in url and url.endswith('x'*43)
    assert any(isinstance(handler,NoRedirect) for handler in build.call_args.args)
    assert NoRedirect().redirect_request(None,None,None,None,None,None) is None
    assert isinstance(NoRedirect(),HTTPRedirectHandler)
