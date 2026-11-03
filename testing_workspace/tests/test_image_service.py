from testing_workspace import image_service as service


def test_gate_requires_evidence_and_explicit_enable(tmp_path, monkeypatch):
    monkeypatch.setattr(service, 'DATA', tmp_path)
    assert service.validated_gate()['enabled'] is False
    model = tmp_path / 'model.safetensors'
    model.write_bytes(b'fixture')
    stat=model.stat()
    registration={'path':str(model),'sha256':service.sha256(model),'pin':service.PIN,'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
    service.write('image-checkpoint.json',registration)
    service.write('config.json',{'images_enable_testers':True})
    assert service.validated_gate()['enabled'] is False
    evidence={'passed':True,'pin':service.PIN,'checkpoint_sha256':registration['sha256'],'api_verified':True,'results':[{'seconds':30,'chat_ok':True} for _ in range(3)]}
    service.write('image-benchmark.json',evidence)
    assert service.validated_gate()['enabled'] is True
    evidence['results'][0]['seconds']=181
    service.write('image-benchmark.json',evidence)
    assert service.validated_gate()['enabled'] is False
    evidence['results'][0]['seconds']=30
    service.write('image-benchmark.json',evidence)
    model.write_bytes(b'changed')
    assert service.validated_gate()['enabled'] is False


def test_gate_bad_evidence_fails_closed(tmp_path,monkeypatch):
    monkeypatch.setattr(service,'DATA',tmp_path)
    service.write('config.json',{'images_enable_testers':True})
    service.write('image-checkpoint.json',{'path':'missing'})
    assert not service.validated_gate()['enabled']


def test_clean_environment_does_not_copy_provider_credentials(monkeypatch):
    monkeypatch.setenv('GEMINI_API_KEY','secret')
    monkeypatch.setenv('TELEGRAM_BOT_TOKEN','secret')
    env=service.clean_env()
    assert 'GEMINI_API_KEY' not in env and 'TELEGRAM_BOT_TOKEN' not in env
    assert env['GRADIO_ANALYTICS_ENABLED']=='False'
