from railway.extensions import db


class Dataset(db.Model):
    __tablename__ = "datasets"
    id = db.Column(db.Integer, primary_key=True)
    fingerprint = db.Column(db.String(64), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False)
    version = db.Column(db.String(200))
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    attributions = db.Column(db.JSON, nullable=False, default=list)
    report = db.Column(db.JSON, nullable=False, default=dict)


class Station(db.Model):
    __tablename__ = "stations"
    id = db.Column(db.Integer, primary_key=True)
    source_key = db.Column(db.String(200), nullable=False, unique=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    __table_args__ = (
        db.CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude"),
        db.CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude"),
    )
