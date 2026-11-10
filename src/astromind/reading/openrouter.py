"""OpenRouter client for optional narrative readings.

The astronomical engine stays fully deterministic. This module only turns
already-computed facts into prose, and is always safe to skip.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemma-4-31b-it:free"
ENV_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "OPENROUTER_MODEL"

Transport = Callable[[urllib.request.Request, float], bytes]


class OpenRouterError(RuntimeError):
    """Raised when the optional narrative provider cannot answer."""


def _decode(raw: bytes | str) -> dict:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OpenRouterError(f"OpenRouter returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise OpenRouterError("OpenRouter returned an unexpected payload")
    if payload.get("error"):
        message = payload["error"]
        if isinstance(message, dict):
            message = message.get("message") or message
        raise OpenRouterError(str(message))
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise OpenRouterError("OpenRouter returned no choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
        raise OpenRouterError("OpenRouter returned an empty reading")
    return {"content": content.strip(), "model": payload.get("model")}


def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def chat(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    api_key: str | None = None,
    timeout: float = 90.0,
    transport: Transport | None = None,
    retries: int = 1,
) -> str:
    """Call OpenRouter and return the assistant message.

    A missing key raises immediately so callers can fall back locally.
    """
    key = (api_key or os.environ.get(ENV_KEY, "")).strip()
    if not key:
        raise OpenRouterError(f"{ENV_KEY} is not set")
    chosen_model = (model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL).strip()
    payload = {
        "model": chosen_model,
        "messages": messages,
        "temperature": 0.8,
        "top_p": 0.9,
        "max_tokens": 1800,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/muxd22-alt/ASTR",
            "X-Title": "ASTR",
        },
    )
    send = transport or _default_transport
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = send(request, timeout)
            return _decode(raw)["content"]
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = ""
            last_error = RuntimeError(f"HTTP {exc.code}: {detail or exc.reason}")
            if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                break
            time.sleep(2.0)
        except Exception as exc:  # network, timeout, malformed payload
            last_error = exc
            break
    raise OpenRouterError(f"OpenRouter request failed: {last_error}") from last_error
