"""Initial MINDORA bot schema."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def _json_type():
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), server_default="", nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("account_status", sa.String(length=20), server_default="active", nullable=False),
        sa.CheckConstraint("age IS NULL OR (age >= 7 AND age <= 70)", name="ck_users_age_range"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_last_active_at", "users", ["last_active_at"])
    op.create_index("ix_users_username_lower", "users", [sa.text("lower(username)")])

    op.create_table(
        "test_categories",
        sa.Column("slug", sa.String(length=32), nullable=False),
        sa.Column("name_uz", sa.String(length=120), nullable=False),
        sa.Column("description_uz", sa.Text(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("slug"),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("question_key", sa.String(length=100), nullable=False),
        sa.Column("category_slug", sa.String(length=32), nullable=False),
        sa.Column("age_band", sa.String(length=8), nullable=False),
        sa.Column("prompt_uz", sa.Text(), nullable=False),
        sa.Column("options_uz", _json_type(), nullable=False),
        sa.Column("correct_index", sa.Integer(), nullable=True),
        sa.Column("factor", sa.String(length=32), nullable=True),
        sa.Column("reverse_scored", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["category_slug"], ["test_categories.slug"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("question_key", name="uq_questions_question_key"),
    )
    op.create_index(
        "ix_questions_category_age_active",
        "questions",
        ["category_slug", "age_band", "is_active"],
    )

    op.create_table(
        "test_attempts",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("category_slug", sa.String(length=32), nullable=False),
        sa.Column("age_at_test", sa.Integer(), nullable=False),
        sa.Column("age_band", sa.String(length=8), nullable=False),
        sa.Column("question_order", _json_type(), nullable=False),
        sa.Column("answered_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="in_progress", nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("max_score", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["category_slug"], ["test_categories.slug"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_test_attempts_user_status", "test_attempts", ["user_id", "status"])
    op.create_index("ix_test_attempts_category_status", "test_attempts", ["category_slug", "status"])

    op.create_table(
        "test_answers",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("question_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("answer_index", sa.Integer(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("score_value", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["test_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["question_id"], ["questions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "question_id", name="uq_test_answers_attempt_question"),
    )
    op.create_index("ix_test_answers_attempt", "test_answers", ["attempt_id"])

    op.create_table(
        "assessment_reports",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("attempt_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("report_text", sa.Text(), nullable=False),
        sa.Column("released_to_user", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["test_attempts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id"),
    )
    op.create_index("ix_assessment_reports_user_id", "assessment_reports", ["user_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("report_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("amount_uzs", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("receipt_file_id", sa.Text(), nullable=False),
        sa.Column("receipt_file_unique_id", sa.String(length=200), nullable=False),
        sa.Column("receipt_kind", sa.String(length=16), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("rejection_reason", sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(["report_id"], ["assessment_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receipt_file_unique_id"),
    )
    op.create_index("ix_payments_status_submitted", "payments", ["status", "submitted_at"])
    op.create_index("ix_payments_user_id", "payments", ["user_id"])
    op.create_index("ix_payments_report_id", "payments", ["report_id"])
    op.create_index(
        "uq_payments_one_pending_report",
        "payments",
        ["report_id"],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
        sqlite_where=sa.text("status = 'pending'"),
    )

    op.create_table(
        "admin_actions",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("actor_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=True),
        sa.Column("metadata_json", _json_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_actions_actor_telegram_id", "admin_actions", ["actor_telegram_id"])
    op.create_index("ix_admin_actions_target_created", "admin_actions", ["target_user_id", "created_at"])

    op.create_table(
        "bot_settings",
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("value_json", _json_type(), nullable=False),
        sa.Column("updated_by_telegram_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("setting_key"),
    )

    op.create_table(
        "broadcast_jobs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("status", sa.String(length=20), server_default="queued", nullable=False),
        sa.Column("audience", sa.String(length=20), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("photo_file_id", sa.Text(), nullable=True),
        sa.Column("entities_json", _json_type(), nullable=True),
        sa.Column("caption_entities_json", _json_type(), nullable=True),
        sa.Column("initiated_by_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_broadcast_jobs_status_created", "broadcast_jobs", ["status", "created_at"])

    op.create_table(
        "broadcast_recipients",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result_code", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["broadcast_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "user_id", name="uq_broadcast_recipient_job_user"),
    )
    op.create_index(
        "ix_broadcast_recipients_job_status",
        "broadcast_recipients",
        ["job_id", "status"],
    )
    op.create_index(
        "ix_broadcast_recipients_status_next_attempt",
        "broadcast_recipients",
        ["status", "next_attempt_at"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("service_opt_in", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("promotional_opt_in", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("bot_blocked", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "conversation_states",
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("payload", _json_type(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("telegram_id"),
    )


def downgrade() -> None:
    op.drop_table("conversation_states")
    op.drop_table("notification_preferences")
    op.drop_index("ix_broadcast_recipients_status_next_attempt", table_name="broadcast_recipients")
    op.drop_index("ix_broadcast_recipients_job_status", table_name="broadcast_recipients")
    op.drop_table("broadcast_recipients")
    op.drop_index("ix_broadcast_jobs_status_created", table_name="broadcast_jobs")
    op.drop_table("broadcast_jobs")
    op.drop_table("bot_settings")
    op.drop_index("ix_admin_actions_target_created", table_name="admin_actions")
    op.drop_index("ix_admin_actions_actor_telegram_id", table_name="admin_actions")
    op.drop_table("admin_actions")
    op.drop_index("uq_payments_one_pending_report", table_name="payments")
    op.drop_index("ix_payments_report_id", table_name="payments")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_index("ix_payments_status_submitted", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_assessment_reports_user_id", table_name="assessment_reports")
    op.drop_table("assessment_reports")
    op.drop_index("ix_test_answers_attempt", table_name="test_answers")
    op.drop_table("test_answers")
    op.drop_index("ix_test_attempts_category_status", table_name="test_attempts")
    op.drop_index("ix_test_attempts_user_status", table_name="test_attempts")
    op.drop_table("test_attempts")
    op.drop_index("ix_questions_category_age_active", table_name="questions")
    op.drop_table("questions")
    op.drop_table("test_categories")
    op.drop_index("ix_users_username_lower", table_name="users")
    op.drop_index("ix_users_last_active_at", table_name="users")
    op.drop_table("users")
