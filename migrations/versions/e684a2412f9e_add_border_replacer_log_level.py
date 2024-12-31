"""add border replacer log level

Revision ID: e684a2412f9e
Revises: 10738889821b
Create Date: 2024-12-31 12:30:09.278232

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e684a2412f9e"
down_revision = "10738889821b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "settings_table",
        sa.Column(
            "log_level_border_replacerr",
            sa.String(),
            nullable=False,
            server_default="info",
        ),
    )


def downgrade():
    op.drop_column("settings_table", "log_level_border_replacerr")
    # ### end Alembic commands ###
