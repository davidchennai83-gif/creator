"""Add history_events table

Revision ID: 20260916_01
Revises: 
Create Date: 2026-09-16 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260916_01'
down_revision = None
branch_labels = None
depends_on_none = None


def upgrade():
    op.create_table(
        'history_events',
        sa.Column('id', sa.Integer(), nullable_primary=False),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        sa.Column('event_title', sa.String(200), nullable=False),
        sa.Column('event_description', sa.Text(), nullable=False),
        sa.Column('tamil_title', sa.String(200), nullable=False),
        sa.Column('tamil_description', sa.Text(), nullable=False),
        sa.Column('importance_points', sa.JSON(), nullable=False),
        sa.Column('bgm_track', sa.String(100)),
        sa.Column('voice_over_path', sa.String(100)),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('date'),
    )


def downgrade():
    op.drop_table('history_events')