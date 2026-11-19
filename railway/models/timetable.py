from railway.extensions import db


class RouteVariant(db.Model):
    __tablename__ = "route_variants"
    id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column(db.ForeignKey("trains.id"), nullable=False, index=True)
    dataset_id = db.Column(db.ForeignKey("datasets.id"))
    signature = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(300), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    mode = db.Column(db.String(10), nullable=False, default="rail")
    train = db.relationship("Train")
    dataset = db.relationship("Dataset")
    stops = db.relationship(
        "Stop", order_by="Stop.sequence", cascade="all, delete-orphan", back_populates="route"
    )
    runs = db.relationship(
        "Run", cascade="all, delete-orphan", back_populates="route", order_by="Run.service_date"
    )
    __table_args__ = (db.CheckConstraint("mode IN ('rail','bus')", name="mode"),)


class Stop(db.Model):
    __tablename__ = "stops"
    route_id = db.Column(db.ForeignKey("route_variants.id", ondelete="CASCADE"), primary_key=True)
    sequence = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.ForeignKey("stations.id"), nullable=False, index=True)
    arrival = db.Column(db.Integer, nullable=False)
    departure = db.Column(db.Integer, nullable=False)
    platform = db.Column(db.String(40))
    track = db.Column(db.String(40))
    pickup = db.Column(db.Boolean, nullable=False, default=True)
    drop_off = db.Column(db.Boolean, nullable=False, default=True)
    route = db.relationship(RouteVariant, back_populates="stops")
    station = db.relationship("Station")
    __table_args__ = (
        db.CheckConstraint("sequence >= 0", name="sequence"),
        db.CheckConstraint(
            "arrival >= 0 AND departure >= arrival AND departure < 604800", name="times"
        ),
    )


class Run(db.Model):
    __tablename__ = "runs"
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.ForeignKey("route_variants.id", ondelete="CASCADE"), nullable=False)
    service_date = db.Column(db.Date, nullable=False, index=True)
    route = db.relationship(RouteVariant, back_populates="runs")
    __table_args__ = (db.UniqueConstraint("route_id", "service_date"),)


class TripSource(db.Model):
    __tablename__ = "trip_sources"
    dataset_id = db.Column(db.ForeignKey("datasets.id"), primary_key=True)
    trip_id = db.Column(db.String(240), primary_key=True)
    route_id = db.Column(
        db.ForeignKey("route_variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    gtfs_route_id = db.Column(db.String(200), nullable=False)
    service_id = db.Column(db.String(200), nullable=False)
    block_id = db.Column(db.String(200))
    dates = db.Column(db.JSON, nullable=False)


class TransferRule(db.Model):
    __tablename__ = "transfer_rules"
    id = db.Column(db.Integer, primary_key=True)
    dataset_id = db.Column(db.ForeignKey("datasets.id"), nullable=False)
    from_station_id = db.Column(db.ForeignKey("stations.id"))
    to_station_id = db.Column(db.ForeignKey("stations.id"))
    from_trip_id = db.Column(db.String(240))
    to_trip_id = db.Column(db.String(240))
    from_route_id = db.Column(db.String(200))
    to_route_id = db.Column(db.String(200))
    transfer_type = db.Column("type", db.Integer, nullable=False)
    minimum_seconds = db.Column(db.Integer)
    __table_args__ = (db.CheckConstraint("type BETWEEN 0 AND 5", name="type"),)
