"""Store a fingerprint so each newly issued test form is unique."""

from alembic import op
import sqlalchemy as sa


revision = "0003_unique_test_forms"
down_revision = "0002_registration_completed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "test_attempts",
        sa.Column("form_fingerprint", sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint(
        "uq_test_attempts_unique_form",
        "test_attempts",
        ["category_slug", "form_fingerprint"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_test_attempts_unique_form",
        "test_attempts",
        type_="unique",
    )
    op.drop_column("test_attempts", "form_fingerprint")
