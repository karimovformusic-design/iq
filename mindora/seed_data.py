from __future__ import annotations

from dataclasses import dataclass

from mindora.constants import AGE_BANDS, QUESTION_COUNT_PER_ATTEMPT, TEST_NAMES


@dataclass(frozen=True)
class SeedQuestion:
    question_key: str
    category_slug: str
    age_band: str
    prompt_uz: str
    options_uz: list[str]
    correct_index: int | None = None
    factor: str | None = None
    reverse_scored: bool = False


_IQ_ITEMS = [
    ("Ketma-ketlikni davom ettiring: 3, 6, 9, 12, ?", ["14", "15", "16", "18"], 1),
    ("Qatorning keyingi sonini toping: 2, 4, 8, 16, ?", ["24", "30", "32", "34"], 2),
    ("Qonuniyatni davom ettiring: 1, 4, 9, 16, ?", ["20", "24", "25", "36"], 2),
    ("Ketma-ketlikda har safar 3 ayiriladi: 20, 17, 14, 11, ?", ["7", "8", "9", "10"], 1),
    ("Qatorni davom ettiring: 1, 3, 6, 10, ?", ["13", "14", "15", "16"], 2),
    ("Barcha lolalar gul. Bu o‘simlik lola. Qaysi xulosa to‘g‘ri?", ["U gul.", "U daraxt.", "U hayvon.", "Xulosa qilib bo‘lmaydi."], 0),
    ("Har bir uchburchakning 3 tomoni bor. Shakl uchburchak. Uning nechta tomoni bor?", ["2", "3", "4", "5"], 1),
    ("Agar chiroq yonsa, xona yorishadi. Chiroq yondi. Xona haqida nima aniq?", ["Xona yorishadi.", "Deraza ochiladi.", "Xona soviydi.", "Buni aniqlab bo‘lmaydi."], 0),
    ("Ali Barnodan katta, Barno esa Diyordan katta. Eng yoshi kim?", ["Ali", "Barno", "Diyor", "Aniqlab bo‘lmaydi."], 2),
    ("Bugun chorshanba. Ikki kundan keyin haftaning qaysi kuni bo‘ladi?", ["Payshanba", "Juma", "Shanba", "Yakshanba"], 1),
    ("Har bir qutida 2 ta olma bor. 3 ta qutida jami nechta olma bor?", ["5", "6", "8", "9"], 1),
    ("5 ta qalam 10 tanga turadi. Shu narxda 3 ta qalam qancha turadi?", ["4", "5", "6", "8"], 2),
    ("24 ta don 4 kishiga teng taqsimlandi. Har biriga nechtadan tegdi?", ["4", "5", "6", "8"], 2),
    ("Qaysi biri hafta kuni emas?", ["Dushanba", "Seshanba", "Yanvar", "Juma"], 2),
    ("Tish cho‘tkasi tish tozalash uchun. Taroq nima uchun ishlatiladi?", ["Soch tarash uchun", "Yozish uchun", "Ovqat pishirish uchun", "Vaqtni bilish uchun"], 0),
    ("Qaysi shaklning burchagi yo‘q?", ["Uchburchak", "Kvadrat", "To‘g‘ri to‘rtburchak", "Doira"], 3),
    ("Qaysi biri ovqatlanish anjomi emas?", ["Qoshiq", "Sanchqi", "Pichoq", "Yostiq"], 3),
    ("Qatorni davom ettiring: 2, 5, 11, 23, ?", ["45", "46", "47", "48"], 2),
    ("A, B, C, D bekatlari shu tartibda joylashgan. B bekatidan D gacha nechta bekat bor?", ["1", "2", "3", "4"], 1),
    ("Xaltada 2 ta qizil va 3 ta ko‘k shar bor. Qaysi rangdagi shar ko‘proq?", ["Qizil", "Ko‘k", "Teng", "Aniqlab bo‘lmaydi."], 1),
]


def _iq_questions(age_band: str) -> list[SeedQuestion]:
    return [
        SeedQuestion(
            question_key=f"iq:{age_band}:{number}",
            category_slug="iq",
            age_band=age_band,
            prompt_uz=prompt,
            options_uz=options,
            correct_index=correct,
        )
        for number, (prompt, options, correct) in enumerate(
            _IQ_ITEMS[:QUESTION_COUNT_PER_ATTEMPT],
            start=1,
        )
    ]


