"""Explicit FreeLLMAPI inference; Derek alone validates and executes tools."""

import json
import re
from urllib.parse import urlsplit

import httpx

from .errors import ConfigError, ProviderError, RequestCancelled
from .model_base import ResearchPlanningMixin, SYSTEM


class FreeLLMAPIGateway(ResearchPlanningMixin):
    def __init__(self, base_url, api_key, model, timeout_seconds=120, reasoning_effort="none", research_model=None):
        parsed = urlsplit(base_url)
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or (parsed.scheme == "http" and not loopback)
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") != "/v1"):
            raise ConfigError("FREELLMAPI_BASE_URL must be an HTTPS /v1 endpoint or loopback HTTP /v1 endpoint, without URL credentials.")
        if not api_key or any(char.isspace() for char in api_key):
            raise ConfigError("Set FREELLMAPI_API_KEY to your router's unified key.")
        if not model or len(model) > 160 or any(char.isspace() for char in model):
            raise ConfigError("Set FREELLMAPI_MODEL to an enabled tool-capable model or router profile.")
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.research_model = research_model or model
        if (len(self.research_model) > 160 or any(char.isspace() for char in self.research_model)):
            raise ConfigError("FREELLMAPI_RESEARCH_MODEL must be an enabled schema-capable model or router profile.")
        self.last_requested_model = model
        self.timeout_seconds = min(max(int(timeout_seconds), 15), 600)
        if reasoning_effort not in {"", "none", "minimal", "low", "medium", "high"}:
            raise ConfigError("FREELLMAPI_REASONING_EFFORT must be blank, none, minimal, low, medium or high.")
        self.reasoning_effort = reasoning_effort
        self.last_routing = {}
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def _request(self, messages, *, tools=None, schema=None, max_output_tokens=512, cancelled=None):
        cancelled = cancelled or getattr(self, "cancelled", None)
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_routing = {}
        self.last_requested_model = self.research_model if schema is not None else self.model
        body = {"model": self.last_requested_model, "messages": messages, "stream": False,
                "temperature": 0.2, "max_tokens": min(max(int(max_output_tokens), 128), 12000)}
        if self.reasoning_effort:
            body["reasoning_effort"] = self.reasoning_effort
        if tools:
            body["tools"] = tools
        if schema is not None:
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "derek_result", "strict": False, "schema": schema}}
        headers = {"Authorization": "Bearer " + self.api_key}
        try:
            if cancelled:
                from .cancellation import cancellable_request
                async def generate():
                    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                                 timeout=httpx.Timeout(self.timeout_seconds, connect=5)) as client:
                        return await client.post(self.base_url + "/chat/completions", headers=headers, json=body)
                response = cancellable_request(generate, cancelled)
            else:
                with httpx.Client(trust_env=False, follow_redirects=False,
                                  timeout=httpx.Timeout(self.timeout_seconds, connect=5)) as client:
                    response = client.post(self.base_url + "/chat/completions", headers=headers, json=body)
            if response.status_code in {401, 403}:
                raise ConfigError("FreeLLMAPI authentication failed. Check the unified router key.")
            if response.status_code == 429:
                raise ProviderError("FreeLLMAPI's enabled providers are rate limited. Retry later or review your router's quotas.")
            if response.status_code in {400, 404, 422}:
                raise ProviderError("FreeLLMAPI rejected the model, tools or JSON schema. Select a compatible enabled model in your router.")
            if not response.is_success:
                raise ProviderError("FreeLLMAPI is unavailable. Check the router and enabled provider keys.")
            if len(response.content) > 2_000_000:
                raise ProviderError("FreeLLMAPI response exceeded the allowed size.")
            data = response.json()
            # Retain bounded routing identifiers, never credentials/response
            # headers wholesale, so a saved answer identifies its actual model.
            for name, value in {"requested_model": self.last_requested_model, "served_model": data.get("model"),
                                "routed_via": response.headers.get("x-routed-via")}.items():
                if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:/@+-]{1,200}", value):
                    self.last_routing[name] = value
            choice = data["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ProviderError("FreeLLMAPI did not finish the answer. Request a shorter answer or review model limits.")
            message = choice["message"]
            if not isinstance(message, dict):
                raise ValueError
            usage = data.get("usage") or {}
            self.last_usage = {"input_tokens": max(0, int(usage.get("prompt_tokens", 0))),
                               "output_tokens": max(0, int(usage.get("completion_tokens", 0)))}
            # Deliberately ignore reasoning fields; only final content is shown.
            content = message.get("content") or ""
            if not isinstance(content, str):
                raise ValueError
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1]
            content = content.split("<think>", 1)[0].strip()
            message["content"] = content
            if not content and not message.get("tool_calls"):
                raise ProviderError("FreeLLMAPI returned no final answer.")
            return message
        except httpx.TimeoutException:
            raise ProviderError("FreeLLMAPI timed out. Check provider latency or choose a faster router profile.") from None
        except httpx.RequestError:
            raise ProviderError("Cannot reach FreeLLMAPI. Start the router and check its base URL.") from None
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise ProviderError("FreeLLMAPI returned an invalid response.") from None

    def chat(self, messages, tools, cancelled=None, max_output_tokens=512):
        if not messages or len(messages) > 100:
            raise ValueError("Provide between 1 and 100 chat messages.")
        history = [{"role": "system", "content": SYSTEM}]
        for item in messages:
            role, content = item.get("role"), item.get("content", "")
            if not isinstance(content, str) or len(content) > 40000:
                raise ValueError("Chat content must be text of at most 40000 characters.")
            if role == "tool":
                role, content = "user", "UNTRUSTED TOOL RESULT DATA:\n" + content
            if role == "model":
                role = "assistant"
            if role not in {"system", "user", "assistant"}:
                raise ValueError("Unsupported chat role.")
            history.append({"role": role, "content": content})
        declarations = [{"type": "function", "function": item.get("function", item)} for item in tools[:32]]
        result = self._request(history, tools=declarations, cancelled=cancelled, max_output_tokens=max_output_tokens)
        registered = {item["function"]["name"] for item in declarations}
        raw_calls = result.get("tool_calls") or []
        if not isinstance(raw_calls, list) or len(raw_calls) > 8:
            raise ProviderError("FreeLLMAPI returned invalid tool calls.")
        calls = []
        for item in raw_calls:
            try:
                function = item["function"]
                name, args = function["name"], function.get("arguments", {})
                if isinstance(args, str):
                    args = json.loads(args)
                if not isinstance(name, str) or name not in registered or not isinstance(args, dict):
                    raise ValueError
            except (ValueError, TypeError, KeyError):
                raise ProviderError("FreeLLMAPI returned an unregistered or invalid tool call.") from None
            calls.append({"name": name, "args": args})
        return {"text": result["content"][:20000], "tool_calls": calls, "usage": self.last_usage.copy(),
                "routing": self.last_routing.copy()}

    def _json(self, prompt, schema, max_output_tokens=4096):
        message = self._request([{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": prompt + "\nReturn only the requested JSON object."}],
                                schema=schema, max_output_tokens=max_output_tokens)
        try:
            result = json.loads(message["content"])
            if not isinstance(result, dict) or message.get("tool_calls"):
                raise ValueError
            return result
        except (ValueError, TypeError):
            raise ProviderError("FreeLLMAPI returned invalid structured output. Choose a JSON-schema-capable model.") from None

    def grounded_search(self, query, cancelled=None):
        from .web_search import public_search
        cancelled = cancelled or getattr(self, "cancelled", None)
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        result = public_search(query)
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        return result
