"""question order and paradata of a screen

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19 22:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.add_column(sa.Column('question_order_json', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('leaves', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('away_ms', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('links_json', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.drop_column('links_json')
        batch_op.drop_column('away_ms')
        batch_op.drop_column('leaves')
        batch_op.drop_column('question_order_json')
