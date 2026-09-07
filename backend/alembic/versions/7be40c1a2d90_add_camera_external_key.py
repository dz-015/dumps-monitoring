"""add camera.external_key

Revision ID: 7be40c1a2d90
Revises: 6da671ee0981
Create Date: 2026-07-31 14:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7be40c1a2d90'
down_revision: Union[str, None] = '6da671ee0981'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.add_column(sa.Column('external_key', sa.String(length=50), nullable=True))
        batch_op.create_index(batch_op.f('ix_cameras_external_key'), ['external_key'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('cameras', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_cameras_external_key'))
        batch_op.drop_column('external_key')
