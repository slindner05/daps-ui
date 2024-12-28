"""add match_alt and clean_assets

Revision ID: b6c35bb19a0b
Revises: 31f9073ee748
Create Date: 2024-12-27 18:49:31.984589

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "b6c35bb19a0b"
down_revision = "31f9073ee748"
branch_labels = None
depends_on = None


def upgrade():
    # Add clean_assets and match_alt columns with default value 0
    op.add_column(
        "settings_table",
        sa.Column("clean_assets", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "settings_table",
        sa.Column("match_alt", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    # Remove clean_assets and match_alt columns
    op.drop_column("settings_table", "clean_assets")
    op.drop_column("settings_table", "match_alt")
    # ### end Alembic commands ###
