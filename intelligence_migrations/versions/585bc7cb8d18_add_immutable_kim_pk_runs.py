"""Add immutable saved Kim 2026 runs (Patient Lab 2.1f)

Revision ID: 585bc7cb8d18
Revises: 3949e70874a5
Create Date: 2026-10-14 15:40:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '585bc7cb8d18'
down_revision = '3949e70874a5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('kim_pk_run',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('revision_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('created_at_utc', sa.DateTime(), nullable=False),
    sa.Column('schema_version', sa.String(length=40), nullable=False),
    sa.Column('report_sha256', sa.String(length=64), nullable=False),
    sa.Column('payload_sha256', sa.String(length=64), nullable=False),
    sa.Column('save_key', sa.String(length=64), nullable=False),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.ForeignKeyConstraint(['revision_id'], ['patient_state_revision.id'], name=op.f('fk_kim_pk_run_revision_id_patient_state_revision'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kim_pk_run')),
    sa.UniqueConstraint('save_key', name=op.f('uq_kim_pk_run_save_key'))
    )
    with op.batch_alter_table('kim_pk_run', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_kim_pk_run_revision_id'), ['revision_id'], unique=False)


def downgrade():
    with op.batch_alter_table('kim_pk_run', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_kim_pk_run_revision_id'))
    op.drop_table('kim_pk_run')
