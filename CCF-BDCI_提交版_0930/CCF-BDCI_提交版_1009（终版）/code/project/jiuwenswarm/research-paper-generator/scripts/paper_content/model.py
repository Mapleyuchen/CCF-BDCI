"""Small OpenAI-compatible HTTP client; no local inference framework is needed."""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def resolve_env(value):
    if isinstance(value, str):
        def replace(match):
            name, fallback = match.group(1), match.group(2)
            return os.environ.get(name) or fallback or ""
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}", replace, value)
    if isinstance(value, list):
        return [resolve_env(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_env(item) for key, item in value.items()}
    return value


def load_model_config(path: Path, env_file: Path | None = None) -> dict:
    import yaml
    if env_file is not None:
        if not env_file.is_file():
            raise ValueError(f"Environment file does not exist: {env_file}")
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
    if not path.is_file():
        raise ValueError(f"Model configuration does not exist: {path}")
    config = resolve_env(yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {})
    models = config.get("models") or {}
    entries = models.get("defaults")
    if not entries:
        entries = [models["default"]] if models.get("default") else [{
            "model_client_config": {"api_base": os.getenv("API_BASE", ""),
                                    "api_key": os.getenv("API_KEY", ""),
                                    "model_name": os.getenv("MODEL_NAME", ""),
                                    "client_provider": os.getenv("MODEL_PROVIDER", "OpenAI")}}]
    if not isinstance(entries, list) or any(not isinstance(e, dict) for e in entries):
        raise ValueError("models.defaults must be a list of model entries")
    entry = next((item for item in entries if item.get("is_default")), entries[0])
    client = dict(entry.get("model_client_config") or {})
    if client.get("client_provider", "OpenAI") != "OpenAI":
        raise ValueError("Content generation currently supports the OpenAI-compatible protocol")
    for field in ("api_base", "api_key", "model_name"):
        if not isinstance(client.get(field), str) or not client[field].strip():
            raise ValueError(f"Missing model setting or environment variable for {field}")
    url = urlparse(client["api_base"])
    if url.scheme not in ("https", "http") or not url.netloc or url.username or url.password or url.query:
        raise ValueError("api_base must be an HTTP(S) endpoint without embedded credentials or query parameters")
    client["timeout"] = float(client.get("timeout", 180))
    if not 0 < client["timeout"] <= 600:
        raise ValueError("timeout must be between 0 and 600 seconds")
    request = entry.get("model_config_obj") or {}
    return {"client": client, "request": {
        key: request[key] for key in ("temperature", "max_tokens", "top_p", "enable_thinking", "thinking_budget", "reasoning_effort") if key in request}}


class JsonModel:
    def __init__(self, config: dict):
        self.config = config
        self.calls: list[dict] = []

    def complete(self, messages: list[dict]) -> dict:
        client = self.config["client"]
        payload = {"model": client["model_name"], "messages": messages, "stream": False,
                   "temperature": 0, "max_tokens": 7000,
                   "response_format": {"type": "json_object"}, **self.config["request"]}
        url = client["api_base"].rstrip("/") + "/chat/completions"
        request = Request(url, data=json.dumps(payload).encode("utf-8"), headers={
            "Authorization": "Bearer " + client["api_key"], "Content-Type": "application/json"})
        started = time.monotonic()
        for attempt in range(3):
            try:
                with urlopen(request, timeout=client["timeout"]) as response:
                    data = json.load(response)
                break
            except HTTPError as error:
                code = error.code
                try:
                    service_code = json.load(error).get("error", {}).get("code")
                except (ValueError, AttributeError, TypeError):
                    service_code = None
                error.close()
                if code in (429, 500, 502, 503, 504) and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                # Persist only known codes, never provider messages that could echo credentials.
                hints = {
                    "AllocationQuota.FreeTierOnly": "Free quota exhausted with free-tier-only mode enabled; adjust Model Studio quota settings or select another available model",
                    "InvalidApiKey": "API key is invalid for this endpoint/region",
                    "ModelNotFound": "Model is unavailable or this account has no access",
                }
                hint = hints.get(service_code, "check endpoint, model access, quota and API key")
                self.calls.append({"model": client["model_name"], "http_status": code,
                                   "error_code": service_code if service_code in hints else "provider_error",
                                   "elapsed_seconds": round(time.monotonic() - started, 3),
                                   "http_attempts": attempt + 1})
                raise ValueError(f"Model API returned HTTP {code}; {hint}") from None
            except (URLError, TimeoutError, OSError):
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                self.calls.append({"model": client["model_name"], "error_code": "connection_failed",
                                   "elapsed_seconds": round(time.monotonic() - started, 3),
                                   "http_attempts": attempt + 1, "usage": None})
                raise ValueError("Model API connection failed or timed out") from None
        usage = data.get("usage") or {}
        self.calls.append({"model": data.get("model", client["model_name"]),
                           "elapsed_seconds": round(time.monotonic() - started, 3),
                           "http_attempts": attempt + 1,
                           "usage": {key: usage.get(key) for key in
                                     ("prompt_tokens", "completion_tokens", "total_tokens")}})
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError("Model response was truncated; increase max_tokens in the model configuration")
            raw = choice["message"]["content"]
            parsed = json.loads(raw)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            raise ValueError("Model did not return the required JSON object") from None
        if not isinstance(parsed, dict):
            raise ValueError("Model JSON must be an object")
        return parsed
