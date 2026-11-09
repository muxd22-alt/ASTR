"""Core data models: profiles, birth data, and the profile bundle."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time as dt_time, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from astromind.i18n import SIGNS_AR, SIGNS_EN

VALID_ROLES = {"self", "partner", "child"}
VALID_FOCUS = {
    "communication",
    "emotional_security",
    "conflict",
    "parenting",
    "talent",
    "planning",
}

BODY_ALIASES = {
    "sun": "sun",
    "moon": "moon",
    "mercury": "mercury",
    "venus": "venus",
    "mars": "mars",
    "jupiter": "jupiter",
    "saturn": "saturn",
    "uranus": "uranus",
    "neptune": "neptune",
    "pluto": "pluto",
    "node": "node",
    "north_node": "node",
    "northnode": "node",
    "chiron": "chiron",
    "asc": "asc",
    "ascendant": "asc",
    "rising": "asc",
    "mc": "mc",
    "midheaven": "mc",
}

SIGN_LOOKUP: dict[str, int] = {
    name.lower(): index for index, name in enumerate(SIGNS_EN)
}
SIGN_LOOKUP.update({name: index for index, name in enumerate(SIGNS_AR)})



class ProfileError(ValueError):
    """Raised when profile data is missing or invalid."""


def _parse_date(value: Any, field_name: str) -> date:
    if not isinstance(value, str):
        raise ProfileError(f"{field_name} must be a YYYY-MM-DD string")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ProfileError(f"{field_name} is not a valid date: {value!r}") from exc


def _parse_time(value: Any, field_name: str) -> dt_time:
    if not isinstance(value, str):
        raise ProfileError(f"{field_name} must be an HH:MM string")
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).time()
        except ValueError:
            continue
    raise ProfileError(f"{field_name} is not a valid time: {value!r}")


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProfileError(f"{field_name} must be a number")
    return float(value)


@dataclass(frozen=True)
class BirthData:
    date: str
    time: str
    tz: str
    lat: float
    lon: float
    time_known: bool = True

    @classmethod
    def from_dict(cls, raw: dict[str, Any], context: str = "birth") -> "BirthData":
        if not isinstance(raw, dict):
            raise ProfileError(f"{context} must be an object")
        day = _parse_date(raw.get("date"), f"{context}.date")
        time_known = raw.get("time_known", True)
        if isinstance(time_known, str):
            time_known = time_known.strip().lower() not in {"false", "0", "no", "unknown", ""}
        time_known = bool(time_known) and bool(str(raw.get("time", "")).strip())
        time_value = str(raw.get("time") or "12:00").strip()
        _parse_time(time_value, f"{context}.time")

        tz_name = str(raw.get("tz") or "").strip()
        if not tz_name:
            raise ProfileError(f"{context}.tz is required (IANA name, e.g. Asia/Riyadh)")
        try:
            ZoneInfo(tz_name)
        except ZoneInfoNotFoundError as exc:
            raise ProfileError(f"{context}.tz is unknown: {tz_name!r}") from exc

        lat = _number(raw.get("lat"), f"{context}.lat")
        lon = _number(raw.get("lon"), f"{context}.lon")
        if not -90 <= lat <= 90:
            raise ProfileError(f"{context}.lat must be between -90 and 90")
        if not -180 <= lon <= 180:
            raise ProfileError(f"{context}.lon must be between -180 and 180")

        return cls(
            date=day.isoformat(),
            time=time_value,
            tz=tz_name,
            lat=lat,
            lon=lon,
            time_known=time_known,
        )

    def local_dt(self) -> datetime:
        day = date.fromisoformat(self.date)
        clock = _parse_time(self.time if self.time_known else "12:00", "birth.time")
        return datetime.combine(day, clock, tzinfo=ZoneInfo(self.tz))

    def utc_dt(self) -> datetime:
        return self.local_dt().astimezone(timezone.utc)

    def fingerprint(self) -> str:
        payload = json.dumps(
            {
                "date": self.date,
                "time": self.time if self.time_known else "12:00",
                "tz": self.tz,
                "lat": round(self.lat, 4),
                "lon": round(self.lon, 4),
                "time_known": self.time_known,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _sign_value(value: Any, context: str) -> int:
    raw_value = value
    if isinstance(value, dict):
        value = value.get("sign")
    if isinstance(value, bool):
        raise ProfileError(f"{context} must be a zodiac sign name")
    if isinstance(value, int):
        if 0 <= value <= 11:
            return value
        raise ProfileError(f"{context} sign index must be 0..11, got {value}")
    if isinstance(value, str):
        text = value.strip()
        if text in SIGN_LOOKUP:
            return SIGN_LOOKUP[text]
        lowered = text.lower()
        if lowered in SIGN_LOOKUP:
            return SIGN_LOOKUP[lowered]
        normalized = (
            text.replace("أ", "ا")
            .replace("إ", "ا")
            .replace("آ", "ا")
            .replace("ى", "ي")
            .replace("ة", "ه")
        )
        for name, index in SIGN_LOOKUP.items():
            if (
                name.replace("أ", "ا")
                .replace("إ", "ا")
                .replace("آ", "ا")
                .replace("ى", "ي")
                .replace("ة", "ه")
                == normalized
            ):
                return index
    raise ProfileError(f"{context} is not a valid zodiac sign: {raw_value!r}")


def _body_key(key: Any) -> str | None:
    text = str(key).strip().lower().replace(" ", "_").replace("-", "_")
    return BODY_ALIASES.get(text)


def _extract_signs(raw: dict[str, Any]) -> dict[str, int]:
    sources: dict[str, Any] = {}
    nested = raw.get("signs")
    if isinstance(nested, dict):
        sources.update(nested)
    for key, value in raw.items():
        if _body_key(key) is not None:
            sources[key] = value

    signs: dict[str, int] = {}
    for key, value in sources.items():
        body = _body_key(key)
        if body is None:
            continue
        context = f"profile {raw.get('name') or raw.get('id') or '?'}.{body}"
        signs[body] = _sign_value(value, context)
    return signs


def _extract_houses(raw: dict[str, Any]) -> dict[str, int]:
    sources: dict[str, Any] = {}
    nested = raw.get("signs")
    if isinstance(nested, dict):
        sources.update(nested)
    houses_raw = raw.get("houses")
    if isinstance(houses_raw, dict):
        for key, value in houses_raw.items():
            body = _body_key(key)
            if body is None:
                continue
            candidate = value.get("house") if isinstance(value, dict) else value
            sources[body] = {"house": candidate}
    for key, value in raw.items():
        body = _body_key(key)
        if body is not None and isinstance(value, dict) and "house" in value:
            sources[body] = value

    houses: dict[str, int] = {}
    for key, value in sources.items():
        body = _body_key(key) or key
        candidate = value.get("house") if isinstance(value, dict) else value
        if candidate is None:
            continue
        try:
            number = int(candidate)
        except (TypeError, ValueError) as exc:
            raise ProfileError(
                f"profile {raw.get('name') or raw.get('id') or '?'}.{body}.house "
                "must be an integer 1..12"
            ) from exc
        if not 1 <= number <= 12:
            raise ProfileError(
                f"profile {raw.get('name') or raw.get('id') or '?'}.{body}.house "
                f"must be between 1 and 12, got {number}"
            )
        houses[body] = number
    return houses


@dataclass(frozen=True)
class Profile:
    id: str
    role: str
    name: str
    birth: BirthData | None
    focus: tuple[str, ...] = ()
    notes: str = ""
    gender: str = ""
    signs: dict[str, int] = field(default_factory=dict)
    houses: dict[str, int] = field(default_factory=dict)
    tz_name: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], index: int = 0) -> "Profile":
        if not isinstance(raw, dict):
            raise ProfileError(f"profiles[{index}] must be an object")
        role = str(raw.get("role") or "").strip().lower()
        if role not in VALID_ROLES:
            raise ProfileError(
                f"profiles[{index}]: role must be one of {sorted(VALID_ROLES)}"
            )

        pid = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not pid:
            pid = role if role in {"self", "partner"} else f"{role}_{index + 1}"
        if not name:
            name = pid

        birth_raw = raw.get("birth")
        birth = None
        if isinstance(birth_raw, dict) and birth_raw.get("date"):
            birth = BirthData.from_dict(birth_raw, context=f"profile {pid}.birth")

        signs = _extract_signs(raw)
        houses = _extract_houses(raw)
        if birth is None and not signs:
            raise ProfileError(
                f"profile {pid!r}: either complete birth data or sign placements "
                "(sun, moon, ascendant, ...) are required"
            )
        if birth is None and "sun" not in signs:
            raise ProfileError(
                f"profile {pid!r}: sign-only profiles need at least a 'sun' sign"
            )

        raw_focus = raw.get("focus") or []
        if isinstance(raw_focus, str):
            raw_focus = [raw_focus]
        if not isinstance(raw_focus, Iterable):
            raise ProfileError(f"profile {pid!r}: focus must be a list")
        focus = tuple(
            str(item).strip() for item in raw_focus if str(item).strip() in VALID_FOCUS
        )

        gender = str(raw.get("gender") or "").strip().lower()
        if gender in {"m", "male", "ذكر"}:
            gender = "male"
        elif gender in {"f", "female", "أنثى"}:
            gender = "female"
        else:
            gender = ""

        tz_name = str(raw.get("tz") or "").strip()
        if tz_name:
            try:
                ZoneInfo(tz_name)
            except ZoneInfoNotFoundError as exc:
                raise ProfileError(
                    f"profile {pid!r}: tz is unknown: {tz_name!r}"
                ) from exc

        return cls(
            id=pid,
            role=role,
            name=name,
            birth=birth,
            focus=focus,
            notes=str(raw.get("notes") or "").strip(),
            gender=gender,
            signs=signs,
            houses=houses,
            tz_name=tz_name,
        )

    @property
    def pronoun(self) -> str:
        return "f" if self.gender == "female" else "m"

    @property
    def tz(self) -> str:
        if self.birth is not None:
            return self.birth.tz
        return self.tz_name or "Asia/Riyadh"

    @property
    def sign_only(self) -> bool:
        return self.birth is None

    def age_on(self, on: date) -> int | None:
        if self.birth is None:
            return None
        born = date.fromisoformat(self.birth.date)
        return on.year - born.year - ((on.month, on.day) < (born.month, born.day))

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "role": self.role,
            "name": self.name,
            "focus": list(self.focus),
            "notes": self.notes,
            "gender": self.gender,
            "signs": {body: SIGNS_EN[sign] for body, sign in self.signs.items()},
            "houses": dict(self.houses),
            "tz": self.tz,
        }
        if self.birth is not None:
            payload["birth"] = {
                "date": self.birth.date,
                "time": self.birth.time,
                "tz": self.birth.tz,
                "lat": self.birth.lat,
                "lon": self.birth.lon,
                "time_known": self.birth.time_known,
            }
        return payload


@dataclass(frozen=True)
class Bundle:
    profiles: tuple[Profile, ...]

    @classmethod
    def from_dict(cls, raw: Any) -> "Bundle":
        if isinstance(raw, dict):
            items = raw.get("profiles")
        else:
            items = raw
        if not isinstance(items, list) or not items:
            raise ProfileError("payload must contain a non-empty 'profiles' list")

        profiles = tuple(Profile.from_dict(item, i) for i, item in enumerate(items))
        ids = [p.id for p in profiles]
        if len(ids) != len(set(ids)):
            raise ProfileError("profile ids must be unique")

        self_profiles = [p for p in profiles if p.role == "self"]
        if len(self_profiles) != 1:
            raise ProfileError("exactly one profile with role 'self' is required")

        partners = [p for p in profiles if p.role == "partner"]
        if len(partners) > 1:
            raise ProfileError("at most one profile with role 'partner' is supported")

        return cls(profiles=profiles)

    @property
    def self_profile(self) -> Profile:
        return next(p for p in self.profiles if p.role == "self")

    @property
    def partner(self) -> Profile | None:
        return next((p for p in self.profiles if p.role == "partner"), None)

    @property
    def children(self) -> tuple[Profile, ...]:
        return tuple(p for p in self.profiles if p.role == "child")

    def by_id(self, profile_id: str) -> Profile:
        for profile in self.profiles:
            if profile.id == profile_id:
                return profile
        raise KeyError(profile_id)

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "profiles": [p.to_dict() for p in self.profiles]}

    def summary(self) -> str:
        lines = []
        for profile in self.profiles:
            if profile.birth is None:
                detail = "بيانات أبراج فقط — بدون تاريخ/وقت ميلاد"
            else:
                known = "وقت معلوم" if profile.birth.time_known else "وقت غير معلوم"
                detail = (
                    f"{profile.birth.date} {profile.birth.time} "
                    f"{profile.birth.tz} — {known}"
                )
            lines.append(
                f"- {profile.name} ({profile.role}, id={profile.id}) — {detail}"
            )
        return "\n".join(lines)
