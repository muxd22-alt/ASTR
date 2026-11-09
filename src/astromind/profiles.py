"""Load profiles from GitHub Secrets (base64 JSON) or a local private file."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from astromind.models import Bundle, ProfileError

ENV_VAR = "ASTROMIND_PROFILES"
DEFAULT_LOCAL_PATHS = (
    Path("profiles.local") / "profiles.json",
    Path("profiles") / "profiles.json",
)


def _decode_base64(raw: str) -> str:
    cleaned = "".join(raw.split())
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(cleaned, validate=False).decode("utf-8")
    except Exception as exc:
        raise ProfileError(
            "ASTROMIND_PROFILES is not valid base64-encoded UTF-8 JSON. "
            "Run `python -m astromind encode --file profiles.local/profiles.json`."
        ) from exc


def parse_payload(raw: Any) -> Bundle:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ProfileError("profile payload is empty")
        if text[0] in "[{":
            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProfileError(f"profile payload is invalid JSON: {exc}") from exc
        else:
            raw = json.loads(_decode_base64(text))
    return Bundle.from_dict(raw)


def load_bundle(file: str | Path | None = None) -> Bundle:
    if file:
        path = Path(file)
        if not path.exists():
            raise ProfileError(f"profile file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ProfileError(f"invalid JSON in {path}: {exc}") from exc
        return Bundle.from_dict(payload)

    secret = os.environ.get(ENV_VAR, "").strip()
    if secret:
        try:
            payload = json.loads(_decode_base64(secret))
        except ProfileError:
            raise
        except json.JSONDecodeError as exc:
            raise ProfileError(
                f"{ENV_VAR} decoded but is not valid JSON: {exc}"
            ) from exc
        return Bundle.from_dict(payload)

    for path in DEFAULT_LOCAL_PATHS:
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8-sig"))
            except json.JSONDecodeError as exc:
                raise ProfileError(f"invalid JSON in {path}: {exc}") from exc
            return Bundle.from_dict(payload)

    raise ProfileError(
        "No profiles found. Set the GitHub secret "
        f"`{ENV_VAR}` (base64 JSON) or create `profiles.local/profiles.json`. "
        "See `profiles/self.example.json` for the schema."
    )


def encode_payload(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def encode_file(path: str | Path) -> str:
    source = Path(path)
    if not source.exists():
        raise ProfileError(f"file not found: {source}")
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    return encode_payload(payload)
