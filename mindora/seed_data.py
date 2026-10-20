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
    "Kundalik vazifalarimni uddalay oldim.",
    "Meni quvontiradigan kichik bir narsani payqadim.",
    "Boshqalardan kerakli yordam yoki dalda oldim.",
    "Dam olish va mashg‘ulotlar o‘rtasida muvozanat saqladim.",
    "O‘zimni jamoa yoki yaqinlarim bilan bog‘liq his qildim.",
    "Tanaffus qilish kerakligini sezib, o‘zimga ruxsat berdim.",
    "Qiyin paytda keyingi kichik qadamni topa oldim.",
    "O‘zim uchun muhim bo‘lgan ishga vaqt topdim.",
    "Atrofimdagi ishonchli insonlar bilan o‘zimni xavfsiz his qildim.",
    "O‘zimning kuchli tomonlarimni eslay oldim.",
    "Tanamning suv, ovqat yoki harakat kabi ehtiyojlarini payqab, ularga e’tibor berdim.",
    "Bugungi kunimda qadrlaydigan biror narsani ko‘rdim.",
    "Ertangi kun haqida umid yoki qiziqish his qildim.",
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
                    question_key=f"personality:{age_band}:{index}",
                    category_slug="personality",
                    age_band=age_band,
                    prompt_uz=text,
                    options_uz=["Hech qachon", "Kamdan-kam", "Ba’zan", "Ko‘pincha", "Deyarli doimo"],
                    factor=factor,
                    reverse_scored=reverse,
                )
            )
        for index, prompt in enumerate(
            _WELLBEING_ITEMS[:QUESTION_COUNT_PER_ATTEMPT],
            start=1,
        ):
            bank.append(
                SeedQuestion(
                    question_key=f"wellbeing:{age_band}:{index}",
                    category_slug="wellbeing",
                    age_band=age_band,
                    prompt_uz=prompt,
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
