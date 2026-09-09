"""add mock interview answer position

Revision ID: 0005_mock_interview_answer_position
Revises: 0004_mock_interview_type
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_mock_interview_answer_position"
down_revision = "0004_mock_interview_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mock_interview_answers", sa.Column("position", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("mock_interview_answers", "position")