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


def logical_reasoning_band(score_percent: int) -> tuple[str, str]:
    if score_percent < 40:
        return "Rivojlanish bosqichi", "Developing"
    if score_percent < 60:
        return "Boshlang‘ich", "Foundational"
    if score_percent < 80:
        return "Yaxshi", "Strong"
    return "Yuqori", "Advanced"


def _draw_centered_wrapped(
    pdf: Canvas,
    text: str,
    *,
    center_x: float,
    y: float,
    max_width: float,
    font_size: float,
    color,
    leading: float,
) -> float:
    lines = simpleSplit(text, FONT_NAME, font_size, max_width)
    pdf.setFillColor(color)
    pdf.setFont(FONT_NAME, font_size)
    for line in lines:
        pdf.drawCentredString(center_x, y, line)
        y -= leading
    return y


def build_iq_completion_certificate(
    *,
    first_name: str,
    last_name: str | None,
    age: int,
    score: int,
    max_score: int,
    completed_at: datetime | None,
    age_band: str | None = None,
    percentile: int | None = None,
    cohort_size: int = 0,
    certificate_number: int | None = None,
) -> bytes:
    """Build a completion certificate, not an official IQ or clinical assessment."""
    full_name = " ".join(part.strip() for part in (first_name, last_name or "") if part and part.strip())
    if not full_name:
        raise ValueError("Sertifikat uchun foydalanuvchining ismi kerak.")
    if not 7 <= age <= 70:
        raise ValueError("Sertifikat yoshi 7–70 oralig‘ida bo‘lishi kerak.")
    if max_score <= 0 or not 0 <= score <= max_score:
        raise ValueError("Test natijasi noto‘g‘ri.")
    if percentile is not None and not 0 <= percentile <= 100:
        raise ValueError("Foizli o‘rin noto‘g‘ri.")
    if cohort_size < 0:
        raise ValueError("Taqqoslash ishtirokchilari soni noto‘g‘ri.")

    page_width, page_height = landscape(A4)
    output = BytesIO()
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height), pageCompression=1)
    pdf.setTitle("MINDORA Certificate of Completion — Logical Reasoning Practice")
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
    pdf.drawCentredString(
        page_width / 2,
        page_height - 89,
        "MINDORA TELEGRAM BOT · CERTIFICATE OF COMPLETION",
    )
    if certificate_number is not None:
        pdf.setFont(FONT_NAME, 8)
        pdf.drawRightString(
            page_width - 50,
            page_height - 62,
            f"Certificate No. MND-IQ-{certificate_number:06d}",
        )

    pdf.setFillColor(purple)
    pdf.setFont(FONT_NAME, 18)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 137,
        "CERTIFICATE OF COMPLETION · YAKUNLAGANLIK SERTIFIKATI",
    )
    pdf.setStrokeColor(cyan)
    pdf.setLineWidth(1.2)
    pdf.line(page_width / 2 - 100, page_height - 151, page_width / 2 + 100, page_height - 151)

    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 10)
    pdf.drawCentredString(
        page_width / 2,
        page_height - 184,
        "Awarded to · Quyidagi ishtirokchiga taqdim etiladi:",
    )

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
    band_uz, band_en = logical_reasoning_band(percent)
    pdf.setFillColor(navy)
    pdf.setFont(FONT_NAME, 15)
    pdf.drawCentredString(
        page_width / 2,
        info_y - 36,
        f"Exercise score · Mashq natijasi: {score}/{max_score} ({percent}%)",
    )

    performance_text = (
        f"Exercise-specific reasoning indicator · Shu mashq doirasidagi mantiqiy "
        f"salohiyat ko‘rsatkichi: {band_en} · {band_uz}"
    )
    _draw_centered_wrapped(
        pdf,
        performance_text,
        center_x=page_width / 2,
        y=info_y - 58,
        max_width=page_width - 100,
        font_size=9.2,
        color=navy,
        leading=12,
    )

    if percentile is not None and cohort_size >= 10:
        cohort_text = (
            f"MINDORA participant percentile · MINDORA botidagi bir xil yosh guruhida "
            f"taxminiy foizli o‘rin: {percentile}/100 (n={cohort_size}, age band · yosh guruhi "
            f"{age_band or '—'})."
        )
    else:
        cohort_text = (
            f"Percentile not reported · Foizli taqqoslash berilmadi: bir xil yosh guruhida "
            f"yetarli MINDORA natijasi yo‘q (n={cohort_size}, kamida 10 talab qilinadi)."
        )
    next_y = _draw_centered_wrapped(
        pdf,
        cohort_text,
        center_x=page_width / 2,
        y=info_y - 80,
        max_width=page_width - 100,
        font_size=8.3,
        color=muted,
        leading=10.5,
    )

    if completed_at is None:
        date_label = "Sana ko‘rsatilmagan"
    else:
        if completed_at.tzinfo is None:
            completed_at = completed_at.replace(tzinfo=timezone.utc)
        date_label = completed_at.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 10)
    pdf.drawCentredString(
        page_width / 2,
        next_y - 3,
        f"Issued on · Berilgan sana: {date_label}",
    )

    disclaimer = (
        "Bu qisqa, standartlashtirilmagan mashq rasmiy IQ yoki klinik baho emas va insonning umumiy "
        "salohiyatini o‘lchamaydi. Foizli o‘rin faqat MINDORA botidagi shu yosh guruhining "
        "ishtirokchilari bilan taqqoslaydi; umumiy aholi normasi emas. "
        "This non-standardized exercise is not an official IQ or clinical assessment and does not "
        "measure overall potential. Any percentile compares only MINDORA users in the same age band, "
        "not the general population."
    )
    disclaimer_lines = simpleSplit(disclaimer, FONT_NAME, 7.2, page_width - 260)
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 7.2)
    disclaimer_x = 64
    disclaimer_y = 92
    for line in disclaimer_lines:
        pdf.drawString(disclaimer_x, disclaimer_y, line)
        disclaimer_y -= 10

    _draw_seal(pdf, page_width - 96, 91)
    pdf.setFillColor(muted)
    pdf.setFont(FONT_NAME, 7)
    pdf.drawString(51, 48, "Issued electronically by · Elektron tarzda berildi: MINDORA Telegram bot")

    pdf.showPage()
    pdf.save()
    return output.getvalue()
