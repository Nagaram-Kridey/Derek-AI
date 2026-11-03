from unittest.mock import patch

import httpx
import pytest
from django.test import override_settings
from assistant.integrations.custom_llm import CustomLLMGateway
from assistant.integrations.errors import ConfigError, ProviderError
from assistant.integrations.models import create_gateway


def gateway(**kwargs):
    return CustomLLMGateway("http://127.0.0.1:9000/v1", "", "derek-model", **kwargs)


def response(content="Hello", **extra):
    return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {"content": content}}], **extra})


def test_chat_preserves_context_without_router_fields_or_unsupported_tools():
    with patch("assistant.integrations.custom_llm.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = response()
        answer = gateway().chat([{"role":"user","content":"Earlier"}, {"role":"model","content":"Reply"}, {"role":"user","content":"Next"}], [{"name":"search","parameters":{}}])
        request = client.return_value.__enter__.return_value.post.call_args
        assert request.args[0] == "http://127.0.0.1:9000/v1/chat/completions"
        body = request.kwargs["json"]
        assert body["model"] == "derek-model"
        assert body["messages"][-2:] == [{"role":"assistant","content":"Reply"},{"role":"user","content":"Next"}]
        assert not ({"tools","response_format","reasoning_effort"} & body.keys())
        assert request.kwargs["headers"] == {}
        assert answer["text"] == "Hello"


def test_schema_requires_explicit_capability_before_network():
    with patch("assistant.integrations.custom_llm.httpx.Client") as client:
        with pytest.raises(ConfigError, match="structured output is disabled"):
            gateway()._json("research", {})
        client.assert_not_called()


def test_explicit_schema_and_tools():
    with patch("assistant.integrations.custom_llm.httpx.Client") as client:
        post = client.return_value.__enter__.return_value.post
        post.return_value = response('{"ok": true}')
        assert gateway(supports_json_schema=True)._json("x", {"type":"object"}) == {"ok":True}
        assert post.call_args.kwargs["json"]["response_format"]["type"] == "json_schema"
        post.return_value = response()
        gateway(supports_tools=True).chat([{"role":"user","content":"x"}], [{"name":"search","parameters":{}}])
        assert post.call_args.kwargs["json"]["tools"][0]["function"]["name"] == "search"


@pytest.mark.parametrize("url", ["http://example.org/v1", "https://user:secret@example.org/v1", "https://example.org/v1?key=secret", "https://example.org/other"])
def test_invalid_endpoints(url):
    with pytest.raises(ConfigError):
        CustomLLMGateway(url,"key","model")


def test_remote_requires_credential():
    with pytest.raises(ConfigError):
        CustomLLMGateway("https://example.org/v1","","model")


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("secret"), httpx.ConnectError("secret")])
def test_transport_errors_are_sanitized(failure):
    with patch("assistant.integrations.custom_llm.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.side_effect = failure
        with pytest.raises(ProviderError) as exc:
            gateway().chat([{"role":"user","content":"x"}], [])
        assert "secret" not in str(exc.value)
        assert "Custom LLM" in str(exc.value)


def test_invalid_output_is_sanitized():
    with patch("assistant.integrations.custom_llm.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.return_value = httpx.Response(200,json={"secret":"private"})
        with pytest.raises(ProviderError, match="invalid response"):
            gateway().chat([{"role":"user","content":"x"}], [])


@override_settings(MODEL_PROVIDER="custom",CUSTOM_LLM_BASE_URL="http://localhost:9000/v1",CUSTOM_LLM_MODEL="own-model",CUSTOM_LLM_API_KEY="")
def test_factory_selects_custom():
    assert isinstance(create_gateway("configured"), CustomLLMGateway)
