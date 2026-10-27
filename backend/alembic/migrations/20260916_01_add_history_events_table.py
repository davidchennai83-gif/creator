"""Add history_events table

Revision ID: 20260916_01
Revises:
Create Date: 2026-09-16 01:00:00.000000

INACTIVE: alembic.ini points at ``alembic/versions``, so this file is never
executed by ``alembic upgrade head``. It is kept as the reference schema for
history_events (currently unused by the app and seeded via seed_history.py).
To activate it, move it into alembic/versions with ``down_revision = '0001'``
(and register app.models.history_event) so the revision chain stays linear.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260916_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'history_events',
        sa.Column('id', sa.Integer(), nullable=False),
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