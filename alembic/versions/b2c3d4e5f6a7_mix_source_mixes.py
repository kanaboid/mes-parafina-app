"""mix_source_mixes table

Revision ID: b2c3d4e5f6a7
Revises: c1de97e2d69a
Create Date: 2026-02-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'c1de97e2d69a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mix_source_mixes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('mix_id', sa.Integer(), nullable=False),
        sa.Column('source_mix_id', sa.Integer(), nullable=False),
        sa.Column('quantity_from_source', sa.DECIMAL(10, 2), nullable=False),
        sa.ForeignKeyConstraint(['mix_id'], ['tank_mixes.id']),
        sa.ForeignKeyConstraint(['source_mix_id'], ['tank_mixes.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mix_source_mixes_mix_id', 'mix_source_mixes', ['mix_id'])
    op.create_index('ix_mix_source_mixes_source_mix_id', 'mix_source_mixes', ['source_mix_id'])


def downgrade() -> None:
    op.drop_index('ix_mix_source_mixes_source_mix_id', 'mix_source_mixes')
    op.drop_index('ix_mix_source_mixes_mix_id', 'mix_source_mixes')
    op.drop_table('mix_source_mixes')
