"""Add password reset tokens table and token_version to users

Revision ID: 0009_password_reset
Revises: 0008_search_discovery
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_password_reset"
down_revision = "0008_search_discovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Add token_version to users for session invalidation on password reset if not present
    users_columns = [c["name"] for c in inspector.get_columns("users")]
    if "token_version" not in users_columns:
        op.add_column(
            "users",
            sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
        )

    # Create password_reset_tokens table if not present
    tables = inspector.get_table_names()
    if "password_reset_tokens" not in tables:
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True, index=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tables = inspector.get_table_names()
    if "password_reset_tokens" in tables:
        op.drop_table("password_reset_tokens")

    users_columns = [c["name"] for c in inspector.get_columns("users")]
    if "token_version" in users_columns:
        op.drop_column("users", "token_version")
