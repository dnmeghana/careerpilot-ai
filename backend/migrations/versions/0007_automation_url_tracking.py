"""add current_url and page_title to automation_runs and automation_action_logs

Revision ID: 0007_url_tracking
Revises: 0006_automation
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_url_tracking"
down_revision = "0006_automation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automation_runs", sa.Column("current_url", sa.String(length=2048), nullable=True))
    op.add_column("automation_runs", sa.Column("page_title", sa.String(length=512), nullable=True))
    op.add_column("automation_action_logs", sa.Column("current_url", sa.String(length=2048), nullable=True))
    op.add_column("automation_action_logs", sa.Column("page_title", sa.String(length=512), nullable=True))


def downgrade() -> None:
    op.drop_column("automation_action_logs", "page_title")
    op.drop_column("automation_action_logs", "current_url")
    op.drop_column("automation_runs", "page_title")
    op.drop_column("automation_runs", "current_url")

