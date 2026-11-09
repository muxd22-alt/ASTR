"""Arabic labels, sign tables, and formatting helpers."""

from __future__ import annotations

from datetime import date, datetime

SIGNS_AR = [
    "الحمل",
    "الثور",
    "الجوزاء",
    "السرطان",
    "الأسد",
    "العذراء",
    "الميزان",
    "العقرب",
    "القوس",
    "الجدي",
    "الدلو",
    "الحوت",
]

SIGNS_EN = [
    "Aries",
    "Taurus",
    "Gemini",
    "Cancer",
    "Leo",
    "Virgo",
    "Libra",
    "Scorpio",
    "Sagittarius",
    "Capricorn",
    "Aquarius",
    "Pisces",
]

SIGN_ELEMENTS = [
    "fire",
    "earth",
    "air",
    "water",
    "fire",
    "earth",
    "air",
    "water",
    "fire",
    "earth",
    "air",
    "water",
]

SIGN_MODALITIES = [
    "cardinal",
    "fixed",
    "mutable",
    "cardinal",
    "fixed",
    "mutable",
    "cardinal",
    "fixed",
    "mutable",
    "cardinal",
    "fixed",
    "mutable",
]

ELEMENTS_AR = {
    "fire": "ناري",
    "earth": "ترابي",
    "air": "هوائي",
    "water": "مائي",
}

MODALITIES_AR = {
    "cardinal": "أساسي",
    "fixed": "ثابت",
    "mutable": "متغيّر",
}

BODIES_AR = {
    "sun": "الشمس",
    "moon": "القمر",
    "mercury": "عطارد",
    "venus": "الزهرة",
    "mars": "المريخ",
    "jupiter": "المشتري",
    "saturn": "زحل",
    "uranus": "أورانوس",
    "neptune": "نبتون",
    "pluto": "بلوتو",
    "node": "العقدة الشمالية",
    "asc": "الطالع",
    "mc": "وسط السماء",
    "dsc": "الغروب",
    "ic": "الرابع",
}

ASPECTS_AR = {
    "conjunction": "اقتران",
    "opposition": "تقابل",
    "trine": "تثليث",
    "square": "تربيع",
    "sextile": "تسديس",
    "quincunx": "زاوية 150°",
    "semisextile": "زاوية 30°",
    "semisquare": "زاوية 45°",
    "sesquiquadrate": "زاوية 135°",
}

ASPECT_NATURE_AR = {
    "conjunction": "دمج مباشر",
    "opposition": "توتر بين طرفين",
    "trine": "تدفق وسهولة",
    "square": "احتكاك يدفع للتعديل",
    "sextile": "فرصة تحتاج مبادرة",
    "quincunx": "عدم توافق يحتاج تعديلًا",
    "semisextile": "تلامس خفيف",
    "semisquare": "ضغط صغير متكرر",
    "sesquiquadrate": "ضغط يحتاج تفريغًا",
}

MONTHS_AR = [
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
]

WEEKDAYS_AR = [
    "الاثنين",
    "الثلاثاء",
    "الأربعاء",
    "الخميس",
    "الجمعة",
    "السبت",
    "الأحد",
]


def sign_name(sign: int) -> str:
    return SIGNS_AR[sign % 12]


def sign_element(sign: int) -> str:
    return SIGN_ELEMENTS[sign % 12]


def sign_modality(sign: int) -> str:
    return SIGN_MODALITIES[sign % 12]


def sign_of(lon: float) -> int:
    return int((lon % 360) // 30)


def degree_in_sign(lon: float) -> float:
    return lon % 30


def format_degree(lon: float) -> str:
    sign = sign_of(lon)
    degree = degree_in_sign(lon)
    whole = int(degree)
    minutes = int(round((degree - whole) * 60))
    if minutes == 60:
        whole += 1
        minutes = 0
    if whole == 30:
        whole = 0
        sign = (sign + 1) % 12
    return f"{whole}°{minutes:02d}′ {SIGNS_AR[sign]}"


def format_date(value: date, include_weekday: bool = True) -> str:
    text = f"{value.day} {MONTHS_AR[value.month - 1]} {value.year}"
    if include_weekday:
        return f"{WEEKDAYS_AR[value.weekday()]} {text}"
    return text


def format_date_short(value: date) -> str:
    return f"{value.day} {MONTHS_AR[value.month - 1]}"


def format_datetime(value: datetime, tz_label: str | None = None) -> str:
    text = f"{format_date_short(value.date())} — {value:%H:%M}"
    if tz_label:
        text += f" ({tz_label})"
    return text


def element_ar(element: str) -> str:
    return ELEMENTS_AR.get(element, element)


def modality_ar(modality: str) -> str:
    return MODALITIES_AR.get(modality, modality)
