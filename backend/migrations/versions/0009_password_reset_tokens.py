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
    # Add token_version to users for session invalidation on password reset
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
    )

    # Create password_reset_tokens table
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
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "token_version")
