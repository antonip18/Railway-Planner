from railway.extensions import db


class Train(db.Model):
    """A public service identity, not an assertion about a physical vehicle diagram."""

    __tablename__ = "trains"
    id = db.Column(db.Integer, primary_key=True)
    identity = db.Column(db.String(240), nullable=False, unique=True)
    agency = db.Column(db.String(80), nullable=False)
    number = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(40), nullable=False)
    carriages = db.relationship(
        "Carriage",
        back_populates="train",
        order_by="Carriage.position",
        cascade="all, delete-orphan",
    )

    @property
    def label(self):
        return " ".join(p for p in (self.category, self.number, self.name) if p)


class CarriageType(db.Model):
    __tablename__ = "carriage_types"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rows = db.Column(db.Integer, nullable=False)
    columns = db.Column(db.Integer, nullable=False)
    compartment = db.Column(db.Boolean, nullable=False)
    # Layouts are immutable value objects: no separate table needed for every fixture seat.
    layout = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.CheckConstraint("rows > 0 AND columns > 0", name="dimensions"),)


class Carriage(db.Model):
    __tablename__ = "carriages"
    id = db.Column(db.Integer, primary_key=True)
    train_id = db.Column(db.ForeignKey("trains.id", ondelete="CASCADE"), nullable=False)
    type_id = db.Column(db.ForeignKey("carriage_types.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    train = db.relationship(Train, back_populates="carriages")
    carriage_type = db.relationship(CarriageType)
    __table_args__ = (
        db.UniqueConstraint("train_id", "position"),
        db.CheckConstraint("position > 0", name="position"),
    )
