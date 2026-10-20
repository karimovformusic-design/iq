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


_IQ_LOGIC_ITEMS = [
    (
        "Barcha lolalar gul. Bu bog‘dagi ayrim gullar sariq. Qaysi xulosa aniq to‘g‘ri?",
        ["Barcha gullar lola.", "Lola gul hisoblanadi.", "Barcha lolalar sariq.", "Sariq gullarning barchasi lola."],
        1,
    ),
    (
        "Barcha sayyohlar xarita olib yuradi. Nodira sayyoh. Qaysi xulosa aniq?",
        ["Nodira xarita olib yuradi.", "Nodira xarita chizadi.", "Xarita olganlarning barchasi sayyoh.", "Nodira sayohat qilmaydi."],
        0,
    ),
    (
        "Agar chiroq yonsa, xona yorishadi. Chiroq yondi. Nima aniq?",
        ["Xona qorong‘i bo‘ladi.", "Chiroq o‘chadi.", "Xona yorishadi.", "Deraza ochiladi."],
        2,
    ),
    (
        "Ba’zi kitoblar qalin. Barcha qalin kitoblarda belgi bor. Qaysi xulosa aniq?",
        ["Barcha kitoblar qalin.", "Ayrim kitoblarda belgi bor.", "Belgi bor kitoblarning hammasi qalin.", "Qalin kitoblar kitob emas."],
        1,
    ),
    (
        "Har bir uchburchakning uchta tomoni bor. Bu shakl uchburchak. Qaysi xulosa to‘g‘ri?",
        ["Shaklning uchta tomoni bor.", "Shakl doira.", "Uchburchakning to‘rtta tomoni bor.", "Shaklning tomonlari yo‘q."],
        0,
    ),
    (
        "Agar yomg‘ir yog‘sa, yo‘lak nam bo‘ladi. Yomg‘ir yog‘di. Qaysi xulosa aniq?",
        ["Yo‘lak quruq.", "Yomg‘ir to‘xtadi.", "Yo‘lak nam bo‘ladi.", "Ko‘chada odam yo‘q."],
        2,
    ),
    (
        "Barcha suv o‘simliklari suvda o‘sadi. Nilufar suv o‘simligi. Qaysi xulosa to‘g‘ri?",
        ["Nilufar suvda o‘sadi.", "Suvdagi barcha o‘simliklar nilufar.", "Nilufar o‘simlik emas.", "Nilufar faqat quruqlikda o‘sadi."],
        0,
    ),
]


def _iq_questions(age_band: str, level: int) -> list[SeedQuestion]:
    questions: list[SeedQuestion] = []
    for number in range(1, 36):
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
            slot = number // 5
            base = 2 + level + slot
            multiplier = 2 + (slot % 2)
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
            prompt, options, correct = _IQ_LOGIC_ITEMS[(number // 5) % len(_IQ_LOGIC_ITEMS)]
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
    ("curiosity", "Notanish vazifani ko‘rsam, uni o‘rganishga qiziqaman.", False),
    ("curiosity", "Biror narsaning sababini bilishga intilaman.", False),
    ("curiosity", "Yangi ma’lumotni eshitsam, uni tekshirib ko‘rishni yoqtiraman.", False),
    ("reliability", "Biror ishni boshlashdan oldin kerakli narsalarni tayyorlayman.", False),
    ("reliability", "Vazifalarimni muhimligiga qarab tartiblayman.", False),
    ("reliability", "Boshlagan vazifamni tugatish uchun vaqt ajrataman.", False),
    ("sociability", "Boshqalar bilan hamkorlikda ish qilish menga yoqadi.", False),
    ("sociability", "Yangi guruhda avval tinglab, keyin suhbatga qo‘shilaman.", False),
    ("sociability", "Ko‘pincha boshqalar bilan gaplashishdan ko‘ra yolg‘iz qolishni tanlayman.", True),
    ("kindness", "Kelishmovchilikda boshqa odamning nuqtai nazarini tushunishga harakat qilaman.", False),
    ("kindness", "Nizoni tinch yo‘l bilan hal qilishga intilaman.", False),
    ("kindness", "Boshqa odamning mehnatini qadrlashimni bildirishga harakat qilaman.", False),
    ("kindness", "Boshqalarning muvaffaqiyatidan chin dildan xursand bo‘la olaman.", False),
    ("calmness", "Kutilmagan o‘zgarishda moslashish yo‘lini izlayman.", False),
    ("calmness", "Xatodan keyin undan nimani o‘rganishim mumkinligini o‘ylayman.", False),
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
    "Hislarimni ishonchli inson bilan bo‘lisha oldim.",
    "Qiyin vazifani kichik qadamlarga ajratdim.",
    "Uddalagan ishimni o‘zim e’tirof etdim.",
    "O‘zim uchun foydali yoki yoqimli mashg‘ulotga vaqt topdim.",
    "Kerak bo‘lganda dam olishga ruxsat berdim.",
    "Charchaganimdan keyin tiklanish uchun vaqt ajratdim.",
    "Men uchun muhim bo‘lgan ishga vaqt ajratdim.",
    "Muammo chiqqanda birinchi kichik qadamni belgiladim.",
    "Yaqinlarim bilan iliq va hurmatli muloqot qildim.",
    "Vazifalarni rejalaganda o‘z imkoniyatlarimni hisobga oldim.",
    "O‘zimni boshqalar bilan solishtirishni kamaytirishga harakat qildim.",
    "Yordam so‘rash mumkinligini eslab, kerak bo‘lsa murojaat qildim.",
    "Tanaffus yoki yengil harakat uchun vaqt ajratdim.",
    "Uyqu va dam olishimga e’tibor berdim.",
    "Qiyin hislarim haqida gaplashishim yoki yozishim mumkinligini esladim.",
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
