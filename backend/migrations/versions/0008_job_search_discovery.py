"""Add job search config and discovered jobs tables for multi-job discovery

Revision ID: 0008_search_discovery
Revises: 0007_url_tracking
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_search_discovery"
down_revision = "0007_url_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_search_configs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("desired_job_title", sa.String(length=255), nullable=False),
        sa.Column("desired_location", sa.String(length=255), nullable=False),
        sa.Column("years_of_experience", sa.Integer(), nullable=False, default=0),
        sa.Column("platform_search_url", sa.String(length=2048), nullable=False),
        sa.Column("specific_company", sa.String(length=255), nullable=True),
        sa.Column("active_resume_id", sa.Uuid(), sa.ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("max_jobs_to_discover", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_searched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "discovered_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("config_id", sa.Uuid(), sa.ForeignKey("job_search_configs.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("exact_title", sa.String(length=255), nullable=False),
        sa.Column("job_url", sa.String(length=2048), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("platform", sa.String(length=64), nullable=False, server_default="portal"),
        sa.Column("raw_description", sa.Text(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("title_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("skills_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("location_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("experience_score", sa.Float(), nullable=False, default=0.0),
        sa.Column("is_matched", sa.Boolean(), nullable=False, default=False),
        sa.Column("match_reasons_json", sa.Text(), nullable=True),
        sa.Column("match_breakdown_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="DISCOVERED"),
        sa.Column("automation_run_id", sa.Uuid(), sa.ForeignKey("automation_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_discovered_jobs_user_status", "discovered_jobs", ["user_id", "status"])
    op.create_index("ix_discovered_jobs_user_score", "discovered_jobs", ["user_id", "match_score"])


def downgrade() -> None:
    op.drop_table("discovered_jobs")
    op.drop_table("job_search_configs")
