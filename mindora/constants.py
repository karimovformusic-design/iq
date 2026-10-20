"""Product configuration defaults and user-facing labels."""

PAYMENT_RECIPIENT = "Karimov Nosirjon"
PAYMENT_CARD_NUMBER = "5614684702056944"
PRICE_PER_REPORT_UZS = 11_900
ADMIN_CONTACT = "@Karimov_112"

TEST_NAMES = {
    "iq": "Mantiqiy fikrlash (IQ uslubidagi test)",
    "personality": "Shaxsiyat testi",
    "wellbeing": "Psixologik farovonlik testi",
}

AGE_BANDS = (
    (7, 12, "7-12"),
    (13, 17, "13-17"),
    (18, 30, "18-30"),
    (31, 50, "31-50"),
    (51, 70, "51-70"),
)

QUESTION_COUNT_PER_ATTEMPT = 35
USER_PAGE_SIZE = 10
BROADCAST_SEND_INTERVAL_SECONDS = 0.16
BROADCAST_MAX_ATTEMPTS = 4


def age_band_for(age: int) -> str:
    if not 7 <= age <= 70:
        raise ValueError("Age must be between 7 and 70.")
    for minimum, maximum, band in AGE_BANDS:
        if minimum <= age <= maximum:
            return band
    raise ValueError("No age band configured.")
