"""Explicit custom OpenAI-compatible inference; no provider fallback."""

import json
from urllib.parse import urlsplit

import httpx

from .errors import ConfigError, ProviderError, RequestCancelled
from .model_base import ResearchPlanningMixin, SYSTEM


class CustomLLMGateway(ResearchPlanningMixin):
    def __init__(self, base_url, api_key, model, timeout_seconds=120, supports_tools=False, supports_json_schema=False):
        parsed = urlsplit(base_url)
        loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or (parsed.scheme == "http" and not loopback)
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path.rstrip("/") != "/v1"):
            raise ConfigError("CUSTOM_LLM_BASE_URL must be an HTTPS /v1 endpoint or loopback HTTP /v1 endpoint, without URL credentials.")
        if (not api_key and not loopback) or any(char.isspace() for char in api_key):
            raise ConfigError("CUSTOM_LLM_API_KEY is required for remote endpoints and must not contain whitespace.")
        if not model or len(model) > 160 or any(char.isspace() for char in model):
            raise ConfigError("Set CUSTOM_LLM_MODEL to the served model identifier.")
        self.base_url, self.api_key, self.model = base_url.rstrip("/"), api_key, model
        self.last_requested_model = model
        self.supports_tools = bool(supports_tools)
        self.supports_json_schema = bool(supports_json_schema)
        self.timeout_seconds = min(max(int(timeout_seconds), 15), 600)
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def _request(self, messages, *, tools=None, schema=None, max_output_tokens=512, cancelled=None):
        cancelled = cancelled or getattr(self, "cancelled", None)
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        self.last_requested_model = self.model
        body = {"model": self.last_requested_model, "messages": messages, "stream": False,
                "temperature": 0.2, "max_tokens": min(max(int(max_output_tokens), 128), 12000)}
        if tools and self.supports_tools:
            body["tools"] = tools
        if schema is not None:
            if not self.supports_json_schema:
                raise ConfigError("Custom LLM structured output is disabled; research requires CUSTOM_LLM_SUPPORTS_JSON_SCHEMA.")
            body["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "derek_result", "strict": False, "schema": schema}}
        headers = {"Authorization": "Bearer " + self.api_key} if self.api_key else {}
        timeout = self.timeout_seconds
        try:
            if cancelled:
                from .cancellation import cancellable_request
                async def generate():
                    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                                 timeout=httpx.Timeout(timeout, connect=5)) as client:
                        return await client.post(self.base_url + "/chat/completions", headers=headers, json=body)
                response = cancellable_request(generate, cancelled)
            else:
                with httpx.Client(trust_env=False, follow_redirects=False,
                                  timeout=httpx.Timeout(timeout, connect=5)) as client:
                    response = client.post(self.base_url + "/chat/completions", headers=headers, json=body)
            if response.status_code in {401, 403}:
                raise ConfigError("Custom LLM authentication failed. Check the server API credential.")
            if response.status_code == 429:
                raise ProviderError("Custom LLM is rate limited. Retry later.")
            if response.status_code in {400, 404, 422}:
                raise ProviderError("Custom LLM rejected the model, tools or JSON schema. Check the configured model capabilities.")
            if not response.is_success:
                raise ProviderError("Custom LLM is unavailable. Check the configured inference service.")
            if len(response.content) > 2_000_000:
                raise ProviderError("Custom LLM response exceeded the allowed size.")
            data = response.json()
            choice = data["choices"][0]
            if choice.get("finish_reason") not in {"stop", "tool_calls"}:
                raise ProviderError("Custom LLM did not finish the answer. Request a shorter answer or review model limits.")
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
                raise ProviderError("Custom LLM returned no final answer.")
            return message
        except httpx.TimeoutException:
            raise ProviderError("Custom LLM timed out. The inference service did not respond within its timeout.") from None
        except httpx.RequestError:
            raise ProviderError("Cannot reach Custom LLM. Check the configured inference endpoint.") from None
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            raise ProviderError("Custom LLM returned an invalid response.") from None

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
        declarations = [{"type": "function", "function": item.get("function", item)} for item in (tools[:32] if self.supports_tools else [])]
        result = self._request(history, tools=declarations, cancelled=cancelled, max_output_tokens=max_output_tokens)
        registered = {item["function"]["name"] for item in declarations}
        raw_calls = result.get("tool_calls") or []
        if not isinstance(raw_calls, list) or len(raw_calls) > 8:
            raise ProviderError("Custom LLM returned invalid tool calls.")
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
                raise ProviderError("Custom LLM returned an unregistered or invalid tool call.") from None
            calls.append({"name": name, "args": args})
        return {"text": result["content"][:20000], "tool_calls": calls, "usage": self.last_usage.copy()}

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
            raise ProviderError("Custom LLM returned invalid structured output. Choose a JSON-schema-capable model.") from None

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
