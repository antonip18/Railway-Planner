"""Initial normalized timetable and whole-train coupling schema

Revision ID: 0001
Revises:
Create Date: 2026-11-19 18:38:30.228523

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "carriage_types",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("rows", sa.Integer(), nullable=False),
        sa.Column("columns", sa.Integer(), nullable=False),
        sa.Column("compartment", sa.Boolean(), nullable=False),
        sa.Column("layout", sa.JSON(), nullable=False),
        sa.CheckConstraint("rows > 0 AND columns > 0", name=op.f("ck_carriage_types_dimensions")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carriage_types")),
    )
    op.create_table(
        "datasets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("version", sa.String(length=200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("attributions", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_datasets")),
        sa.UniqueConstraint("fingerprint", name=op.f("uq_datasets_fingerprint")),
    )
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_key", sa.String(length=200), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name=op.f("ck_stations_latitude")),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name=op.f("ck_stations_longitude")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stations")),
        sa.UniqueConstraint("source_key", name=op.f("uq_stations_source_key")),
    )
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stations_name"), ["name"], unique=False)

    op.create_table(
        "trains",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identity", sa.String(length=240), nullable=False),
        sa.Column("agency", sa.String(length=80), nullable=False),
        sa.Column("number", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trains")),
        sa.UniqueConstraint("identity", name=op.f("uq_trains_identity")),
    )
    op.create_table(
        "carriages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=False),
        sa.Column("type_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position > 0", name=op.f("ck_carriages_position")),
        sa.ForeignKeyConstraint(
            ["train_id"],
            ["trains.id"],
            name=op.f("fk_carriages_train_id_trains"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["type_id"], ["carriage_types.id"], name=op.f("fk_carriages_type_id_carriage_types")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_carriages")),
        sa.UniqueConstraint("train_id", "position", name=op.f("uq_carriages_train_id")),
    )
    op.create_table(
        "route_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("train_id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=True),
        sa.Column("signature", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False),
        sa.CheckConstraint("mode IN ('rail','bus')", name=op.f("ck_route_variants_mode")),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_route_variants_dataset_id_datasets")
        ),
        sa.ForeignKeyConstraint(
            ["train_id"], ["trains.id"], name=op.f("fk_route_variants_train_id_trains")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_route_variants")),
        sa.UniqueConstraint("signature", name=op.f("uq_route_variants_signature")),
    )
    with op.batch_alter_table("route_variants", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_route_variants_train_id"), ["train_id"], unique=False)

    op.create_table(
        "transfer_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("from_station_id", sa.Integer(), nullable=True),
        sa.Column("to_station_id", sa.Integer(), nullable=True),
        sa.Column("from_trip_id", sa.String(length=240), nullable=True),
        sa.Column("to_trip_id", sa.String(length=240), nullable=True),
        sa.Column("from_route_id", sa.String(length=200), nullable=True),
        sa.Column("to_route_id", sa.String(length=200), nullable=True),
        sa.Column("type", sa.Integer(), nullable=False),
        sa.Column("minimum_seconds", sa.Integer(), nullable=True),
        sa.CheckConstraint("type BETWEEN 0 AND 5", name=op.f("ck_transfer_rules_type")),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_transfer_rules_dataset_id_datasets")
        ),
        sa.ForeignKeyConstraint(
            ["from_station_id"],
            ["stations.id"],
            name=op.f("fk_transfer_rules_from_station_id_stations"),
        ),
        sa.ForeignKeyConstraint(
            ["to_station_id"],
            ["stations.id"],
            name=op.f("fk_transfer_rules_to_station_id_stations"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transfer_rules")),
    )
    op.create_table(
        "runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("service_date", sa.Date(), nullable=False),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["route_variants.id"],
            name=op.f("fk_runs_route_id_route_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runs")),
        sa.UniqueConstraint("route_id", "service_date", name=op.f("uq_runs_route_id")),
    )
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_runs_service_date"), ["service_date"], unique=False)

    op.create_table(
        "stops",
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("arrival", sa.Integer(), nullable=False),
        sa.Column("departure", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=40), nullable=True),
        sa.Column("track", sa.String(length=40), nullable=True),
        sa.Column("pickup", sa.Boolean(), nullable=False),
        sa.Column("drop_off", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "arrival >= 0 AND departure >= arrival AND departure < 604800",
            name=op.f("ck_stops_times"),
        ),
        sa.CheckConstraint("sequence >= 0", name=op.f("ck_stops_sequence")),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["route_variants.id"],
            name=op.f("fk_stops_route_id_route_variants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], name=op.f("fk_stops_station_id_stations")
        ),
        sa.PrimaryKeyConstraint("route_id", "sequence", name=op.f("pk_stops")),
    )
    with op.batch_alter_table("stops", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_stops_station_id"), ["station_id"], unique=False)

    op.create_table(
        "trip_sources",
        sa.Column("dataset_id", sa.Integer(), nullable=False),
        sa.Column("trip_id", sa.String(length=240), nullable=False),
        sa.Column("route_id", sa.Integer(), nullable=False),
        sa.Column("gtfs_route_id", sa.String(length=200), nullable=False),
        sa.Column("service_id", sa.String(length=200), nullable=False),
        sa.Column("block_id", sa.String(length=200), nullable=True),
        sa.Column("dates", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["datasets.id"], name=op.f("fk_trip_sources_dataset_id_datasets")
        ),
        sa.ForeignKeyConstraint(
            ["route_id"],
            ["route_variants.id"],
            name=op.f("fk_trip_sources_route_id_route_variants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("dataset_id", "trip_id", name=op.f("pk_trip_sources")),
    )
    with op.batch_alter_table("trip_sources", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_trip_sources_route_id"), ["route_id"], unique=False)

    op.create_table(
        "couplings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("output_run_id", sa.Integer(), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=False),
        sa.ForeignKeyConstraint(
            ["output_run_id"], ["runs.id"], name=op.f("fk_couplings_output_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["station_id"], ["stations.id"], name=op.f("fk_couplings_station_id_stations")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_couplings")),
        sa.UniqueConstraint("output_run_id", name=op.f("uq_couplings_output_run_id")),
    )
    op.create_table(
        "coupling_inputs",
        sa.Column("coupling_id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint("position IN (1,2)", name=op.f("ck_coupling_inputs_position")),
        sa.ForeignKeyConstraint(
            ["coupling_id"],
            ["couplings.id"],
            name=op.f("fk_coupling_inputs_coupling_id_couplings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_coupling_inputs_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("coupling_id", "run_id", name=op.f("pk_coupling_inputs")),
        sa.UniqueConstraint("coupling_id", "position", name=op.f("uq_coupling_inputs_coupling_id")),
        sa.UniqueConstraint("run_id", name=op.f("uq_coupling_inputs_run_id")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("coupling_inputs")
    op.drop_table("couplings")
    with op.batch_alter_table("trip_sources", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_trip_sources_route_id"))

    op.drop_table("trip_sources")
    with op.batch_alter_table("stops", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stops_station_id"))

    op.drop_table("stops")
    with op.batch_alter_table("runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_runs_service_date"))

    op.drop_table("runs")
    op.drop_table("transfer_rules")
    with op.batch_alter_table("route_variants", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_route_variants_train_id"))

    op.drop_table("route_variants")
    op.drop_table("carriages")
    op.drop_table("trains")
    with op.batch_alter_table("stations", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_stations_name"))

    op.drop_table("stations")
    op.drop_table("datasets")
    op.drop_table("carriage_types")
