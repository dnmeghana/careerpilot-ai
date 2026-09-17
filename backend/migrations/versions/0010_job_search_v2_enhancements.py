"""Add v2 job search enhancements (min_match_score, skip_already_applied, schedule_interval, requisition_id, experience_raw, skills JSON)

Revision ID: 0010_job_search_v2
Revises: 0009_password_reset
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_job_search_v2"
down_revision = "0009_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add optional matching & scheduling settings to job_search_configs
    op.add_column(
        "job_search_configs",
        sa.Column("min_match_score", sa.Float(), nullable=False, server_default="50.0"),
    )
    op.add_column(
        "job_search_configs",
        sa.Column("skip_already_applied", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "job_search_configs",
        sa.Column("schedule_interval", sa.String(length=32), nullable=False, server_default="manual"),
    )

    # Add requisition identity, raw experience, and detailed skills breakdown to discovered_jobs
    op.add_column(
        "discovered_jobs",
        sa.Column("requisition_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("experience_raw", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("matched_skills_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "discovered_jobs",
        sa.Column("missing_skills_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovered_jobs", "missing_skills_json")
    op.drop_column("discovered_jobs", "matched_skills_json")
    op.drop_column("discovered_jobs", "experience_raw")
    op.drop_column("discovered_jobs", "requisition_id")
    op.drop_column("job_search_configs", "schedule_interval")
    op.drop_column("job_search_configs", "skip_already_applied")
    op.drop_column("job_search_configs", "min_match_score")
