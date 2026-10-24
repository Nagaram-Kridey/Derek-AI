from datetime import timedelta
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient
from assistant.models import DesktopLaunchGrant

HOST = {'HTTP_HOST':'127.0.0.1:8000','REMOTE_ADDR':'127.0.0.1'}


def issue(user,settings):
    settings.LOCAL_EXECUTION = True
    token,_=Token.objects.get_or_create(user=user)
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Token '+token.key)
    response=client.post('/v1/local/session/launch/',{},format='json',**HOST)
    assert response.status_code==200
    return response.json()['code'],token


def exchange(code,**headers):
    return APIClient().post('/v1/local/session/exchange/',{'code':code},format='json',**{**HOST,'HTTP_ORIGIN':'http://127.0.0.1:8000',**headers})


def test_launch_is_one_use_and_contains_no_owner_token(user,settings):
    code,token=issue(user,settings)
    row=DesktopLaunchGrant.objects.get()
    assert code not in row.digest and token.key not in row.token_digest
    result=exchange(code)
    assert result.status_code==200 and result.json()['token']==token.key
    assert 'no-store' in result['Cache-Control']
    assert exchange(code).status_code==401


def test_origin_remote_and_cloud_rejected(user,settings):
    code,_=issue(user,settings)
    for headers in [{'HTTP_ORIGIN':'https://evil.example'},{'REMOTE_ADDR':'192.168.1.2'},{'HTTP_X_FORWARDED_FOR':'127.0.0.1'}]:
        assert exchange(code,**headers).status_code==403
    settings.LOCAL_EXECUTION=False
    assert exchange(code).status_code==403


def test_expiry_logout_and_rotation_invalidate_launch(user,settings):
    code,token=issue(user,settings)
    DesktopLaunchGrant.objects.update(expires_at=timezone.now()-timedelta(seconds=1))
    assert exchange(code).status_code==401
    code,token=issue(user,settings)
    token.delete()
    Token.objects.create(user=user)
    assert exchange(code).status_code==401


def test_unauthenticated_site_cannot_issue_launch(settings):
    settings.LOCAL_EXECUTION=True
    assert APIClient().post('/v1/local/session/launch/',{},format='json',**HOST).status_code in (401,403)


def test_authenticated_browser_cannot_issue_and_malformed_json_is_controlled(user,settings):
    code,token=issue(user,settings)
    client=APIClient(); client.credentials(HTTP_AUTHORIZATION='Token '+token.key)
    assert client.post('/v1/local/session/launch/',{},format='json',HTTP_ORIGIN='http://127.0.0.1:8000',**HOST).status_code==403
    assert APIClient().post('/v1/local/session/exchange/',[],format='json',HTTP_ORIGIN='http://127.0.0.1:8000',**HOST).status_code==400
    assert exchange(code,HTTP_ORIGIN='').status_code==403


def test_actual_logout_invalidates_launch(user,settings):
    code,token=issue(user,settings)
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Token '+token.key)
    assert client.post('/v1/auth/logout',{},format='json').status_code==200
    assert exchange(code).status_code==401


def test_inactive_owner_and_replaced_handoff_rejected(user,settings):
    first,_=issue(user,settings)
    second,_=issue(user,settings)
    assert exchange(first).status_code==401
    user.is_active=False;user.save()
    assert exchange(second).status_code==401
