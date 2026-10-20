from __future__ import annotations


def normalize_registration_name(value: str) -> str:
    """Normalize a user-entered name while allowing Unicode and multi-part names."""
    name = " ".join(value.split())
    if (
        not name
        or len(name) > 128
        or not any(character.isalpha() for character in name)
        or any(ord(character) < 32 for character in name)
    ):
        raise ValueError("Ism yoki familiyani matn ko‘rinishida kiriting (1–128 belgi).")
    return name


def parse_registration_age(value: str) -> int:
    text = value.strip()
    if not text.isdecimal():
        raise ValueError("Yoshingizni 7 dan 70 gacha bo‘lgan butun son bilan kiriting.")
    age = int(text)
    if not 7 <= age <= 70:
        raise ValueError("Yoshingizni 7 dan 70 gacha bo‘lgan butun son bilan kiriting.")
    return age
