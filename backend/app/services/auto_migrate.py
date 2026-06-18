"""
Lightweight auto-migration utility for PhantomWALL.

Runs on application startup to ensure the live database schema matches
the SQLAlchemy ORM model definitions.  This handles the gap that
`Base.metadata.create_all` cannot fill: adding new columns to tables
that already exist.

This replaces a full Alembic migration setup for zero-configuration
deployments (Docker, Hugging Face Spaces).
"""

import logging

from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.models import Base

logger = logging.getLogger(__name__)


# Map SQLAlchemy type names → portable SQL column type strings.
_TYPE_MAP = {
    "String": "VARCHAR({length})",
    "Text": "TEXT",
    "Integer": "INTEGER",
    "Float": "DOUBLE PRECISION",
    "Boolean": "BOOLEAN",
    "DateTime": "TIMESTAMP WITH TIME ZONE",
}


def _sql_type(sa_column) -> str:
    """Convert a SQLAlchemy column type object to a raw SQL type string."""
    type_name = type(sa_column.type).__name__

    if type_name == "String":
        length = getattr(sa_column.type, "length", None) or 255
        return f"VARCHAR({length})"
    return _TYPE_MAP.get(type_name, "TEXT")


def _default_clause(sa_column) -> str:
    """Return a SQL DEFAULT clause if the column is non-nullable and has a
    server_default or a sensible Python-side default we can express in DDL."""
    if sa_column.server_default is not None:
        return f" DEFAULT {sa_column.server_default.arg}"
    if sa_column.nullable:
        return ""
    # For non-nullable columns without a server default, provide a safe
    # literal so the ALTER TABLE succeeds on tables that already have rows.
    type_name = type(sa_column.type).__name__
    safe_defaults = {
        "String": "''",
        "Text": "''",
        "Integer": "0",
        "Float": "0.0",
        "Boolean": "FALSE",
        "DateTime": "NOW()",
    }
    default = safe_defaults.get(type_name)
    if default:
        return f" DEFAULT {default}"
    return ""


async def run_auto_migration(engine: AsyncEngine) -> None:
    """Inspect every ORM table and ALTER TABLE ADD COLUMN for any column
    present in the model but absent from the live database."""

    async with engine.connect() as conn:
        # Use run_sync to access the synchronous Inspector
        def _sync_inspect(sync_conn):
            insp = inspect(sync_conn)
            results = {}
            for table in Base.metadata.sorted_tables:
                table_name = table.name
                if not insp.has_table(table_name):
                    # Table doesn't exist yet; create_all will handle it
                    continue
                existing_cols = {c["name"] for c in insp.get_columns(table_name)}
                model_cols = {c.name: c for c in table.columns}
                missing = {
                    name: col
                    for name, col in model_cols.items()
                    if name not in existing_cols
                }
                if missing:
                    results[table_name] = missing
            return results

        missing_columns = await conn.run_sync(_sync_inspect)

        if not missing_columns:
            logger.info("Auto-migration: schema is up to date.")
            return

        for table_name, columns in missing_columns.items():
            for col_name, sa_column in columns.items():
                col_type = _sql_type(sa_column)
                nullable = "NULL" if sa_column.nullable else "NOT NULL"
                default = _default_clause(sa_column)

                ddl = f'ALTER TABLE "{table_name}" ADD COLUMN "{col_name}" {col_type} {nullable}{default}'
                logger.info("Auto-migration: %s", ddl)
                await conn.execute(text(ddl))

        await conn.commit()
        logger.info(
            "Auto-migration: added %d column(s) across %d table(s).",
            sum(len(cols) for cols in missing_columns.values()),
            len(missing_columns),
        )
