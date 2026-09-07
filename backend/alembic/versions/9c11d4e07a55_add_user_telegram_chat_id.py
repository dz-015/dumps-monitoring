"""add user.telegram_chat_id

Revision ID: 9c11d4e07a55
Revises: 7be40c1a2d90
Create Date: 2026-08-03 04:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9c11d4e07a55'
down_revision: Union[str, None] = '7be40c1a2d90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('telegram_chat_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('telegram_chat_id')
