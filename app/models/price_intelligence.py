from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String

from app.core.database import Base


class PriceSnapshot(Base):
    """Records a price observation for a flight route at a point in time (US.1 / AC2)."""
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_code = Column(String, nullable=False, index=True)
    to_code = Column(String, nullable=False, index=True)
    depart_date = Column(String, nullable=False)  # YYYY-MM-DD
    cabin_class = Column(String, nullable=False, default="ECONOMY")
    price = Column(Float, nullable=False)
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PriceAlert(Base):
    """A user-defined price target for a route (US.2 / AC4-6)."""
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    from_code = Column(String, nullable=False)
    to_code = Column(String, nullable=False)
    cabin_class = Column(String, nullable=False, default="ECONOMY")
    target_price = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    triggered_at = Column(DateTime, nullable=True)
    triggered_price = Column(Float, nullable=True)
