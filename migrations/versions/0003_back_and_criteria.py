"""criterion of a block screen and revisions of a screen

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20 12:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('block_responses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('criterion', sa.Integer(), nullable=True))
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.add_column(sa.Column('revisions', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.drop_column('revisions')
    with op.batch_alter_table('block_responses', schema=None) as batch_op:
        batch_op.drop_column('criterion')
