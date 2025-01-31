"""updated projet table

Revision ID: f3586568b9d3
Revises: 4a60a5f7a9ee
Create Date: 2025-02-01 01:23:52.520561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3586568b9d3'
down_revision: Union[str, None] = '4a60a5f7a9ee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.add_column('projects', sa.Column('repo_path', sa.String(), nullable=False))
    op.add_column('projects', sa.Column('default_branch', sa.String(), nullable=False))
    op.add_column('projects', sa.Column('current_branch', sa.String(), nullable=False))
    op.add_column('projects', sa.Column('last_commit', sa.String(), nullable=False))

def downgrade():
    op.drop_column('projects', 'repo_path')
    op.drop_column('projects', 'default_branch')
    op.drop_column('projects', 'current_branch')
    op.drop_column('projects', 'last_commit')
