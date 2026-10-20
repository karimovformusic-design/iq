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
    factor_maxima: dict[str, list[int]] = defaultdict(list)
    for question, answer in zip(questions, answer_indexes, strict=True):
        if question.factor:
            maximum_for_question = max(0, len(question.options_uz) - 1)
            value = maximum_for_question - answer if question.reverse_scored else answer
            factor_scores[question.factor].append(value)
            factor_maxima[question.factor].append(maximum_for_question)

    if category_slug == "personality":
        factors_uz = {
            "curiosity": "Qiziquvchanlik va yangi g‘oyalar",
            "reliability": "Mas’uliyat va izchillik",
            "sociability": "Muloqotga ochiqlik",
            "kindness": "Hamkorlik va hamdardlik",
            "calmness": "Hissiy muvozanat va moslashuv",
        }
        normalized = {
            key: round(sum(values) * 100 / sum(factor_maxima[key]))
            for key, values in factor_scores.items()
            if values and sum(factor_maxima[key]) > 0
        }
        profiles = {
            "curiosity": {
                "high": "Yangi mavzu yoki g‘oyaga duch kelganda, uning sababini bilish va boshqa tomondan ham ko‘rish sizga qiziq bo‘lishi mumkin. Bu odat o‘rganishni faol qiladi: siz faqat javobni emas, uning qanday ishlashini ham tushunishga intilasiz.",
                "mid": "Tanish va yangi mavzular orasida muvozanat ko‘rinadi. Zarur yoki qiziqarli tuyulgan paytda yangi fikrlarni sinab ko‘rasiz, boshqa paytda esa sinalgan usullarga tayanishingiz mumkin.",
                "low": "Sizga tanish yo‘nalishlarni chuqurroq o‘rganish va amalda sinalgan usullar bilan ishlash qulayroq bo‘lishi mumkin. Bu barqaror bilim va puxta tajriba to‘plashga mos yondashuv; yangilikni esa o‘zingizga qulay sur’atda tanlaysiz.",
            },
            "reliability": {
                "high": "Reja tuzish, muddatni yodda tutish va ishni oxiriga yetkazish javoblaringizda ancha ko‘rinadi. Atrofdagilar sizga topshiriqni ishonib topshirishi mumkin; shu bilan birga, reja o‘zgarganda o‘zingizga moslashish uchun ham joy qoldirish foydali.",
                "mid": "Aniq maqsad va tushunarli bosqichlar bo‘lsa, ishni izchil olib borishingiz mumkin. Vazifalar ko‘paygan paytda ustuvorliklarni qayta belgilash yoki ishni kichik qismlarga ajratish sizga yengillik berishi mumkin.",
                "low": "Erkinroq va vaziyatga moslashib ishlash sizga tabiiyroq bo‘lishi mumkin. Bu tez o‘zgaradigan sharoitlarda asqatadi; muhim vazifalarda kichik eslatma yoki bitta yaqin muddat belgilash esa fikrni jamlashga yordam berishi mumkin.",
            },
            "sociability": {
                "high": "Guruhdagi suhbatga qo‘shilish va fikr almashish siz uchun qulay ko‘rinadi. Savol berish va muhokamaga hissa qo‘shish orqali jamoada harakat paydo qilishingiz mumkin; boshqalarga ham so‘z navbatini berish bu kuchli tomonni yanada muvozanatlaydi.",
                "mid": "Muloqotga tayyorligingiz vaziyat, odamlar va mavzuga qarab o‘zgarishi mumkin. Ba’zi davralarda faolroq bo‘lasiz, boshqalarida esa avval kuzatib, keyin fikr bildirishni ma’qul ko‘rishingiz mumkin.",
                "low": "Sokinroq muloqot uslubi yoki suhbatga kirishishdan oldin vaqt olish sizga mos bo‘lishi mumkin. Bu diqqat bilan tinglash va mazmunli, yakkama-yakka suhbatlarga imkon beradi; kamgaplik muloqot qobiliyati yo‘qligini anglatmaydi.",
            },
            "kindness": {
                "high": "Boshqa odamning nuqtai nazarini tushunishga urinish va hurmat bilan gaplashish javoblaringizda yaqqol seziladi. Bu kelishuv va hamkorlikni osonlashtiradi; o‘z ehtiyojlaringizni ham xuddi shunday e’tibor bilan ifodalash muvozanatni saqlaydi.",
                "mid": "Hamkorlik va o‘z qarashingizni himoya qilish orasida vaziyatga mos muvozanat ko‘rinadi. Ba’zan tinglashga, ba’zan esa aniq fikr bildirishga ko‘proq e’tibor berishingiz mumkin.",
                "low": "Siz ko‘pincha masalaga bevosita va natijaga yo‘naltirilgan tarzda qarashingiz mumkin. Bu qaror qabul qilishda aniqlik beradi; boshqa odamning fikrini qisqacha qaytarib aytib ko‘rish esa o‘zaro tushunishni kuchaytirishi mumkin.",
            },
            "calmness": {
                "high": "Kutilmagan vaziyatlarda to‘xtab, keyingi qadamni o‘ylab olish va o‘zgarishga moslashish sizga nisbatan oson bo‘lishi mumkin. Xato yoki hayajon paytida o‘zingizga tiklanish uchun vaqt berishingiz ham ichki muvozanatni qo‘llab-quvvatlaydi.",
                "mid": "Tinch va tanish vaziyatlarda o‘zingizni boshqarish osonroq, bosim ko‘payganda esa qisqa tanaffus kerak bo‘lishi mumkin. Bu ko‘pchilikda uchraydigan o‘zgaruvchanlik; vaziyatni bir qadamga kichraytirib ko‘rish keyingi harakatni ravshanlashtiradi.",
                "low": "Kuchli hayajon yoki kutilmagan o‘zgarishlar sizga ko‘proq ta’sir qilishi mumkin. Bu kamchilik belgisi emas; hisni nomlash, nafasni rostlash yoki avval eng yaqin bitta ishni tanlash o‘zingizni qayta jamlashga yordam berishi mumkin.",
            },
        }

        def band_for(value: int) -> str:
            return "high" if value >= 70 else "mid" if value >= 40 else "low"

        ordered = sorted(normalized.items(), key=lambda item: item[1], reverse=True)
        top_labels = [factors_uz.get(key, key) for key, _value in ordered[:2]]
        top_line = (
            f"Javoblaringizda nisbatan ko‘proq ko‘ringan ikki yo‘nalish: "
            f"{' va '.join(top_labels)}."
            if top_labels
            else "Hozircha yetarli javob asosida profil yo‘nalishlarini ajratib bo‘lmadi."
        )
        dimension_lines = []
        for key, value in ordered:
            label = factors_uz.get(key, key.replace("_", " ").title())
            profile = profiles.get(key, {}).get(band_for(value), "")
            dimension_lines.append(f"• {label} — {value}/100\n  {profile}")

        if ordered:
            lowest_key, lowest_value = min(normalized.items(), key=lambda item: item[1])
            lowest_label = factors_uz.get(lowest_key, lowest_key)
            growth_line = (
                f"Ko‘rsatkichlar ichida {lowest_label} hozir nisbatan pastroq chiqdi. "
                "Buni kamchilik deb emas, o‘zingizga boshqa tomondan qarash uchun bir imkoniyat deb ko‘ring: "
                "qaysi vaziyatlarda bu xususiyat ko‘proq namoyon bo‘lishini kuzatishingiz mumkin."
            )
        else:
            lowest_value = 0
            growth_line = "Har bir yo‘nalish bo‘yicha javoblar ko‘paygani sari profil mazmunliroq bo‘ladi."

        report = (
            f"🌿 {TEST_NAMES['personality']} — shaxsiy portretingiz\n\n"
            "Quyidagi tahlil javoblaringizda qayd etilgan odatiy afzalliklarni jamlaydi. "
            "U sizni bitta qat’iy ta’rifga solmaydi: odamning xulqi vaziyat, tajriba va kayfiyatga qarab o‘zgarishi tabiiy.\n\n"
            f"✨ Qisqa ko‘rinish\n{top_line} "
            "Bu yo‘nalishlar yangi narsani o‘rganish, ishni tashkil etish, muloqot va kundalik qarorlarda "
            "qanday uslub sizga yaqinligini anglashga yordam beradigan kuzatuvlardir.\n\n"
            "🧭 Besh yo‘nalish bo‘yicha tahlil\n"
            + "\n\n".join(dimension_lines)
            + "\n\n🌱 O‘zingizga mos tarzda foydalanish\n"
            "Nisbatan yuqori ko‘rsatkichlarni tayanch sifatida ishlating: ular qaysi vaziyatlarda o‘zingizni "
            "erkin va samarali his qilishingizni ko‘rsatishi mumkin. Pastroq raqam esa yomon sifat yoki "
            "o‘zgarmas xususiyat emas — u boshqa sharoit, ko‘nikma yoki dam olish sizga qanday ta’sir qilishini "
            "o‘ylab ko‘rish uchun nuqta, xolos.\n\n"
            f"{growth_line}\n\n"
            "🪞 O‘zingizga berib ko‘rishingiz mumkin bo‘lgan savollar:\n"
            "• Qaysi ish yoki muhitda kuchli tomonlarim eng tabiiy ko‘rinadi?\n"
            "• Qachon reja menga yordam beradi, qachon esa erkinlik kerak bo‘ladi?\n"
            "• Keyingi haftada qaysi kichik odatni sinab ko‘rish menga mos keladi?\n\n"
            "Bu norasmiy, o‘zini anglashga mo‘ljallangan so‘rovnoma. Foizlar faqat shu savollarga bergan "
            "javoblaringizning yo‘nalish ko‘rsatkichidir; ular boshqa odamlar bilan taqqoslash, klinik baho "
            "yoki o‘zgarmas shaxsiyat yorlig‘i emas."
        )
        score = round(sum(normalized.values()) / len(normalized)) if normalized else 0
        return score, 100, report

    if category_slug == "wellbeing":
        wellbeing_labels = {
            "energy": "Quvvat va dam olish",
            "interest": "Qiziqish va yoqimli mashg‘ulotlar",
            "self_awareness": "Hissiyotlarni payqash va o‘ziga mehr",
            "daily_routine": "Kundalik ishlarni uddalash",
            "connection": "Aloqa va yaqinlik",
        }
        normalized = {
            key: round(sum(values) * 100 / sum(factor_maxima[key]))
            for key, values in factor_scores.items()
            if values and sum(factor_maxima[key]) > 0
        }
        total = sum(sum(values) for values in factor_scores.values())
        maximum = sum(sum(values) for values in factor_maxima.values())
        percent = round(total * 100 / maximum) if maximum else 0
        if percent >= 75:
            summary = (
                "Javoblaringiz so‘nggi ikki haftada bir nechta kundalik tayanch tez-tez bo‘lganini ko‘rsatadi. "
                "Dam olish, qiziqish, kundalik ishlar yoki yaqinlar bilan aloqa kabi jihatlar sizga kuch beradigan "
                "manbalar bo‘lishi mumkin. Bu har kuni bir xil o‘tganini anglatmaydi — yaxshi davrlarda ham "
                "charchoq yoki murakkab lahzalar bo‘lishi tabiiy."
            )
        elif percent >= 50:
            summary = (
                "Javoblaringiz aralash manzarani ko‘rsatadi: ayrim tayanchlar mavjud, boshqalari esa kun yoki "
                "vaziyatga qarab o‘zgarib turgan bo‘lishi mumkin. Bu holatni bitta umumiy bahoga aylantirishdan "
                "ko‘ra, qaysi kunlarda quvvat, qiziqish yoki xotirjamlik ko‘proq bo‘lganini payqash foydaliroq."
            )
        else:
            summary = (
                "Javoblaringiz so‘nggi ikki haftada kundalik quvvat, qiziqish yoki muvozanatni saqlash oson "
                "bo‘lmagan paytlar ko‘proq bo‘lganini ko‘rsatishi mumkin. Bu sizning qadringiz yoki imkoniyatingiz "
                "haqidagi hukm emas; u faqat shu davrda savollarga qanday javob berganingizni aks ettiradi. "
                "Charchoq va bandlik ham ayrim javoblarga ta’sir qilishi mumkin."
            )

        dimension_texts = {
            "energy": {
                "high": "Dam olish va kunduzgi quvvat javoblaringizda ko‘proq ijobiy ko‘ringan. Bu tartib sizga nimalar kuch berishini payqash uchun yaxshi tayanch bo‘lishi mumkin.",
                "mid": "Quvvat va dam olish ayrim paytlar yetarli, ayrim paytlar esa o‘zgaruvchan bo‘lgan ko‘rinadi. Uyqu, tanaffus va kun tartibi qaysi kunlarda farq qilganini kuzatib ko‘rishingiz mumkin.",
                "low": "Bu davrda dam olish yoki quvvatni tiklash kamroq sezilgan bo‘lishi mumkin. Buni o‘zingizni ayblash uchun emas, kun davomida qaysi paytlar yengilroq yoki og‘irroq kechishini anglash uchun foydalaning.",
            },
            "interest": {
                "high": "Qiziqarli va yoqimli mashg‘ulotlar javoblaringizda tez-tez uchraydi. Kichik zavq manbalari ham kunning umumiy ohangini o‘zgartirishi mumkin.",
                "mid": "Qiziqish yoki yoqimli lahzalar bo‘lgan, ammo har kuni bir xil darajada emas. Sizga haqiqatan yoqadigan mashg‘ulotlar qaysi paytda ko‘proq joy olganini eslash mumkin.",
                "low": "Yoqimli mashg‘ulot va qiziqish bu davrda kamroq joy olgan bo‘lishi mumkin. Bu qiziqish yo‘qolgan degani emas; bandlik, charchoq yoki imkoniyat kamligi ham ta’sir qilishi mumkin.",
            },
            "self_awareness": {
                "high": "Hislaringizni payqash va o‘zingizga muloyim munosabatda bo‘lish javoblaringizda ko‘proq ko‘rinadi. Bu o‘z holatingizni tushunishga va ehtiyojlaringizni aniqroq sezishga xizmat qilishi mumkin.",
                "mid": "Ba’zi paytlar hislaringizga e’tibor bergansiz, boshqa paytlarda esa kundalik shoshilish bunga vaqt qoldirmagan bo‘lishi mumkin. Qisqa tanaffus o‘zingizni qanday his qilayotganingizni sezishga imkon beradi.",
                "low": "O‘z hislaringizni payqash yoki o‘zingizga muloyim bo‘lish bu davrda kamroq uchragan bo‘lishi mumkin. Bu o‘zgarmas xususiyat emas; keyingi safar hisni bir so‘z bilan nomlashning o‘zi ham foydali kuzatuv bo‘ladi.",
            },
            "daily_routine": {
                "high": "Kundalik vazifalar va kichik qadamlarni belgilash javoblaringizda ko‘proq uddalangan jihatlar sifatida ko‘rinadi. Bu tartib sizga band kunlarda ham yo‘nalishni saqlashga yordam berishi mumkin.",
                "mid": "Ayrim vazifalar bajarilgan, boshqalari esa ko‘proq kuch talab qilgan bo‘lishi mumkin. Bir kunda hamma ishni bitirish shart emas; muhim qadamni tanlashning o‘zi yetarli natija bo‘la oladi.",
                "low": "Oddiy vazifalarni bajarish yoki muvozanatni saqlash bu davrda ko‘proq kuch olgan bo‘lishi mumkin. Buni shaxsiy qobiliyatga hukm deb emas, vazifalarni kichik qismlarga ajratib ko‘rish uchun eslatma deb qabul qiling.",
            },
            "connection": {
                "high": "Yaqinlik va suhbat javoblaringizda ko‘proq ijobiy tajriba sifatida ko‘rinadi. Samimiy suhbat, birga o‘tkazilgan vaqt yoki jamoaga daxldorlik sizga yoqimli ta’sir qilishi mumkin.",
                "mid": "Aloqa va yaqinlik ayrim paytlar bo‘lgan, ammo doimiy bo‘lmasligi mumkin. Sizga qulay bo‘lgan suhbat turi — qisqa xabar, birga sayr yoki sokin suhbat — qaysi ekanini payqash mumkin.",
                "low": "Yaqinlik yoki suhbat bu davrda kamroq sezilgan bo‘lishi mumkin. Bu sizning munosabat qurish qobiliyatingiz haqida xulosa bermaydi; vaqt, masofa va bandlik ham bunday javoblarga ta’sir qiladi.",
            },
        }

        def wellbeing_band(value: int) -> str:
            return "high" if value >= 75 else "mid" if value >= 50 else "low"

        dimension_lines = []
        for key, value in sorted(normalized.items(), key=lambda item: item[1], reverse=True):
            label = wellbeing_labels.get(key, key.replace("_", " ").title())
            details = dimension_texts.get(key, {}).get(wellbeing_band(value), "")
            dimension_lines.append(f"• {label} — {value}/100\n  {details}")
        lowest_key = min(normalized, key=normalized.get) if normalized else None
        next_steps = {
            "energy": "Kun davomida qisqa tanaffus yoki odatdagi dam olish vaqti sizga qanday ta’sir qilishini kuzating.",
            "interest": "O‘zingizga yoqadigan kichik mashg‘ulot uchun 10 daqiqalik vaqt ajratib, undan keyingi kayfiyatni payqang.",
            "self_awareness": "Kun oxirida hislaringizni bir-ikki so‘z bilan yozib ko‘ring; bu o‘zingizni tushunishga yordam beradigan kichik mashq.",
            "daily_routine": "Bitta vazifani eng kichik bajariladigan qadamga ajratib, faqat o‘sha qadamni rejalashtiring.",
            "connection": "Sizga qulay bo‘lgan bir suhbat yoki birga o‘tkaziladigan qisqa vaqtni rejalashtirib ko‘ring.",
        }
        next_step = (
            next_steps.get(lowest_key, "O‘zingizga mos bitta kichik odatni tanlab, uning ta’sirini kuzating.")
            if lowest_key
            else "Keyingi safar javoblaringiz ko‘payganda, alohida yo‘nalishlarni ham ko‘rib chiqing."
        )
        report = (
            f"💛 {TEST_NAMES['wellbeing']} — so‘nggi ikki haftadagi holatingiz\n\n"
            f"Umumiy indeks: {percent}/100.\n"
            "Bu raqam savollarga qay darajada tez-tez ijobiy javob berganingizni jamlaydi; "
            "u boshqa odamlar bilan reyting yoki hayotingizning umumiy bahosi emas.\n\n"
            f"{summary}\n\n"
            "🌤 Kundalik hayotning besh yo‘nalishi\n"
            + "\n\n".join(dimension_lines)
            + "\n\n🌱 Natijani o‘zingiz uchun ishlatish\n"
            "Yuqoriroq ko‘rsatkich chiqqan yo‘nalishlar so‘nggi paytda sizga tayanch bo‘lgan odat yoki "
            "sharoitlarni eslatishi mumkin. Pastroq ko‘rsatkich esa kamchilik emas: u shu ikki haftada "
            "qaysi tajriba kamroq bo‘lganini ko‘rsatadi, xolos. Bitta banddagi javob ham butun hayotingizni "
            "ta’riflamaydi, va keyingi haftalarda natija boshqacha chiqishi mumkin.\n\n"
            f"🪴 Kichik tajriba: {next_step}\n\n"
            "O‘zingizga berib ko‘ring:\n"
            "• Qaysi paytda kunim biroz yengilroq yoki yoqimliroq bo‘ldi?\n"
            "• Menga quvvat bergan odat yoki vaziyat bormi?\n"
            "• Ertaga o‘zim uchun qaysi kichik, bajarilishi oson ishni tanlayman?\n\n"
            "Bu so‘rovnoma o‘zini kuzatish uchun mo‘ljallangan va tashxis emas. Natija faqat so‘nggi ikki "
            "haftadagi javoblaringizga asoslanadi."
        )
        return total, maximum, report

    raise ValueError("Unknown test category.")


def question_payload(question: Question) -> dict[str, Any]:
    return {
        "id": question.id,
        "prompt": question.prompt_uz,
        "options": question.options_uz,
    }
