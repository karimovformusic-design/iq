from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.utils import simpleSplit


FONT_NAME = "MindoraDejaVu"
FONT_PATH = Path(__file__).parent / "assets" / "DejaVuSans.ttf"
LOCAL_TZ = ZoneInfo("Asia/Almaty")

if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))


def _draw_seal(pdf: Canvas, center_x: float, center_y: float) -> None:
    navy = HexColor("#16213E")
    cyan = HexColor("#36C5F0")
    purple = HexColor("#7558E8")

    pdf.saveState()
    pdf.setStrokeColor(navy)
    pdf.setLineWidth(2.2)
    pdf.circle(center_x, center_y, 43, stroke=1, fill=0)
    pdf.setStrokeColor(cyan)
    pdf.setLineWidth(0.9)
    pdf.circle(center_x, center_y, 37, stroke=1, fill=0)
    pdf.setFillColor(purple)
    pdf.setFont(FONT_NAME, 18)
    pdf.drawCentredString(center_x, center_y + 8, "M")
    pdf.setFillColor(navy)
    pdf.setFont(FONT_NAME, 7.2)
    pdf.drawCentredString(center_x, center_y - 7, "MINDORA BOT")
    pdf.setFillColor(HexColor("#526079"))
    pdf.setFont(FONT_NAME, 5.5)
    pdf.drawCentredString(center_x, center_y - 19, "TEST YAKUNLANDI")
    pdf.restoreState()


def build_iq_completion_certificate(
    *,
    first_name: str,
    last_name: str | None,
    age: int,
    score: int,
    max_score: int,
    completed_at: datetime | None,
) -> bytes:
    """Build a completion certificate, not an official IQ or clinical assessment."""
    full_name = " ".join(part.strip() for part in (first_name, last_name or "") if part and part.strip())
    if not full_name:
        raise ValueError("Sertifikat uchun foydalanuvchining ismi kerak.")
    if not 7 <= age <= 70:
        raise ValueError("Sertifikat yoshi 7–70 oralig‘ida bo‘lishi kerak.")
    if max_score <= 0 or not 0 <= score <= max_score:
        raise ValueError("Test natijasi noto‘g‘ri.")

    page_width, page_height = landscape(A4)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle("MINDORA — testni yakunlaganlik sertifikati")
    pdf.setAuthor("MINDORA bot")

    navy = HexColor("#16213E")
    cyan = HexColor("#36C5F0")
    purple = HexColor("#7558E8")
    muted = HexColor("#526079")

    pdf.setFillColor(HexColor("#FBFCFF"))
    pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    pdf.setStrokeColor(navy)
    pdf.setLineWidth(2)
    pdf.roundRect(24, 24, page_width - 48, page_height - 48, 16, stroke=1, fill=0)
    pdf.setStrokeColor(cyan)
    pdf.setLineWidth(0.8)
    pdf.roundRect(32, 32, page_width - 64, page_height - 64, 12, stroke=1, fill=0)

    pdf.setFillColor(navy)
    pdf.setFont(FONT_NAME, 17)
    pdf.drawCentredString(page_width / 2, page_height - 72, "MINDORA")
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 8.5)
    pdf.drawCentredString(page_width / 2, page_height - 89, "MINDORA BOT · TEST NATIJASI")

    pdf.setFillColor(purple)
    pdf.setFont(FONT_NAME, 21)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 137,
        "TESTNI YAKUNLAGANLIK SERTIFIKATI",
    )
    pdf.setStrokeColor(cyan)
    pdf.setLineWidth(1.2)
    pdf.line(page_width / 2 - 100, page_height - 151, page_width / 2 + 100, page_height - 151)

    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 10)
    pdf.drawCentredString(page_width / 2, page_height - 184, "Mantiqiy fikrlash mashqini yakunladi:")

    name_size = 24
    max_name_width = page_width - 130
    while name_size > 14 and pdfmetrics.stringWidth(full_name, FONT_NAME, name_size) > max_name_width:
        name_size -= 1
    name_lines = simpleSplit(full_name, FONT_NAME, name_size, max_name_width)
    pdf.setFillColor(navy)
    pdf.setFont(FONT_NAME, name_size)
    name_y = page_height - 220
    for line in name_lines[:2]:
        pdf.drawCentredString(page_width / 2, name_y, line)
        name_y -= name_size + 5

    info_y = name_y - 8
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 11)
    pdf.drawCentredString(page_width / 2, info_y, f"Yoshi: {age} yosh")

    percent = round(score * 100 / max_score)
    pdf.setFillColor(navy)
    pdf.setFont(FONT_NAME, 15)
    pdf.drawCentredString(page_width / 2, info_y - 39, f"Mashq natijasi: {score}/{max_score} ({percent}%)")

    if completed_at is None:
        date_label = "Sana ko‘rsatilmagan"
    else:
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        date_label = completed_at.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 10)
    pdf.drawCentredString(page_width / 2, info_y - 64, f"Yakunlangan sana: {date_label}")

    disclaimer = (
        "Ushbu hujjat MINDORA botidagi norasmiy mantiqiy fikrlash mashqini yakunlaganlikni qayd etadi. "
        "Natija rasmiy IQ bahosi, klinik xulosa yoki tashxis emas."
    )
    disclaimer_lines = simpleSplit(disclaimer, FONT_NAME, 8.2, page_width - 260)
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 8.2)
    disclaimer_x = 64
    disclaimer_y = 101
    for line in disclaimer_lines:
        pdf.drawString(disclaimer_x, disclaimer_y, line)
        disclaimer_y -= 12

    _draw_seal(pdf, page_width - 96, 101)
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 7)
    pdf.drawString(51, 48, "Avtomatik shakllantirildi · MINDORA Telegram bot")

    pdf.showPage()
    pdf.save()
    return output.getvalue()
