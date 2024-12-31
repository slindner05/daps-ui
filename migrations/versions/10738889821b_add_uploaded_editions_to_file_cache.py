"""add uploaded editions to file cache

Revision ID: 10738889821b
Revises: 16b0ad839532
Create Date: 2024-12-30 17:00:15.542944

"""

import sqlalchemy as sa
from alembic import op

from daps_webui.models.file_cache import \
    JSONEncodedText  # Ensure correct import

# revision identifiers, used by Alembic.
revision = "10738889821b"
down_revision = "16b0ad839532"
branch_labels = None
depends_on = None


def upgrade():
    # Add the uploaded_editions column to the file_cache table
    op.add_column(
        "file_cache",
        sa.Column(
            "uploaded_editions", JSONEncodedText(), nullable=False, server_default="[]"
        ),
    )


def downgrade():
    # Remove the uploaded_editions column from the file_cache table
    op.drop_column("file_cache", "uploaded_editions")
