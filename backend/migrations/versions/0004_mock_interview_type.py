"""add mock interview type

Revision ID: 0004_mock_interview_type
Revises: 0003_mock_interview_answer_details
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_mock_interview_type"
down_revision = "0003_mock_interview_answer_details"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mock_interviews", sa.Column("interview_type", sa.String(length=64), server_default="Behavioral", nullable=False))


def downgrade() -> None:
    op.drop_column("mock_interviews", "interview_type")