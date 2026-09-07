"""add user.max_user_id

Revision ID: d41f8c25ab19
Revises: 9c11d4e07a55
Create Date: 2026-08-03 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd41f8c25ab19'
down_revision: Union[str, None] = '9c11d4e07a55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('max_user_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('max_user_id')
