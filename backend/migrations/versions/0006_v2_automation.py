"""add v2 agentic automation tables and application tracking fields

Revision ID: 0006_v2_automation
Revises: 0005_mock_interview_answer_position
"""
from alembic import op
import sqlalchemy as sa


revision = "0006_v2_automation"
down_revision = "0005_mock_interview_answer_position"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Applications new columns
    op.add_column("applications", sa.Column("automation_status", sa.String(length=32), nullable=True))
    op.add_column("applications", sa.Column("last_automation_attempt", sa.DateTime(timezone=True), nullable=True))

    # candidate_profiles
    op.create_table(
        "candidate_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=1024), nullable=True),
        sa.Column("github_url", sa.String(length=1024), nullable=True),
        sa.Column("portfolio_url", sa.String(length=1024), nullable=True),
        sa.Column("work_authorization", sa.String(length=120), nullable=True),
        sa.Column("requires_sponsorship", sa.Boolean(), nullable=True),
        sa.Column("demographic_sharing_opt_in", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("years_of_experience", sa.Integer(), nullable=True),
        sa.Column("education_degree", sa.String(length=120), nullable=True),
        sa.Column("education_field", sa.String(length=120), nullable=True),
        sa.Column("education_school", sa.String(length=255), nullable=True),
        sa.Column("answers_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_candidate_profiles_user", "candidate_profiles", ["user_id"])

    # automation_scenarios
    op.create_table(
        "automation_scenarios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("company", sa.String(length=255), server_default="*", nullable=False),
        sa.Column("page_signature", sa.String(length=255), server_default="*", nullable=False),
        sa.Column("field_key", sa.String(length=255), nullable=False),
        sa.Column("element_strategy_json", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("value_source", sa.String(length=64), nullable=False),
        sa.Column("static_value", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=16), server_default="HIGH", nullable=False),
        sa.Column("confidence_reason", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_approved", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("times_used", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_scenarios_company_field", "automation_scenarios", ["company", "field_key"])
    op.create_index("ix_automation_scenarios_user", "automation_scenarios", ["user_id"])

    # automation_runs
    op.create_table(
        "automation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("application_id", sa.Uuid(), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("job_title", sa.String(length=255), nullable=False),
        sa.Column("job_url", sa.String(length=2048), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="DISCOVERED", nullable=False),
        sa.Column("current_step", sa.String(length=120), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("requires_user_action", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("user_prompt", sa.Text(), nullable=True),
        sa.Column("user_prompt_context_json", sa.Text(), nullable=True),
        sa.Column("suggested_action_json", sa.Text(), nullable=True),
        sa.Column("user_response_json", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(length=1024), nullable=True),
        sa.Column("scenarios_used_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_runs_user_status", "automation_runs", ["user_id", "status"])
    op.create_index("ix_automation_runs_created_at", "automation_runs", ["user_id", "created_at"])

    # automation_action_logs
    op.create_table(
        "automation_action_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=32), nullable=False),
        sa.Column("action_source", sa.String(length=32), nullable=False),
        sa.Column("step_name", sa.String(length=120), nullable=True),
        sa.Column("selector_used", sa.String(length=512), nullable=True),
        sa.Column("value_used", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(length=16), server_default="HIGH", nullable=False),
        sa.Column("confidence_reason", sa.Text(), nullable=True),
        sa.Column("result", sa.String(length=32), server_default="success", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("screenshot_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["automation_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_action_logs_run", "automation_action_logs", ["run_id"])

    # automation_settings
    op.create_table(
        "automation_settings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("schedule_interval", sa.String(length=32), server_default="manual", nullable=False),
        sa.Column("auto_submit", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("allowed_companies_json", sa.Text(), nullable=True),
        sa.Column("max_daily_applications", sa.Integer(), server_default="10", nullable=False),
        sa.Column("delay_between_actions_ms", sa.Integer(), server_default="800", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("automation_settings")
    op.drop_table("automation_action_logs")
    op.drop_table("automation_runs")
    op.drop_table("automation_scenarios")
    op.drop_table("candidate_profiles")
    op.drop_column("applications", "last_automation_attempt")
    op.drop_column("applications", "automation_status")

