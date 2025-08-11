"""Bazowy schemat przed usunieciem kolumny

Revision ID: 55c02b31917b
Revises: d4c4e6b121e0
Create Date: 2025-08-11 01:30:55.185103

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55c02b31917b'
down_revision: Union[str, None] = 'd4c4e6b121e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
