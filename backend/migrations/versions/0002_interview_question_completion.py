"""add interview question completion state

Revision ID: 0002_interview_question_completion
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_interview_question_completion"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interview_questions", sa.Column("completed", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("interview_questions", "completed")