_PERSONALITY_ITEMS = [
    ("curiosity", "Yangi mavzuni tushunish uchun uning sabablarini bilishga qiziqaman.", False),
    ("curiosity", "Bir g‘oyaga turli tomondan qarab ko‘rishni yoqtiraman.", False),
    ("curiosity", "Odatdagi yo‘ldan boshqa usulni sinab ko‘rishga tayyorman.", False),
    ("curiosity", "Notanish mavzular bilan tanishish men uchun unchalik qiziq emas.", True),
    ("reliability", "Vazifani boshlashdan oldin uni kichik bosqichlarga ajrataman.", False),
    ("reliability", "Belgilagan muddatimga amal qilishga intilaman.", False),
    ("reliability", "Boshlagan ishimni yakunlash uchun muntazam qadam tashlayman.", False),
    ("reliability", "Vazifalarimni ko‘pincha keyinga surib qo‘yaman.", True),
    ("sociability", "Kichik guruhda o‘z fikrimni aytish menga qulay.", False),
    ("sociability", "Yangi odam bilan suhbat boshlashga qiynalaman.", True),
    ("sociability", "Guruh bilan ishlaganda umumiy muhokamaga hissa qo‘shaman.", False),
    ("sociability", "Suhbatda boshqalarning fikrini bilish uchun savol beraman.", False),
    ("kindness", "Boshqa odam vaziyatga men ko‘rmagan tomondan qarashi mumkinligini hisobga olaman.", False),
    ("kindness", "Kelishmovchilikda ham suhbatdoshimni hurmat bilan tinglayman.", False),
    ("kindness", "Boshqalarning his-tuyg‘ularini payqashga e’tibor beraman.", False),
    ("kindness", "Fikrimga qo‘shilmagan odamni tinglashni ortiqcha deb bilaman.", True),
    ("calmness", "Kutilmagan vaziyatda avval to‘xtab, keyin harakat rejasini tuzaman.", False),
    ("calmness", "Hayajonlanganimda e’tiborimni jamlashga yordam beradigan usulni topaman.", False),
    ("calmness", "Rejalarim o‘zgarsa, yangi tartibga moslashib ketaman.", False),
    ("calmness", "Mayda xato sababli o‘zimni uzoq vaqt ayblab yuraman.", True),
]

_WELLBEING_ITEMS = [
    ("energy", "Ertalab o‘zimni dam olgan his qildim.", False),
    ("energy", "Kun davomida quvvatim kundalik ishlarimga yetdi.", False),
    ("energy", "Tanaffus yoki uyqudan keyin kuchim tiklanganini sezdim.", False),
    ("energy", "Dam olishga vaqt ajratish menga qiyin bo‘ldi.", True),
    ("interest", "Menga qiziq bo‘lgan mashg‘ulotga vaqt ajratdim.", False),
    ("interest", "Yoqimli yoki kulgili lahzalarni payqadim.", False),
    ("interest", "Yangi yoki foydali narsani o‘rganishdan zavq oldim.", False),
    ("interest", "Kunlarimda yoqimli mashg‘ulot uchun joy topish qiyin bo‘ldi.", True),
    ("self_awareness", "Hislarimni nomlab, nimani boshdan kechirayotganimni payqadim.", False),
    ("self_awareness", "Xato qilganimda o‘zimga muloyim gapirishga harakat qildim.", False),
    ("self_awareness", "Hissiyotlarimni tushunish uchun bir oz vaqt ajratdim.", False),
    ("self_awareness", "Mayda xatoim uchun o‘zimni uzoq tanqid qildim.", True),
    ("daily_routine", "Kundalik vazifalardan kamida bir nechtasini uddaladim.", False),
    ("daily_routine", "Muhim ishlarim uchun keyingi qadamni belgiladim.", False),
    ("daily_routine", "Dam olish va majburiyatlar o‘rtasida mos muvozanat topdim.", False),
    ("daily_routine", "Oddiy vazifalar ham menga odatdagidan og‘ir tuyuldi.", True),
    ("connection", "Yaqinlarim bilan samimiy suhbatlashdim.", False),
    ("connection", "O‘zimni oila, do‘stlar yoki jamoaning bir qismi deb his qildim.", False),
    ("connection", "Fikrim yoki hislarimni ishonchli inson bilan bo‘lishdim.", False),
    ("connection", "O‘zimni atrofdagilardan uzilib qolgandek his qildim.", True),
]


def build_question_bank() -> list[SeedQuestion]:
    bank: list[SeedQuestion] = []
    for _minimum, _maximum, age_band in AGE_BANDS:
        bank.extend(_iq_questions(age_band))
        for index, (factor, text, reverse) in enumerate(
            _PERSONALITY_ITEMS[:QUESTION_COUNT_PER_ATTEMPT],
            start=1,
        ):
            bank.append(
                SeedQuestion(
                    question_key=f"personality:{age_band}:v2:{index}",
                    category_slug="personality",
                    age_band=age_band,
                    prompt_uz=f"Odatda, {text[0].lower()}{text[1:]}",
                    options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha", "Deyarli doimo"],
                    factor=factor,
                    reverse_scored=reverse,
                )
            )
        for index, (factor, prompt, reverse) in enumerate(
            _WELLBEING_ITEMS[:QUESTION_COUNT_PER_ATTEMPT],
            start=1,
        ):
            bank.append(
                SeedQuestion(
                    question_key=f"wellbeing:{age_band}:v2:{index}",
                    category_slug="wellbeing",
                    age_band=age_band,
                    prompt_uz=f"So‘nggi ikki hafta ichida {prompt[0].lower()}{prompt[1:]}",
                    options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha"],
                    factor=factor,
                    reverse_scored=reverse,
                )
            )
    return bank


CATEGORIES = [
    {
        "slug": "iq",
        "name_uz": TEST_NAMES["iq"],
        "description_uz": "Mantiqiy naqshlar va xulosalash bo‘yicha qisqa norasmiy mashq.",
        "sort_order": 1,
    },
    {
        "slug": "personality",
        "name_uz": TEST_NAMES["personality"],
        "description_uz": "Odatdagi qiziqish, ish uslubi va muloqot afzalliklarini o‘rganadigan norasmiy so‘rovnoma.",
        "sort_order": 2,
    },
    {
        "slug": "wellbeing",
        "name_uz": TEST_NAMES["wellbeing"],
        "description_uz": "So‘nggi ikki haftadagi kundalik farovonlikni mulohaza qilish uchun norasmiy so‘rovnoma.",
        "sort_order": 3,
    },
]
