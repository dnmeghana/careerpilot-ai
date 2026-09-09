"""add mock interview question details

Revision ID: 0003_mock_interview_answer_details
Revises: 0002_interview_question_completion
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_mock_interview_answer_details"
down_revision = "0002_interview_question_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mock_interview_answers", sa.Column("category", sa.String(length=64), nullable=True))
    op.add_column("mock_interview_answers", sa.Column("difficulty", sa.String(length=32), nullable=True))
    op.add_column("mock_interview_answers", sa.Column("suggested_answer", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("mock_interview_answers", "suggested_answer")
    op.drop_column("mock_interview_answers", "difficulty")
    op.drop_column("mock_interview_answers", "category")