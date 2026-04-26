from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---- Price Snapshot ----

class PriceSnapshotCreate(BaseModel):
    from_code: str = Field(..., description="Origin code, e.g. LAX.AIRPORT")
    to_code: str = Field(..., description="Destination code, e.g. NYC.CITY")
    depart_date: str = Field(..., description="Format: YYYY-MM-DD")
    cabin_class: str = Field("ECONOMY", description="ECONOMY | BUSINESS | FIRST")
    price: float = Field(..., gt=0, description="Observed price in the search currency")


class PriceSnapshotResponse(PriceSnapshotCreate):
    id: int
    recorded_at: datetime

    class Config:
        from_attributes = True


class PriceHistoryResponse(BaseModel):
    from_code: str
    to_code: str
    cabin_class: str
    months: int
    snapshots: list[PriceSnapshotResponse]


# ---- Deal Check (US.3 / AC7-8) ----

DealLabel = Literal["Good Deal", "Average", "Expensive", "Insufficient Data"]


class DealCheckResponse(BaseModel):
    from_code: str
    to_code: str
    cabin_class: str
    current_price: float
    average_price: Optional[float] = None
    sample_count: int
    label: DealLabel
    description: str


# ---- Price Alerts (US.2 / AC4-6) ----

class AlertCreate(BaseModel):
    user_id: int
    from_code: str = Field(..., description="Origin code, e.g. LAX.AIRPORT")
    to_code: str = Field(..., description="Destination code, e.g. NYC.CITY")
    cabin_class: str = Field("ECONOMY")
    target_price: float = Field(..., gt=0, description="Alert fires when price drops at or below this value")


class AlertResponse(BaseModel):
    id: int
    user_id: int
    from_code: str
    to_code: str
    cabin_class: str
    target_price: float
    is_active: bool
    created_at: datetime
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None

    class Config:
        from_attributes = True
