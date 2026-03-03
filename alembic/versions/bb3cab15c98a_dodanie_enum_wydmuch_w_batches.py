"""Dodanie ENUM Wydmuch w Batches

Revision ID: bb3cab15c98a
Revises: b2c3d4e5f6a7
Create Date: 2026-03-03 13:06:18.105908

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bb3cab15c98a'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rozszerzenie istniejącego ENUM o 'WYDMUCH'
    op.execute(
        "ALTER TABLE batches "
        "MODIFY COLUMN source_type ENUM('CYS', 'APOLLO', 'WYDMUCH') "
        "NOT NULL DEFAULT 'APOLLO'"
    )


def downgrade() -> None:
    # Powrót do poprzedniej listy wartości ENUM (bez 'WYDMUCH')
    op.execute(
        "ALTER TABLE batches "
        "MODIFY COLUMN source_type ENUM('CYS', 'APOLLO') "
        "NOT NULL DEFAULT 'APOLLO'"
    )
