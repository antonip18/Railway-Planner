from railway.extensions import db


class Coupling(db.Model):
    """Two complete inbound runs continue as one outbound run on a specific date."""

    __tablename__ = "couplings"
    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(db.ForeignKey("stations.id"), nullable=False)
    output_run_id = db.Column(db.ForeignKey("runs.id"), nullable=False, unique=True)
    note = db.Column(db.String(300), nullable=False, default="")
    output = db.relationship("Run", foreign_keys=[output_run_id])
    station = db.relationship("Station")
    inputs = db.relationship(
        "CouplingInput",
        cascade="all, delete-orphan",
        order_by="CouplingInput.position",
        back_populates="coupling",
    )


class CouplingInput(db.Model):
    __tablename__ = "coupling_inputs"
    coupling_id = db.Column(db.ForeignKey("couplings.id", ondelete="CASCADE"), primary_key=True)
    run_id = db.Column(db.ForeignKey("runs.id"), primary_key=True, unique=True)
    position = db.Column(db.Integer, nullable=False)
    coupling = db.relationship(Coupling, back_populates="inputs")
    run = db.relationship("Run")
    __table_args__ = (
        db.UniqueConstraint("coupling_id", "position"),
        db.CheckConstraint("position IN (1,2)", name="position"),
    )
