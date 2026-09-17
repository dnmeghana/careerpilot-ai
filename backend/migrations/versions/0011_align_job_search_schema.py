"""Align job_search_configs and discovered_jobs schema with application model

Revision ID: 0011_align_job_search_schema
Revises: 0010_job_search_v2
"""

from alembic import op
import sqlalchemy as sa


revision = "0011_align_job_search_schema"
down_revision = "0010_job_search_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Align job_search_configs columns
    configs_columns = [c["name"] for c in inspector.get_columns("job_search_configs")]
    if "resume_id" in configs_columns and "active_resume_id" not in configs_columns:
        op.alter_column("job_search_configs", "resume_id", new_column_name="active_resume_id")

    if "max_jobs_per_run" in configs_columns and "max_jobs_to_discover" not in configs_columns:
        op.alter_column("job_search_configs", "max_jobs_per_run", new_column_name="max_jobs_to_discover")

    if "last_run_at" in configs_columns and "last_searched_at" not in configs_columns:
        op.alter_column("job_search_configs", "last_run_at", new_column_name="last_searched_at")

    # 2. Align discovered_jobs columns
    discovered_columns = [c["name"] for c in inspector.get_columns("discovered_jobs")]
    if "search_config_id" in discovered_columns and "config_id" not in discovered_columns:
        op.alter_column("discovered_jobs", "search_config_id", new_column_name="config_id")

    if "title" in discovered_columns and "exact_title" not in discovered_columns:
        op.alter_column("discovered_jobs", "title", new_column_name="exact_title")

    if "platform_source" in discovered_columns and "platform" not in discovered_columns:
        op.alter_column("discovered_jobs", "platform_source", new_column_name="platform")

    if "description" in discovered_columns and "raw_description" not in discovered_columns:
        op.alter_column("discovered_jobs", "description", new_column_name="raw_description")

    # Add missing scoring and metadata columns if not present
    if "title_score" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("title_score", sa.Float(), nullable=False, server_default="0.0"))
    if "skills_score" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("skills_score", sa.Float(), nullable=False, server_default="0.0"))
    if "location_score" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("location_score", sa.Float(), nullable=False, server_default="0.0"))
    if "experience_score" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("experience_score", sa.Float(), nullable=False, server_default="0.0"))
    if "is_matched" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("is_matched", sa.Boolean(), nullable=False, server_default="false"))
    if "match_breakdown_json" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("match_breakdown_json", sa.Text(), nullable=True))
    if "discovered_at" not in discovered_columns:
        op.add_column("discovered_jobs", sa.Column("discovered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    discovered_columns = [c["name"] for c in inspector.get_columns("discovered_jobs")]
    for col in ("discovered_at", "match_breakdown_json", "is_matched", "experience_score", "location_score", "skills_score", "title_score"):
        if col in discovered_columns:
            op.drop_column("discovered_jobs", col)

    if "raw_description" in discovered_columns and "description" not in discovered_columns:
        op.alter_column("discovered_jobs", "raw_description", new_column_name="description")
    if "platform" in discovered_columns and "platform_source" not in discovered_columns:
        op.alter_column("discovered_jobs", "platform", new_column_name="platform_source")
    if "exact_title" in discovered_columns and "title" not in discovered_columns:
        op.alter_column("discovered_jobs", "exact_title", new_column_name="title")
    if "config_id" in discovered_columns and "search_config_id" not in discovered_columns:
        op.alter_column("discovered_jobs", "config_id", new_column_name="search_config_id")

    configs_columns = [c["name"] for c in inspector.get_columns("job_search_configs")]
    if "last_searched_at" in configs_columns and "last_run_at" not in configs_columns:
        op.alter_column("job_search_configs", "last_searched_at", new_column_name="last_run_at")
    if "max_jobs_to_discover" in configs_columns and "max_jobs_per_run" not in configs_columns:
        op.alter_column("job_search_configs", "max_jobs_to_discover", new_column_name="max_jobs_per_run")
    if "active_resume_id" in configs_columns and "resume_id" not in configs_columns:
        op.alter_column("job_search_configs", "active_resume_id", new_column_name="resume_id")

