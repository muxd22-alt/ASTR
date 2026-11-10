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
DEFAULT_FALLBACK_MODELS = (
    "google/gemma-4-26b-a4b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "xingchen-agi/xing4.0-29b-a4b:free",
)
ENV_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "OPENROUTER_MODEL"
ENV_FALLBACK_MODELS = "OPENROUTER_FALLBACK_MODELS"

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
    retries: int = 2,
    fallback_models: tuple[str, ...] | None = None,
) -> str:
    """Call OpenRouter and return the assistant message.

    A missing key raises immediately so callers can fall back locally. Free
    models can be rate-limited upstream, so a free fallback model is tried
    after the primary model is exhausted.
    """
    key = (api_key or os.environ.get(ENV_KEY, "")).strip()
    if not key:
        raise OpenRouterError(f"{ENV_KEY} is not set")
    chosen_model = (model or os.environ.get(ENV_MODEL) or DEFAULT_MODEL).strip()
    if fallback_models is None:
        raw_fallback = os.environ.get(ENV_FALLBACK_MODELS, "").strip()
        if raw_fallback:
            fallback_models = tuple(
                item.strip() for item in raw_fallback.split(",") if item.strip()
            )
        else:
            fallback_models = DEFAULT_FALLBACK_MODELS
    models = [chosen_model]
    for candidate in fallback_models:
        if candidate and candidate not in models:
            models.append(candidate)

    send = transport or _default_transport
    last_error: Exception | None = None
    for candidate_model in models:
        payload = {
            "model": candidate_model,
            "messages": messages,
            "temperature": 0.8,
            "top_p": 0.9,
            "max_tokens": 1800,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for attempt in range(retries + 1):
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
            try:
                raw = send(request, timeout)
                return _decode(raw)["content"]
            except urllib.error.HTTPError as exc:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")[:500]
                except Exception:
                    detail = ""
                last_error = RuntimeError(
                    f"{candidate_model} HTTP {exc.code}: {detail or exc.reason}"
                )
                if exc.code not in {429, 500, 502, 503, 504} or attempt >= retries:
                    break
                time.sleep(2.0 * (attempt + 1))
            except Exception as exc:  # network, timeout, malformed payload
                last_error = exc
                break
    raise OpenRouterError(f"OpenRouter request failed: {last_error}") from last_error
