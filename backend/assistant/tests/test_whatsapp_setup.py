from unittest.mock import patch


def test_setup_is_local_authenticated_and_fixed_target(client,settings):
    settings.LOCAL_EXECUTION=False
    assert client.post('/v1/local/whatsapp/',{},format='json').status_code==409
    settings.LOCAL_EXECUTION=True
    with patch('companion.whatsapp_web.open_login',return_value={'opened':True}) as opened:
        assert client.post('/v1/local/whatsapp/',{'url':'https://example.com'},format='json').status_code==400
        opened.assert_not_called()
        result=client.post('/v1/local/whatsapp/',{},format='json')
    assert result.status_code==200
    assert opened.call_args.args[0].name=='whatsapp-brave-profile'
    from rest_framework.test import APIClient
    assert APIClient().get('/v1/local/whatsapp/').status_code in {401,403}


def test_status_does_not_start_a_browser(client,settings):
    settings.LOCAL_EXECUTION=True
    with patch('companion.whatsapp_web.status',return_value={'state':'relink_required'}), \
         patch('companion.whatsapp_web.open_login') as opened:
        result=client.get('/v1/local/whatsapp/')
    assert result.data['state']=='relink_required'
    opened.assert_not_called()
