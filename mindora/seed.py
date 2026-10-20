from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mindora.constants import QUESTION_COUNT_PER_ATTEMPT
from mindora.db import SessionFactory, dispose_engine
from mindora.models import BotSetting, Question, TestCategory
from mindora.seed_data import CATEGORIES, build_question_bank


async def seed_database(session: AsyncSession) -> int:
    dialect = session.get_bind().dialect.name
    insert = pg_insert if dialect == "postgresql" else sqlite_insert

    for category in CATEGORIES:
        statement = insert(TestCategory).values(**category)
        statement = statement.on_conflict_do_nothing(index_elements=["slug"])
        await session.execute(statement)

    questions = [
        {
            "question_key": question.question_key,
            "category_slug": question.category_slug,
            "age_band": question.age_band,
            "prompt_uz": question.prompt_uz,
            "options_uz": question.options_uz,
            "correct_index": question.correct_index,
            "factor": question.factor,
            "reverse_scored": question.reverse_scored,
            "is_active": True,
        }
        for question in build_question_bank()
    ]
    question_keys = [question["question_key"] for question in questions]
    existing_keys = set(
        await session.scalars(
            select(Question.question_key).where(Question.question_key.in_(question_keys))
        )
    )
    statement = insert(Question).values(questions)
    statement = statement.on_conflict_do_update(
        index_elements=["question_key"],
        set_={
            field: getattr(statement.excluded, field)
            for field in (
                "category_slug",
                "age_band",
                "prompt_uz",
                "options_uz",
                "correct_index",
                "factor",
                "reverse_scored",
                "is_active",
            )
        },
    )
    await session.execute(statement)

    settings = [
        {"setting_key": "test_attempt_question_count", "value_json": QUESTION_COUNT_PER_ATTEMPT},
        {"setting_key": "terms_version", "value_json": 1},
    ]
    for setting in settings:
        statement = insert(BotSetting).values(**setting)
        if setting["setting_key"] == "test_attempt_question_count":
            statement = statement.on_conflict_do_update(
                index_elements=["setting_key"],
                set_={"value_json": statement.excluded.value_json},
            )
        else:
            statement = statement.on_conflict_do_nothing(index_elements=["setting_key"])
        await session.execute(statement)
    return len(questions) - len(existing_keys)


async def main() -> None:
    async with SessionFactory() as session, session.begin():
        added = await seed_database(session)
        print(f"Seed complete; inserted {added} new questions.")
    await dispose_engine()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
