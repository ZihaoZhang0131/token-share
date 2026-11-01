"""Add endpoint modes and pinned reasoning effort; preserve existing chat routes."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "model_routes", sa.Column("api_mode", sa.String(16), nullable=False, server_default="chat")
    )
    op.add_column("model_routes", sa.Column("reasoning_effort", sa.String(16), nullable=True))


def downgrade():
    op.drop_column("model_routes", "reasoning_effort")
    op.drop_column("model_routes", "api_mode")
