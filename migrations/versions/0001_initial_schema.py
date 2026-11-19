"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-11-17 11:12:51.631028

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('rate_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('rate_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rate_events_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_rate_events_key'), ['key'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.String(length=20), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('ui_language', sa.String(length=8), nullable=True),
    sa.Column('session_version', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)

    op.create_table('surveys',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('owner_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('definition_json', sa.Text(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('allocation_seed', sa.String(length=64), nullable=False),
    sa.Column('is_demo', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('published_at', sa.DateTime(), nullable=True),
    sa.Column('closed_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('surveys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_surveys_owner_id'), ['owner_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_surveys_slug'), ['slug'], unique=True)

    op.create_table('responses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('survey_id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=40), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=12), nullable=False),
    sa.Column('preview', sa.Boolean(), nullable=False),
    sa.Column('consented', sa.Boolean(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('state_json', sa.Text(), nullable=False),
    sa.Column('assignments_json', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('retest_submitted_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('responses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_responses_survey_id'), ['survey_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_responses_uuid'), ['uuid'], unique=True)

    op.create_table('allocations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('survey_id', sa.Integer(), nullable=False),
    sa.Column('randomizer_key', sa.String(length=64), nullable=False),
    sa.Column('stratum', sa.String(length=200), nullable=False),
    sa.Column('seq_no', sa.Integer(), nullable=False),
    sa.Column('arm', sa.String(length=32), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=True),
    sa.Column('preview', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['survey_id'], ['surveys.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('survey_id', 'randomizer_key', 'stratum', 'seq_no')
    )
    with op.batch_alter_table('allocations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_allocations_response_id'), ['response_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_allocations_survey_id'), ['survey_id'], unique=False)

    op.create_table('answers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('response_id', 'module_key', 'name', 'occasion')
    )
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_answers_response_id'), ['response_id'], unique=False)

    op.create_table('arrangements',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('board_kind', sa.String(length=16), nullable=False),
    sa.Column('placements_json', sa.Text(), nullable=False),
    sa.Column('reading_json', sa.Text(), nullable=False),
    sa.Column('coherent', sa.Boolean(), nullable=False),
    sa.Column('paradata_json', sa.Text(), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('response_id', 'module_key', 'occasion')
    )
    with op.batch_alter_table('arrangements', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_arrangements_response_id'), ['response_id'], unique=False)

    op.create_table('block_responses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('technique', sa.String(length=8), nullable=False),
    sa.Column('variant', sa.String(length=64), nullable=False),
    sa.Column('design_block', sa.Integer(), nullable=True),
    sa.Column('repeat_of', sa.Integer(), nullable=True),
    sa.Column('attention', sa.Boolean(), nullable=False),
    sa.Column('attention_passed', sa.Boolean(), nullable=True),
    sa.Column('cards_json', sa.Text(), nullable=False),
    sa.Column('result_json', sa.Text(), nullable=False),
    sa.Column('gate_value', sa.String(length=64), nullable=True),
    sa.Column('events_json', sa.Text(), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('response_id', 'module_key', 'occasion', 'position')
    )
    with op.batch_alter_table('block_responses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_block_responses_response_id'), ['response_id'], unique=False)

    op.create_table('confirmations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('element_a', sa.String(length=64), nullable=False),
    sa.Column('element_b', sa.String(length=64), nullable=False),
    sa.Column('answer', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('confirmations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_confirmations_response_id'), ['response_id'], unique=False)

    op.create_table('judgments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('element_a', sa.String(length=64), nullable=False),
    sa.Column('element_b', sa.String(length=64), nullable=False),
    sa.Column('state', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('judgments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_judgments_response_id'), ['response_id'], unique=False)

    op.create_table('pair_observations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('item_a', sa.String(length=64), nullable=False),
    sa.Column('item_b', sa.String(length=64), nullable=False),
    sa.Column('relation', sa.String(length=16), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('pair_observations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_pair_observations_response_id'), ['response_id'], unique=False)

    op.create_table('screen_times',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('response_id', sa.Integer(), nullable=False),
    sa.Column('screen_key', sa.String(length=120), nullable=False),
    sa.Column('module_key', sa.String(length=64), nullable=False),
    sa.Column('occasion', sa.Integer(), nullable=False),
    sa.Column('first_shown_at', sa.DateTime(), nullable=False),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('client_ms', sa.Integer(), nullable=True),
    sa.Column('visits', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('response_id', 'screen_key')
    )
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_screen_times_response_id'), ['response_id'], unique=False)



def downgrade():
    with op.batch_alter_table('screen_times', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_screen_times_response_id'))

    op.drop_table('screen_times')
    with op.batch_alter_table('pair_observations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_pair_observations_response_id'))

    op.drop_table('pair_observations')
    with op.batch_alter_table('judgments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_judgments_response_id'))

    op.drop_table('judgments')
    with op.batch_alter_table('confirmations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_confirmations_response_id'))

    op.drop_table('confirmations')
    with op.batch_alter_table('block_responses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_block_responses_response_id'))

    op.drop_table('block_responses')
    with op.batch_alter_table('arrangements', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_arrangements_response_id'))

    op.drop_table('arrangements')
    with op.batch_alter_table('answers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_answers_response_id'))

    op.drop_table('answers')
    with op.batch_alter_table('allocations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_allocations_survey_id'))
        batch_op.drop_index(batch_op.f('ix_allocations_response_id'))

    op.drop_table('allocations')
    with op.batch_alter_table('responses', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_responses_uuid'))
        batch_op.drop_index(batch_op.f('ix_responses_survey_id'))

    op.drop_table('responses')
    with op.batch_alter_table('surveys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_surveys_slug'))
        batch_op.drop_index(batch_op.f('ix_surveys_owner_id'))

    op.drop_table('surveys')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_email'))

    op.drop_table('users')
    with op.batch_alter_table('rate_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rate_events_key'))
        batch_op.drop_index(batch_op.f('ix_rate_events_created_at'))

    op.drop_table('rate_events')
