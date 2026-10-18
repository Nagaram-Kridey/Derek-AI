import asyncio
import json
from unittest.mock import patch

import httpx
import pytest
from assistant.integrations.cancellation import cancellable_request
from assistant.integrations.errors import ConfigError, ProviderError, RequestCancelled
from assistant.integrations.ollama import OllamaGateway
from assistant.integrations.project_ideas import select_shortlist


@pytest.mark.parametrize(
    "origin,model",
    [
        ("https://example.com", "qwen3:4b"),
        ("http://192.168.1.1:11434", "qwen3:4b"),
        ("http://localhost/path", "qwen3:4b"),
        ("http://localhost:11434", "some-model:cloud"),
    ],
)
def test_local_provider_refuses_remote_origins_or_cloud_models(origin, model):
    with pytest.raises(ConfigError):
        OllamaGateway(origin, model)


def test_local_provider_checks_metadata_filters_reasoning_and_counts_usage():
    requests = []

    def respond(request):
        requests.append(request)
        if request.url.path == "/api/show":
            return httpx.Response(200, json={"capabilities": ["tools"]})
        return httpx.Response(
            200,
            json={
                "done": True,
                "message": {"content": "<think>private reasoning</think>Final answer"},
                "prompt_eval_count": 10,
                "eval_count": 4,
            },
        )

    real_client = httpx.Client
    with patch(
        "assistant.integrations.ollama.httpx.Client",
        side_effect=lambda **kwargs: real_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    ):
        result = OllamaGateway("http://127.0.0.1:11434", "qwen3:4b").chat(
            [{"role": "user", "content": "Hello"}], []
        )
    assert result["text"] == "Final answer" and result["usage"]["output_tokens"] == 4
    body = json.loads(requests[-1].content)
    assert body["think"] is False and body["messages"][-1]["content"].endswith(
        "/no_think"
    )


def test_local_provider_never_sends_prompt_to_remote_delegating_model():
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json={"remote_host": "https://example.com"})

    real_client = httpx.Client
    with patch(
        "assistant.integrations.ollama.httpx.Client",
        side_effect=lambda **kwargs: real_client(
            transport=httpx.MockTransport(respond), **kwargs
        ),
    ):
        with pytest.raises(ConfigError):
            OllamaGateway("http://127.0.0.1:11434", "qwen3:4b").chat(
                [{"role": "user", "content": "Private request"}], []
            )
    assert len(requests) == 1 and requests[0].url.path == "/api/show"


@pytest.mark.parametrize(
    "message",
    [
        {
            "content": "",
            "tool_calls": [{"function": {"name": "unknown", "arguments": {}}}],
        },
        {
            "content": "",
            "tool_calls": [
                {"function": {"name": "list_tasks", "arguments": "invalid-json"}}
            ],
        },
    ],
)
def test_local_provider_rejects_unregistered_or_malformed_tool_calls(message):
    gateway = OllamaGateway("http://127.0.0.1:11434", "qwen3:4b")
    with patch.object(gateway, "_request", return_value=message):
        with pytest.raises(ProviderError):
            gateway.chat(
                [{"role": "user", "content": "Help"}],
                [{"name": "list_tasks", "parameters": {"type": "object"}}],
            )


def test_inference_cancellation_prevents_dispatch_and_stops_active_transport():
    called = []

    async def never_dispatch():
        called.append(True)

    with pytest.raises(RequestCancelled):
        cancellable_request(never_dispatch, lambda: True)
    assert called == []
    ended = []

    async def pending():
        try:
            await asyncio.sleep(30)
        finally:
            ended.append(True)

    probes = iter([False, True])
    with pytest.raises(RequestCancelled):
        cancellable_request(pending, lambda: next(probes))
    assert ended == [True]


def test_shortlist_preserves_highest_score_and_rejects_invalid_tie_choice():
    ideas = [
        {
            "number": index,
            "title": str(index),
            "target_users": "users",
            "problem": "hypothesis",
            "mvp": "prototype",
            "score": score,
        }
        for index, score in enumerate([48, 40, 40, 30, 20], 1)
    ]

    class Gateway:
        def choose_shortlist(self, ideas):
            return {"numbers": [3, 4], "criteria": ["MVP scope"]}

    selected, reason = select_shortlist(ideas, Gateway())
    assert [item["number"] for item in selected] == [1, 2]
    assert "unavailable" in reason
