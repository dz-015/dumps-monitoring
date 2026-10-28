"""add camera.watcher_stream

Revision ID: a3f9c1e7b204
Revises: d41f8c25ab19
Create Date: 2026-09-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f9c1e7b204'
down_revision: Union[str, None] = 'd41f8c25ab19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.add_column(sa.Column('watcher_stream', sa.String(length=255), nullable=True))
        batch_op.create_index('ix_cameras_watcher_stream', ['watcher_stream'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.drop_index('ix_cameras_watcher_stream')
        batch_op.drop_column('watcher_stream')
