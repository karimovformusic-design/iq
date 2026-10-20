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


IQ_QUESTION_BANK_SIZE = 100
_IQ_AGE_LEVEL = {"7-12": 0, "13-17": 1, "18-30": 2, "31-50": 3, "51-70": 4}


def _question_choices(answer: str | int, distractors: list[str | int], salt: int) -> tuple[list[str], int]:
    choices = [str(answer)]
    for item in distractors:
        value = str(item)
        if value not in choices:
            choices.append(value)
        if len(choices) == 4:
            break
    fallback = 1
    while len(choices) < 4:
        value = str(int(answer) + fallback) if str(answer).lstrip("-").isdigit() else f"{answer} {fallback}"
        if value not in choices:
            choices.append(value)
        fallback += 1
    rotation = salt % 4
    return choices[rotation:] + choices[:rotation], (4 - rotation) % 4


def _iq_questions(age_band: str) -> list[SeedQuestion]:
    level = _IQ_AGE_LEVEL[age_band]
    items: list[tuple[str, str | int, list[str | int]]] = []

    for index in range(20):
        start = 5 + level * 3 + index * 2
        first_difference = 2 + level + index % 4
        second_difference = 1 + index % 3
        third_difference = 1 + index % 2
        sequence = [start]
        current_first = first_difference
        current_second = second_difference
        for _ in range(5):
            sequence.append(sequence[-1] + current_first)
            current_first += current_second
            current_second += third_difference
        answer = sequence[-1] + current_first
        items.append(
            (
                f"Qatorning farqlar jadvalini tahlil qilib, keyingi sonni toping: "
                f"{', '.join(map(str, sequence))}, ?",
                answer,
                [answer + third_difference, answer - second_difference, answer + first_difference],
            )
        )

    for index in range(20):
        first_multiplier = 2 + index % 2
        second_multiplier = 2 + (index + 1) % 2
        addition = 1 + level + index % 5
        subtraction = 1 + level + index % 4
        value = 2 + level + index % 3
        sequence = [value]
        for operation in range(5):
            if operation % 2 == 0:
                value = value * first_multiplier + addition
            else:
                value = value * second_multiplier - subtraction
            sequence.append(value)
        answer = value * first_multiplier + addition
        items.append(
            (
                f"Sonlar orasidagi ikki xil amal navbatma-navbat qo‘llangan. "
                f"Keyingi sonni toping: {', '.join(map(str, sequence))}, ?",
                answer,
                [answer + addition, answer - subtraction, answer * first_multiplier],
            )
        )

    for index in range(20):
        start = 3 + level * 3 + index * 2
        difference = 2 + level + index % 5
        difference_growth = 1 + index % 3
        sequence = [start]
        current_difference = difference
        for _ in range(4):
            sequence.append(sequence[-1] + current_difference)
            current_difference += difference_growth
        answer = sequence[-1] + current_difference
        items.append(
            (
                f"Sonlar orasidagi farqlar ham qonuniyat bilan o‘zgaradi. "
                f"Keyingi sonni toping: {', '.join(map(str, sequence))}, ?",
                answer,
                [answer + difference_growth, answer - difference_growth, answer + difference],
            )
        )

    for index in range(15):
        even_start = 2 + level + index % 4
        odd_start = even_start + 2 + index % 3
        even_growth = 1 + index % 2
        odd_growth = 1 + (index + 1) % 3
        current = 8 + level * 3 + index * 2
        sequence = [current]
        for transition in range(6):
            if transition % 2 == 0:
                current += even_start + (transition // 2) * even_growth
            else:
                current += odd_start + (transition // 2) * odd_growth
            sequence.append(current)
        answer = sequence[-1] + even_start + 3 * even_growth
        items.append(
            (
                f"Hadlar orasidagi farqlarning toq va juft o‘rinlari alohida o‘sadi. "
                f"Keyingi sonni toping: {', '.join(map(str, sequence))}, ?",
                answer,
                [answer + even_growth, answer - odd_start, answer + odd_growth],
            )
        )

    for index in range(10):
        even_start = 2 + level * 2 + index * 2
        odd_start = 5 + level + index
        even_difference = 3 + level + index % 4
        odd_difference = 4 + level + index % 5
        even_growth = 1 + index % 3
        odd_growth = 2 + index % 2

        def quadratic_term(start: int, difference: int, growth: int, position: int) -> int:
            return start + position * difference + position * (position - 1) // 2 * growth

        sequence = [
            quadratic_term(even_start, even_difference, even_growth, position // 2)
            if position % 2 == 0
            else quadratic_term(odd_start, odd_difference, odd_growth, position // 2)
            for position in range(6)
        ]
        answer = quadratic_term(even_start, even_difference, even_growth, 3)
        items.append(
            (
                f"Bu qatorda ikkita mustaqil qonuniyat navbatma-navbat berilgan; "
                f"har ikkisining farqlari ham o‘zgaradi. Keyingi sonni toping: "
                f"{', '.join(map(str, sequence))}, ?",
                answer,
                [answer + even_growth, answer - even_difference, answer + odd_difference],
            )
        )

    symbols = ("A", "B", "C", "D", "E", "F")
    for index in range(5):
        a, b, c = (symbols[(index * 2 + level + offset) % len(symbols)] for offset in range(3))
        logic_type = index % 5
        if logic_type == 0:
            prompt = (
                f"Barcha {a} elementlari {b} toifasiga kiradi. Hech bir {b} "
                f"elementi {c} toifasiga kirmaydi. Qaysi xulosa albatta to‘g‘ri?"
            )
            answer = f"Hech bir {a} elementi {c} toifasiga kirmaydi."
            distractors = [
                f"Barcha {c} elementlari {a} toifasiga kiradi.",
                f"Ayrim {a} elementlari {c} toifasiga kiradi.",
                f"Barcha {b} elementlari {a} toifasiga kiradi.",
            ]
        elif logic_type == 1:
            prompt = f"Barcha {a} elementlari {b} toifasida. Barcha {b} elementlari {c} toifasida. Qaysi xulosa kelib chiqadi?"
            answer = f"Barcha {a} elementlari {c} toifasida."
            distractors = [
                f"Barcha {c} elementlari {a} toifasida.",
                f"Hech bir {a} elementi {c} toifasida emas.",
                f"Barcha {b} elementlari {a} toifasida.",
            ]
        elif logic_type == 2:
            prompt = f"Ayrim {a} elementlari {b} toifasida. Barcha {b} elementlari {c} toifasida. Qaysi xulosa albatta to‘g‘ri?"
            answer = f"Ayrim {a} elementlari {c} toifasida."
            distractors = [
                f"Barcha {a} elementlari {c} toifasida.",
                f"Hech bir {a} elementi {c} toifasida emas.",
                f"Barcha {c} elementlari {a} toifasida.",
            ]
        elif logic_type == 3:
            prompt = f"Hech bir {a} elementi {b} toifasida emas. Ayrim {c} elementlari {a} toifasida. Nima aniq?"
            answer = f"Ayrim {c} elementlari {b} toifasida emas."
            distractors = [
                f"Barcha {c} elementlari {b} toifasida.",
                f"Ayrim {a} elementlari {b} toifasida.",
                f"Hech bir {c} elementi {a} toifasida emas.",
            ]
        else:
            prompt = f"Barcha {a} elementlari {b} toifasida. Ayrim {c} elementlari {a} toifasida. Qaysi xulosa kelib chiqadi?"
            answer = f"Ayrim {c} elementlari {b} toifasida."
            distractors = [
                f"Barcha {c} elementlari {b} toifasida.",
                f"Hech bir {c} elementi {b} toifasida emas.",
                f"Barcha {b} elementlari {a} toifasida.",
            ]
        items.append((prompt, answer, distractors))

    logic_labels = (("P", "Q", "R"), ("R", "S", "T"), ("X", "Y", "Z"), ("K", "M", "N"), ("T", "V", "W"))
    for index in range(5):
        left, middle, right = logic_labels[(index + level) % len(logic_labels)]
        if index % 2 == 0:
            prompt = (
                f"Agar {left} rost bo‘lsa, {middle} rost bo‘ladi. "
                f"Agar {middle} rost bo‘lsa, {right} rost bo‘ladi. {right} yolg‘on. "
                f"Qaysi xulosa mantiqan kelib chiqadi?"
            )
            answer = f"{left} yolg‘on."
            distractors = [
                f"{left} rost.",
                f"{right} rost.",
                f"{left} va {right} rost.",
            ]
        else:
            prompt = (
                f"Agar {left} rost bo‘lsa, {middle} rost. Agar {right} rost bo‘lsa, "
                f"{left} ham rost. {middle} yolg‘on. {right} haqida nima aniq?"
            )
            answer = f"{right} yolg‘on."
            distractors = [
                f"{right} rost.",
                f"{left} rost.",
                f"{middle} rost.",
            ]
        items.append((prompt, answer, distractors))

    matrix_rules = [
        lambda first, second: first * first + second,
        lambda first, second: first * second + first,
        lambda first, second: second * second - first,
        lambda first, second: first * (second + 2) - second,
        lambda first, second: first * second + second * second,
    ]
    for index in range(5):
        rule = matrix_rules[index]
        first = 2 + level + index
        second = first + 2
        rows = [
            (first + row, second + row, rule(first + row, second + row))
            for row in range(2)
        ]
        answer = rule(first + 2, second + 2)
        items.append(
            (
                "Jadvaldagi har bir qatorda bir xil yashirin qoida ishlaydi. "
                f"Uchinchi qatordagi natijani toping: {rows[0][0]}, {rows[0][1]}, {rows[0][2]}; "
                f"{rows[1][0]}, {rows[1][1]}, {rows[1][2]}; "
                f"{first + 2}, {second + 2}, ?",
                answer,
                [answer + level + 1, answer - first, answer + second],
            )
        )

    questions = []
    for number, (prompt, answer, distractors) in enumerate(items, start=1):
        options, correct_index = _question_choices(answer, distractors, number + level)
        if number <= 20:
            factor = "cubic_differences"
        elif number <= 40:
            factor = "alternating_operations"
        elif number <= 60:
            factor = "quadratic_differences"
        elif number <= 75:
            factor = "alternating_difference_streams"
        elif number <= 85:
            factor = "interleaved_quadratic_streams"
        elif number <= 90:
            factor = "syllogistic_deduction"
        elif number <= 95:
            factor = "conditional_chains"
        else:
            factor = "numeric_matrices"
        questions.append(
            SeedQuestion(
                question_key=f"iq:{age_band}:v2:{number}",
                category_slug="iq",
                age_band=age_band,
                prompt_uz=prompt,
                options_uz=options,
                correct_index=correct_index,
                factor=factor,
            )
        )
    return questions


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
        "description_uz": "Har safar 100 original topshiriqdan 20 tasi tanlanadigan murakkab mantiq mashqi; rasmiy IQ bahosi emas.",
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
