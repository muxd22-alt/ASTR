"""Persistent, non-sensitive state used for delta reporting."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

STATE_VERSION = 1


def default_state() -> dict[str, Any]:
    return {"version": STATE_VERSION, "seen": {}, "last_run": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_state()
    if not isinstance(raw, dict):
        return default_state()
    raw.setdefault("version", STATE_VERSION)
    raw.setdefault("seen", {})
    raw.setdefault("last_run", {})
    return raw


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prune(state: dict[str, Any], today: date, keep_days: int = 90) -> dict[str, Any]:
    cutoff = today - timedelta(days=keep_days)
    seen = state.get("seen", {})
    kept = {}
    for key, value in seen.items():
        last_seen = value.get("last_seen") if isinstance(value, dict) else None
        if not isinstance(last_seen, str):
            continue
        try:
            if date.fromisoformat(last_seen) >= cutoff:
                kept[key] = value
        except ValueError:
            continue
    state["seen"] = kept
    return state
