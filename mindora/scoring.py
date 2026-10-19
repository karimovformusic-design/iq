from collections import defaultdict
from typing import Any

from mindora.constants import TEST_NAMES
from mindora.models import Question


def score_answers(
    category_slug: str,
    questions: list[Question],
    answer_indexes: list[int],
) -> tuple[int, int, str]:
    if len(questions) != len(answer_indexes) or not questions:
        raise ValueError("A completed attempt must have one answer for every question.")

    if category_slug == "iq":
        correct = sum(
            1
            for question, answer in zip(questions, answer_indexes, strict=True)
            if question.correct_index == answer
        )
        maximum = len(questions)
        percent = round(correct * 100 / maximum)
        report = (
            f"🧠 {TEST_NAMES['iq']}\n\n"
            f"Natija: {correct}/{maximum} ({percent}%).\n"
            f"Bu qisqa, norasmiy mantiqiy fikrlash mashqi; u klinik yoki rasmiy IQ bahosi emas.\n\n"
            f"Kuchli tomoningiz: {('naqshlarni topish va xulosalash' if percent >= 70 else 'mantiqiy masalalarda izchil mashq qilish')}. "
            f"Yangi topshiriqlarni shoshilmasdan tahlil qilish natijani yaxshilashga yordam beradi."
        )
        return correct, maximum, report

    factor_scores: dict[str, list[int]] = defaultdict(list)
    for question, answer in zip(questions, answer_indexes, strict=True):
        if question.factor:
            value = 4 - answer if question.reverse_scored else answer
            factor_scores[question.factor].append(value)

    if category_slug == "personality":
        factors_uz = {
            "curiosity": "Qiziquvchanlik",
            "reliability": "Mas’uliyat",
            "sociability": "Muloqotga ochiqlik",
            "kindness": "Hamkorlik",
            "calmness": "Xotirjamlik",
        }
        normalized = {
            key: round(sum(values) * 100 / (4 * len(values)))
            for key, values in factor_scores.items()
            if values
        }
        strongest = sorted(normalized.items(), key=lambda item: item[1], reverse=True)[:2]
        top_text = "\n".join(f"• {factors_uz[key]}: {value}%" for key, value in strongest)
        report = (
            f"🌱 {TEST_NAMES['personality']}\n\n"
            f"Sizning javoblaringizdagi ko‘proq namoyon bo‘lgan yo‘nalishlar:\n{top_text or '• Profil hisoblanmadi.'}\n\n"
            "Bu o‘zini anglash uchun mo‘ljallangan norasmiy so‘rovnoma; tashxis yoki o‘zgarmas shaxsiyat ta’rifi emas. "
            "Turli vaziyatlarda javoblar o‘zgarishi tabiiy."
        )
        score = round(sum(normalized.values()) / len(normalized)) if normalized else 0
        return score, 100, report

    if category_slug == "wellbeing":
        total = sum(sum(values) for values in factor_scores.values())
        maximum = sum(3 * len(values) for values in factor_scores.values())
        percent = round(total * 100 / maximum) if maximum else 0
        if percent >= 75:
            message = "Javoblaringiz hozirgi paytda kundalik tayanch va ijobiy holatlar mavjudligini ko‘rsatadi."
        elif percent >= 50:
            message = "Ayrim kunlarda o‘zingizga ko‘proq vaqt ajratish va ishonchli inson bilan suhbatlashish foydali bo‘lishi mumkin."
        else:
            message = (
                "Javoblaringiz oxirgi paytlar qiyinroq kechayotgan bo‘lishi mumkinligini ko‘rsatadi. "
                "Ishonchli yaqin inson yoki malakali mutaxassis bilan gaplashishni ko‘rib chiqing."
            )
        report = (
            f"💛 {TEST_NAMES['wellbeing']}\n\n"
            f"Farovonlik indeksi: {percent}%.\n{message}\n\n"
            "Bu qisqa o‘zini baholash so‘rovnomasi, klinik tekshiruv yoki tashxis emas. "
            "Agar o‘zingizni xavfsiz his qilmasangiz, yoningizdagi ishonchli kattaga yoki mahalliy shoshilinch yordamga murojaat qiling."
        )
        return total, maximum, report

    raise ValueError("Unknown test category.")


def question_payload(question: Question) -> dict[str, Any]:
    return {
        "id": question.id,
        "prompt": question.prompt_uz,
        "options": question.options_uz,
    }
