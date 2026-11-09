from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from astromind.models import Bundle, ProfileError
from astromind.profiles import encode_payload, load_bundle, parse_payload

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "profiles" / "profiles.example.json"


def test_load_example_bundle() -> None:
    bundle = load_bundle(EXAMPLES)
    assert bundle.self_profile.id == "self"
    assert bundle.partner is not None
    assert len(bundle.children) == 2
    assert bundle.partner.pronoun == "f"
    assert bundle.self_profile.birth.tz == "Asia/Riyadh"


def test_encode_and_parse_roundtrip() -> None:
    payload = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    encoded = encode_payload(payload)
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert json.loads(decoded)["profiles"][0]["id"] == "self"
    bundle = parse_payload(encoded)
    assert bundle.self_profile.name


def test_missing_self_is_rejected() -> None:
    payload = {
        "profiles": [
            {
                "id": "partner",
                "role": "partner",
                "name": "X",
                "birth": {
                    "date": "1990-01-01",
                    "time": "12:00",
                    "tz": "Asia/Riyadh",
                    "lat": 24.7,
                    "lon": 46.6,
                },
            }
        ]
    }
    with pytest.raises(ProfileError):
        Bundle.from_dict(payload)


def test_duplicate_ids_are_rejected() -> None:
    payload = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    payload["profiles"][1]["id"] = "self"
    with pytest.raises(ProfileError):
        Bundle.from_dict(payload)


def test_unknown_time_is_marked() -> None:
    payload = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    payload["profiles"][0]["birth"]["time_known"] = False
    bundle = Bundle.from_dict(payload)
    assert bundle.self_profile.birth.time_known is False
    assert bundle.self_profile.birth.local_dt().hour == 12


def test_bad_timezone_is_rejected() -> None:
    payload = json.loads(EXAMPLES.read_text(encoding="utf-8"))
    payload["profiles"][0]["birth"]["tz"] = "Mars/Olympus"
    with pytest.raises(ProfileError):
        Bundle.from_dict(payload)
