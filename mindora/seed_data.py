from __future__ import annotations

from dataclasses import dataclass

from mindora.constants import AGE_BANDS, TEST_NAMES


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


def _iq_questions(age_band: str, level: int) -> list[SeedQuestion]:
    questions: list[SeedQuestion] = []
    for number in range(1, 26):
        mode = number % 5
        if mode == 0:
            start = 2 + level * 3 + number
            step = 2 + (number % 4) + level
            sequence = [start + step * index for index in range(5)]
            answer = start + step * 5
            options = [answer, answer + step, answer - 1, answer + 2 * step]
            prompt = f"Ketma-ketlikni davom ettiring: {', '.join(map(str, sequence))}, ?"
            correct = 0
        elif mode == 1:
            base = 2 + level + (number % 5)
            multiplier = 2 + (number % 2)
            sequence = [base * multiplier**index for index in range(4)]
            answer = base * multiplier**4
            options = [answer - base, answer, answer + base, answer * 2]
            prompt = f"Qatorning keyingi sonini toping: {', '.join(map(str, sequence))}, ?"
            correct = 1
        elif mode == 2:
            offset = level + (number % 3)
            start_n = 2 + (number % 4)
            sequence = [index * index + offset for index in range(start_n, start_n + 4)]
            answer = (start_n + 4) ** 2 + offset
            options = [answer + 1, answer, answer - 2, answer + 4]
            prompt = f"Qonuniyatni aniqlang: {', '.join(map(str, sequence))}, ?"
            correct = 1
        elif mode == 3:
            prompt = "Barcha lolalar gul. Bu bog‘dagi ayrim gullar sariq. Qaysi xulosa aniq to‘g‘ri?"
            options = [
                "Barcha gullar lola.",
                "Lola gul hisoblanadi.",
                "Barcha lolalar sariq.",
                "Sariq gullarning barchasi lola.",
            ]
            correct = 1
        else:
            apple_count = 3 + level + (number % 4)
            box_count = 2 + (number % 3)
            answer = apple_count * box_count
            options = [str(answer + 1), str(answer - 1), str(answer), str(answer + box_count)]
            prompt = f"Har bir qutida {apple_count} tadan olma bor. {box_count} ta qutida jami nechta olma bor?"
            correct = 2

        if mode != 3:
            correct_value = options[correct]
            # Deterministic order keeps seed runs stable and makes scoring unambiguous.
            rotate = (number + level) % len(options)
            options = options[rotate:] + options[:rotate]
            correct = options.index(correct_value)
            options = [str(value) for value in options]

        questions.append(
            SeedQuestion(
                question_key=f"iq:{age_band}:{number}",
                category_slug="iq",
                age_band=age_band,
                prompt_uz=prompt,
                options_uz=options,
                correct_index=correct,
            )
        )
    return questions


_PERSONALITY_ITEMS = [
    ("curiosity", "Yangi narsalarni o‘rganishga qiziqaman.", False),
    ("curiosity", "Biror mavzuni tushunish uchun savollar beraman.", False),
    ("curiosity", "Yangi g‘oyalarni sinab ko‘rishni yoqtirmayman.", True),
    ("curiosity", "Turli fikrlarni tinglash menga qiziq.", False),
    ("reliability", "Boshlagan ishimni oxiriga yetkazishga harakat qilaman.", False),
    ("reliability", "Vazifalarimni oldindan rejalashtiraman.", False),
    ("reliability", "Muhim ishlarni tez-tez unutib qo‘yaman.", True),
    ("reliability", "Bergan va’damni bajarishga intilaman.", False),
    ("sociability", "Guruhda fikrimni aytish menga qulay.", False),
    ("sociability", "Yangi odamlar bilan suhbat boshlashdan qochaman.", True),
    ("sociability", "Yaqinlarim bilan birga vaqt o‘tkazishni yoqtiraman.", False),
    ("sociability", "Suhbatda boshqalarning gapini tinglayman.", False),
    ("kindness", "Boshqalarning his-tuyg‘ularini tushunishga harakat qilaman.", False),
    ("kindness", "Kerak bo‘lsa, boshqalarga yordam beraman.", False),
    ("kindness", "Kelishmovchilikda faqat o‘z fikrimni o‘tkazishga urinaman.", True),
    ("kindness", "Boshqalar bilan hurmat bilan gaplashaman.", False),
    ("calmness", "Qiyin vaziyatda tinchlanish uchun tanaffus qilaman.", False),
    ("calmness", "Xato qilsam, o‘zimni uzoq vaqt ayblayman.", True),
    ("calmness", "Hayajonlangan paytimda nafasimni rostlashga harakat qilaman.", False),
    ("calmness", "O‘zgarishlarga moslashishim mumkin.", False),
]

