"""estado "duplicado" para los hallazgos

Una validación con decisión "duplicado" deja el hallazgo en este estado
(T-057): sale de la cola sin decir que el problema no existe, que es lo que
diría falso_positivo.

Revision ID: 7c2e9d41b3a5
Revises: 418a070dfa63
Create Date: 2026-11-15 21:30:00
"""
from typing import Sequence, Union

from alembic import op

revision: str = "7c2e9d41b3a5"
down_revision: Union[str, None] = "418a070dfa63"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: si alguien bajó solo esta migración y vuelve a subir, el
    # valor sigue en el tipo (ver downgrade) y no debe fallar.
    op.execute("ALTER TYPE estado_hallazgo ADD VALUE IF NOT EXISTS 'duplicado'")


def downgrade() -> None:
    # No se puede deshacer: PostgreSQL no permite quitar un valor de un enum.
    # Recrear el tipo sin 'duplicado' obligaría a reescribir la columna y a
    # decidir qué hacer con los hallazgos que ya están en ese estado. El valor
    # queda en el tipo; sin usarlo, no molesta. `alembic downgrade base` sí lo
    # elimina, porque el downgrade de la migración inicial borra los tipos.
    pass
