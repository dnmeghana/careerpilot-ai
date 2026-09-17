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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Add optional matching & scheduling settings to job_search_configs if not present
    configs_columns = [c["name"] for c in inspector.get_columns("job_search_configs")]
    if "min_match_score" not in configs_columns:
        op.add_column(
            "job_search_configs",
            sa.Column("min_match_score", sa.Float(), nullable=False, server_default="50.0"),
        )
    if "skip_already_applied" not in configs_columns:
        op.add_column(
            "job_search_configs",
            sa.Column("skip_already_applied", sa.Boolean(), nullable=False, server_default="true"),
        )
    if "schedule_interval" not in configs_columns:
        op.add_column(
            "job_search_configs",
            sa.Column("schedule_interval", sa.String(length=32), nullable=False, server_default="manual"),
        )

    # Add requisition identity, raw experience, and detailed skills breakdown to discovered_jobs if not present
    discovered_columns = [c["name"] for c in inspector.get_columns("discovered_jobs")]
    if "requisition_id" not in discovered_columns:
        op.add_column(
            "discovered_jobs",
            sa.Column("requisition_id", sa.String(length=255), nullable=True),
        )
    if "experience_raw" not in discovered_columns:
        op.add_column(
            "discovered_jobs",
            sa.Column("experience_raw", sa.String(length=255), nullable=True),
        )
    if "matched_skills_json" not in discovered_columns:
        op.add_column(
            "discovered_jobs",
            sa.Column("matched_skills_json", sa.Text(), nullable=True),
        )
    if "missing_skills_json" not in discovered_columns:
        op.add_column(
            "discovered_jobs",
            sa.Column("missing_skills_json", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    discovered_columns = [c["name"] for c in inspector.get_columns("discovered_jobs")]
    for col in ("missing_skills_json", "matched_skills_json", "experience_raw", "requisition_id"):
        if col in discovered_columns:
            op.drop_column("discovered_jobs", col)

    configs_columns = [c["name"] for c in inspector.get_columns("job_search_configs")]
    for col in ("schedule_interval", "skip_already_applied", "min_match_score"):
        if col in configs_columns:
            op.drop_column("job_search_configs", col)
