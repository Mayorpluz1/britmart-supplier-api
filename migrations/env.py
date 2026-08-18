"""Alembic migration environment for the BritMart Supplier API."""

from __future__ import annotations

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.schema import SchemaItem

from app.core.config import settings
from app.models import Base  # Imports and registers every model.


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the environment-driven application database URL rather than
# storing credentials in alembic.ini. Percent signs must be escaped
# because Alembic configuration uses interpolation.
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("%", "%%"),
)

target_metadata = Base.metadata


# SQLAlchemy Enum objects with native_enum=False create type-bound check
# constraints. SQLite reflects them as ordinary constraints, which can
# produce false-positive Alembic drift after the migration is applied.
#
# We exclude only the known enum constraints. All business check
# constraints remain part of schema comparison.
ENUM_CHECK_CONSTRAINT_NAMES = {
    "ck_product_reference_product_storage_type",
    "ck_purchase_order_lines_purchase_order_line_currency_code",
    "ck_purchase_orders_purchase_order_currency_code",
    "ck_purchase_orders_purchase_order_status",
    "ck_purchase_orders_purchase_order_type",
    "ck_shipment_lines_shipment_line_storage_type",
    "ck_shipment_status_history_shipment_new_status",
    "ck_shipment_status_history_shipment_previous_status",
    "ck_shipments_delivery_performance_status",
    "ck_shipments_shipment_status",
    "ck_supplier_performance_events_performance_event_category",
    "ck_supplier_performance_events_performance_event_severity",
    "ck_supplier_performance_monthly_supplier_performance_rating",
    (
        "ck_supplier_performance_monthly_"
        "supplier_performance_risk_indicator"
    ),
    "ck_supplier_products_agreement_currency_code",
    "ck_supplier_products_agreement_role",
    "ck_supplier_products_agreement_status",
    "ck_supplier_status_history_supplier_new_status",
    "ck_supplier_status_history_supplier_previous_status",
    "ck_suppliers_currency_code",
    "ck_suppliers_supplier_risk_rating",
    "ck_suppliers_supplier_status",
}


def include_object(
    object_: SchemaItem,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to: SchemaItem | None,
) -> bool:
    """Control which database objects participate in autogeneration."""

    del object_, compare_to

    if (
        type_ == "check_constraint"
        and reflected
        and name in ENUM_CHECK_CONSTRAINT_NAMES
    ):
        return False

    return True


def configure_context_options() -> dict[str, Any]:
    """Return shared Alembic comparison options."""

    return {
        "target_metadata": target_metadata,
        "compare_type": True,
        "compare_server_default": True,
        "render_as_batch": settings.is_sqlite,
        "include_object": include_object,
    }


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""

    database_url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=database_url,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        **configure_context_options(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations using a live database connection."""

    connectable = engine_from_config(
        config.get_section(
            config.config_ini_section,
            {},
        ),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            **configure_context_options(),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()