_WELLBEING_ITEMS = [
    "O‘zimni dam olgan va quvvatli his qildim.",
    "Kun davomida yoqimli yoki qiziqarli ish bilan shug‘ullandim.",
    "Ishonchli inson bilan gaplashish imkonim bo‘ldi.",
    "Biror vazifa qiyin bo‘lsa, yordam so‘ray oldim.",
    "Uyqum va dam olishim yetarli bo‘ldi.",
    "O‘zimga mehr bilan munosabatda bo‘ldim.",
    "Hissiyotlarimni tushunish uchun vaqt ajratdim.",
    "O‘qish, ish yoki өдөр тутмын ishlarimni uddalay oldim.",
    "Meni quvontiradigan kichik bir narsani payqadim.",
    "Boshqalardan kerakli yordam yoki dalda oldim.",
    "Dam olish va mashg‘ulotlar o‘rtasida muvozanat saqladim.",
    "O‘zimni jamoa yoki yaqinlarim bilan bog‘liq his qildim.",
    "Tanaffus qilish kerakligini sezib, o‘zimga ruxsat berdim.",
    "Qiyin paytda keyingi kichik qadamni topa oldim.",
    "O‘zim uchun muhim bo‘lgan ishga vaqt topdim.",
    "Atrofimdagi ishonchli insonlar bilan o‘zimni xavfsiz his qildim.",
    "O‘zimning kuchli tomonlarimni eslay oldim.",
    "Hordiq chiqarish uchun yoqimli mashg‘ulot topdim.",
    "Bugungi kunimda qadrlaydigan biror narsani ko‘rdim.",
    "Ertangi kun haqida umid yoki qiziqish his qildim.",
]


def build_question_bank() -> list[SeedQuestion]:
    bank: list[SeedQuestion] = []
    for level, (minimum, maximum, age_band) in enumerate(AGE_BANDS):
        bank.extend(_iq_questions(age_band, level))
        if age_band in {"7-12", "13-17"}:
            context = "maktab"
            reliability_prompt = "Maktabdagi vazifalarimni oldindan rejalashtiraman."
        elif age_band == "18-30":
            context = "o‘qish yoki ish"
            reliability_prompt = "O‘qish yoki ishdagi vazifalarimni oldindan rejalashtiraman."
        else:
            context = "kundalik"
            reliability_prompt = "Kundalik vazifalarimni oldindan rejalashtiraman."
        for index, (factor, text, reverse) in enumerate(_PERSONALITY_ITEMS, start=1):
            age_specific = reliability_prompt if index == 6 else text
            bank.append(
                SeedQuestion(
                    question_key=f"personality:{age_band}:{index}",
                    category_slug="personality",
                    age_band=age_band,
                    prompt_uz=age_specific,
                    options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha", "Deyarli doimo"],
                    factor=factor,
                    reverse_scored=reverse,
                )
            )
        for index, prompt in enumerate(_WELLBEING_ITEMS, start=1):
            if index == 8 and context == "maktab":
                age_prompt = "Maktabdagi kundalik vazifalarimni uddalay oldim."
            elif index == 8 and context == "o‘qish yoki ish":
                age_prompt = "O‘qish yoki ishdagi kundalik vazifalarimni uddalay oldim."
            elif index == 8:
                age_prompt = "Kundalik vazifalarimni uddalay oldim."
            else:
                age_prompt = prompt
            bank.append(
                SeedQuestion(
                    question_key=f"wellbeing:{age_band}:{index}",
                    category_slug="wellbeing",
                    age_band=age_band,
                    prompt_uz=age_prompt,
                    options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha"],
                    factor="wellbeing",
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
        "description_uz": "O‘zini anglashga yordam beradigan, klinik bo‘lmagan so‘rovnoma.",
        "sort_order": 2,
    },
    {
        "slug": "wellbeing",
        "name_uz": TEST_NAMES["wellbeing"],
        "description_uz": "Oxirgi paytdagi kundalik farovonlikni mulohaza qilish uchun so‘rovnoma.",
        "sort_order": 3,
    },
]
