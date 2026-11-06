"""Separate default output budgets; preserve existing behavior until configured."""

import sqlalchemy as sa

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("model_routes", sa.Column("default_output_tokens", sa.Integer(), nullable=True))
    op.execute("UPDATE model_routes SET default_output_tokens = max_output_tokens")


def downgrade():
    op.drop_column("model_routes", "default_output_tokens")
