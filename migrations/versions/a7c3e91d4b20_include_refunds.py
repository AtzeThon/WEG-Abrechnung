"""include_refunds: Erstattung/Nachzahlung je Periode im Endsaldo berücksichtigen

Revision ID: a7c3e91d4b20
Revises: 5fd0b12998a5
Create Date: 2026-10-22 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c3e91d4b20'
down_revision: str | Sequence[str] | None = '5fd0b12998a5'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema. Bestehende Perioden bleiben unverändert (Flag = aus)."""
    with op.batch_alter_table('billing_periods', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('include_refunds', sa.Boolean(), server_default='0', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('billing_periods', schema=None) as batch_op:
        batch_op.drop_column('include_refunds')
