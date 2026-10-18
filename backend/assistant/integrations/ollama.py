"""Local Ollama chat/tools and structured research; no cloud-model fallback."""

import json
import os
from urllib.parse import urlsplit

import httpx

from .errors import ConfigError, ProviderError, RequestCancelled
from .model_base import ResearchPlanningMixin, SYSTEM


class OllamaGateway(ResearchPlanningMixin):
    def __init__(self, base_url, model, timeout_seconds=900, num_ctx=8192):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ConfigError("OLLAMA_BASE_URL must be a local Ollama HTTP origin without credentials or a path.")
        if not model or len(model) > 200 or model.endswith((":cloud", "-cloud")):
            raise ConfigError("Set OLLAMA_MODEL to an installed local model with tool calling and structured output support.")
        self.base_url, self.model = base_url.rstrip("/"), model
        self.timeout_seconds = min(max(int(timeout_seconds), 30), 1800)
        self.num_ctx = min(max(int(num_ctx), 4096), 32768)
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def _request(self, messages, *, tools=None, schema=None, max_output_tokens=2048, cancelled=None):
        cancelled = cancelled or getattr(self, "cancelled", None)
        messages = [dict(message) for message in messages]
        if self.model.split("/")[-1].split(":")[0] == "qwen3":
            # Qwen's prompt switch complements the runtime's think=False flag.
            for message in reversed(messages):
                if message["role"] == "user":
                    message["content"] += "\n/no_think"
                    break
        body = {"model": self.model, "messages": messages, "stream": False, "think": False,
                "keep_alive": "5m", "options": {"temperature": 0 if schema else 0.2,
                "num_ctx": self.num_ctx, "num_predict": min(max_output_tokens, 4096),
                "num_thread": max(1, min(8, (os.cpu_count() or 4) - 2))}}
        if tools:
            body["tools"] = tools
        if schema is not None:
            body["format"] = schema
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        def validate_model(info):
            if info.status_code == 404:
                raise ConfigError("The selected Ollama model is not installed. Pull OLLAMA_MODEL on the service PC first.")
            if not info.is_success:
                raise ProviderError("Cannot inspect the selected Ollama model. Check its local server log.")
            metadata = info.json()
            if not isinstance(metadata, dict):
                raise ValueError
            if metadata.get("remote_model") or metadata.get("remote_host"):
                raise ConfigError("This Ollama model delegates inference to a remote host. Select a downloaded local model.")
            capabilities = metadata.get("capabilities")
            if tools and isinstance(capabilities, list) and "tools" not in capabilities:
                raise ConfigError("The selected local model does not support tool calling. Choose a tool-capable Ollama model.")
        try:
            if cancelled:
                from .cancellation import cancellable_request
                async def generate():
                    async with httpx.AsyncClient(trust_env=False, follow_redirects=False,
                                                 timeout=httpx.Timeout(self.timeout_seconds, connect=5)) as client:
                        info = await client.post(self.base_url + "/api/show", json={"model": self.model}, timeout=30)
                        validate_model(info)
                        return await client.post(self.base_url + "/api/chat", json=body)
                response = cancellable_request(generate, cancelled)
            else:
                with httpx.Client(trust_env=False, follow_redirects=False,
                                  timeout=httpx.Timeout(self.timeout_seconds, connect=5)) as client:
                    info = client.post(self.base_url + "/api/show", json={"model": self.model}, timeout=30)
                    validate_model(info)
                    response = client.post(self.base_url + "/api/chat", json=body)
            if response.status_code == 404:
                raise ConfigError("The selected Ollama model is not installed. Pull OLLAMA_MODEL on the service PC first.")
            if response.status_code == 400:
                raise ProviderError("Ollama rejected the request. Select a model supporting tools and JSON schemas, such as qwen3:4b.")
            if not response.is_success:
                raise ProviderError("Ollama could not run the model. Check available RAM and its local server log.")
            if len(response.content) > 2_000_000:
                raise ProviderError("Ollama response exceeded the allowed size.")
            result = response.json()
            if not isinstance(result, dict) or not isinstance(result.get("message"), dict):
                raise ValueError
            self.last_usage = {"input_tokens": int(result.get("prompt_eval_count", 0)),
                               "output_tokens": int(result.get("eval_count", 0))}
            if result.get("done") is not True or result.get("done_reason") == "length":
                raise ProviderError("The local model did not finish its response. Request a shorter report or review context/output limits.")
            message = result["message"]
            content = message.get("content", "")
            if not isinstance(content, str):
                raise ValueError
            # Some runtimes place reasoning in content, including a closing tag
            # without an opening tag. Never return that prefix as the reply.
            if "</think>" in content:
                content = content.rsplit("</think>", 1)[1]
            if "<think>" in content:
                content = content.split("<think>", 1)[0]
            message["content"] = content.strip()
            if not message["content"] and not message.get("tool_calls"):
                raise ProviderError("The local model returned no final answer. Try a shorter request or another tool-capable model.")
            return message
        except httpx.TimeoutException:
            raise ProviderError("The local model timed out. CPU generation can be slow; try a smaller model or free some RAM.") from None
        except httpx.RequestError:
            raise ProviderError("Cannot reach local Ollama. Start Ollama on the service PC and check OLLAMA_BASE_URL.") from None
        except (ValueError, TypeError, KeyError):
            raise ProviderError("Ollama returned an invalid response.") from None

    def chat(self, messages, tools, cancelled=None):
        if not messages or len(messages) > 100:
            raise ValueError("Provide between 1 and 100 chat messages.")
        history = [{"role": "system", "content": SYSTEM + "\nReturn only the final user-facing answer or a tool call. Keep replies concise."}]
        for message in messages:
            role, content = message.get("role"), message.get("content", "")
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
        result = self._request(history, tools=declarations, max_output_tokens=512, cancelled=cancelled)
        registered = {item["function"]["name"] for item in declarations}
        calls = []
        for item in (result.get("tool_calls") or [])[:8]:
            function = item.get("function", {})
            name, args = function.get("name"), function.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    raise ProviderError("The local model returned invalid tool arguments.") from None
            if not isinstance(name, str) or name not in registered or not isinstance(args, dict):
                raise ProviderError("The local model returned an unregistered or invalid tool call.")
            calls.append({"name": name, "args": args})
        return {"text": str(result.get("content", ""))[:20000], "tool_calls": calls, "usage": self.last_usage.copy()}

    def _json(self, prompt, schema, max_output_tokens=4096):
        result = self._request([{"role": "system", "content": SYSTEM}, {"role": "user", "content":
            prompt + "\nReturn only the requested JSON object. Keep text fields concise: one or two sentences per field and three brief items per implementation/features array."}],
            schema=schema, max_output_tokens=max_output_tokens)
        try:
            parsed = json.loads(result.get("content", ""))
            if not isinstance(parsed, dict):
                raise ValueError
            return parsed
        except (ValueError, TypeError):
            raise ProviderError("The local model returned invalid structured output. Try a model with stronger JSON schema support.") from None

    def grounded_search(self, query, cancelled=None):
        cancelled = cancelled or getattr(self, "cancelled", None)
        # Compatibility interface: search snippets are NOT Google-grounded prose.
        from .web_search import public_search
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        result = public_search(query)
        if cancelled and cancelled():
            raise RequestCancelled("Command cancelled.")
        return result

    def plan_research(self, topic):
        # Bound CPU work: one focused search, up to six public result pages.
        return super().plan_research(topic)[:1]

    def verify_evidence(self, claim, evidence):
        from .research import registrable_domain
        domains = {registrable_domain(item["url"]) for item in evidence}
        domains.discard("")
        if len(domains) < 2:
            # The report cannot mark this claim corroborated. Returning no
            # semantic judgments retains deterministic exact-quote checking and
            # the unverified label without a costly CPU generation request.
            return []
        return super().verify_evidence(claim, evidence)
