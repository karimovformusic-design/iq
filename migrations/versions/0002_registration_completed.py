"""Track whether a user completed the full onboarding form."""

from alembic import op
import sqlalchemy as sa

revision = "0002_registration_completed"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "registration_completed",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "registration_completed")
