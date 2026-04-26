from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.booking import User
from app.models.price_intelligence import PriceAlert, PriceSnapshot
from app.schemas.price_intelligence import (
    AlertCreate,
    AlertResponse,
    DealCheckResponse,
    PriceHistoryResponse,
    PriceSnapshotCreate,
    PriceSnapshotResponse,
)

router = APIRouter()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD_DEAL_THRESHOLD = 0.85   # current <= avg * 0.85  → "Good Deal"
_EXPENSIVE_THRESHOLD = 1.15   # current >= avg * 1.15  → "Expensive"
_MIN_SAMPLES = 3               # need at least this many snapshots for a label


def _compute_label(current_price: float, average_price: float) -> str:
    if current_price <= average_price * _GOOD_DEAL_THRESHOLD:
        return "Good Deal"
    if current_price >= average_price * _EXPENSIVE_THRESHOLD:
        return "Expensive"
    return "Average"


def _check_and_trigger_alerts(
    db: Session,
    from_code: str,
    to_code: str,
    cabin_class: str,
    observed_price: float,
) -> None:
    """Trigger any active alerts whose target price is met (AC5)."""
    alerts = (
        db.query(PriceAlert)
        .filter(
            PriceAlert.from_code == from_code,
            PriceAlert.to_code == to_code,
            PriceAlert.cabin_class == cabin_class,
            PriceAlert.is_active == True,
            PriceAlert.target_price >= observed_price,
        )
        .all()
    )
    for alert in alerts:
        alert.is_active = False
        alert.triggered_at = datetime.utcnow()
        alert.triggered_price = observed_price
    if alerts:
        db.commit()


# ---------------------------------------------------------------------------
# Price Snapshot endpoints  (US.1 / AC2)
# ---------------------------------------------------------------------------

@router.post(
    "/flights/price-snapshot",
    response_model=PriceSnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Price Intelligence"],
    summary="Record a flight price observation",
)
def record_price_snapshot(snapshot: PriceSnapshotCreate, db: Session = Depends(get_db)):
    """
    Manually record an observed price for a route.
    The frontend should call this after displaying search results so that
    historical trend data accumulates over time (US.1).
    Also automatically triggers any matching price alerts (US.2 / AC5).
    """
    db_snap = PriceSnapshot(**snapshot.model_dump())
    db.add(db_snap)
    db.commit()
    db.refresh(db_snap)

    _check_and_trigger_alerts(
        db,
        from_code=snapshot.from_code,
        to_code=snapshot.to_code,
        cabin_class=snapshot.cabin_class,
        observed_price=snapshot.price,
    )
    return db_snap


@router.get(
    "/flights/price-history",
    response_model=PriceHistoryResponse,
    tags=["Price Intelligence"],
    summary="Get historical price trend for a route (US.1 / AC2)",
)
def get_price_history(
    from_code: str = Query(..., description="Origin code, e.g. LAX.AIRPORT"),
    to_code: str = Query(..., description="Destination code, e.g. NYC.CITY"),
    cabin_class: str = Query("ECONOMY"),
    months: int = Query(6, ge=1, le=24, description="How many months of history to return"),
    db: Session = Depends(get_db),
):
    """
    Returns time-series price observations for a route over the requested
    number of months.  The frontend uses this data to render the line chart
    required by AC2/AC3.

    Each snapshot includes `recorded_at` (timestamp) and `price` so the
    chart tooltip can show the exact price and date on hover (AC3).
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    snapshots = (
        db.query(PriceSnapshot)
        .filter(
            PriceSnapshot.from_code == from_code,
            PriceSnapshot.to_code == to_code,
            PriceSnapshot.cabin_class == cabin_class,
            PriceSnapshot.recorded_at >= cutoff,
        )
        .order_by(PriceSnapshot.recorded_at.asc())
        .all()
    )
    return PriceHistoryResponse(
        from_code=from_code,
        to_code=to_code,
        cabin_class=cabin_class,
        months=months,
        snapshots=snapshots,
    )


# ---------------------------------------------------------------------------
# Deal Check endpoint  (US.3 / AC7-8)
# ---------------------------------------------------------------------------

@router.get(
    "/flights/deal-check",
    response_model=DealCheckResponse,
    tags=["Price Intelligence"],
    summary="Compare a price against historical average and get a deal label (US.3 / AC7-8)",
)
def deal_check(
    from_code: str = Query(...),
    to_code: str = Query(...),
    current_price: float = Query(..., gt=0, description="The price you want to evaluate"),
    cabin_class: str = Query("ECONOMY"),
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """
    Compares `current_price` against the average of stored historical prices
    for the same route.

    **Labels (AC8):**
    - **Good Deal** — current price is ≤ 85% of the historical average
    - **Average** — within ±15% of the historical average
    - **Expensive** — current price is ≥ 115% of the historical average
    - **Insufficient Data** — fewer than 3 snapshots on record
    """
    cutoff = datetime.utcnow() - timedelta(days=months * 30)
    snapshots = (
        db.query(PriceSnapshot)
        .filter(
            PriceSnapshot.from_code == from_code,
            PriceSnapshot.to_code == to_code,
            PriceSnapshot.cabin_class == cabin_class,
            PriceSnapshot.recorded_at >= cutoff,
        )
        .all()
    )

    sample_count = len(snapshots)

    if sample_count < _MIN_SAMPLES:
        return DealCheckResponse(
            from_code=from_code,
            to_code=to_code,
            cabin_class=cabin_class,
            current_price=current_price,
            average_price=None,
            sample_count=sample_count,
            label="Insufficient Data",
            description=(
                f"Only {sample_count} price observation(s) on record. "
                f"At least {_MIN_SAMPLES} are needed for a reliable comparison."
            ),
        )

    average_price = sum(s.price for s in snapshots) / sample_count
    label = _compute_label(current_price, average_price)

    descriptions = {
        "Good Deal": f"${current_price:.2f} is at least 15% below the {months}-month average of ${average_price:.2f}.",
        "Average": f"${current_price:.2f} is within 15% of the {months}-month average of ${average_price:.2f}.",
        "Expensive": f"${current_price:.2f} is at least 15% above the {months}-month average of ${average_price:.2f}.",
    }

    return DealCheckResponse(
        from_code=from_code,
        to_code=to_code,
        cabin_class=cabin_class,
        current_price=current_price,
        average_price=round(average_price, 2),
        sample_count=sample_count,
        label=label,
        description=descriptions[label],
    )


# ---------------------------------------------------------------------------
# Price Alert endpoints  (US.2 / AC4-6)
# ---------------------------------------------------------------------------

@router.post(
    "/alerts/",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Price Alerts"],
    summary="Set a price alert for a flight route (US.2 / AC4)",
)
def create_alert(alert: AlertCreate, db: Session = Depends(get_db)):
    """
    Create a price alert. When a price at or below `target_price` is observed
    for the given route (via `/flights/price-snapshot` or the flight search
    auto-record), the alert is triggered and `is_active` becomes `false` (AC5).

    **Note:** Email / push delivery (AC6) requires an external notification
    service wired to the `triggered_at` field — poll `GET /alerts/?user_id=`
    for triggered alerts in the meantime.
    """
    user = db.query(User).filter(User.User_ID == alert.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail=f"User {alert.user_id} does not exist.")

    db_alert = PriceAlert(**alert.model_dump())
    db.add(db_alert)
    db.commit()
    db.refresh(db_alert)
    return db_alert


@router.get(
    "/alerts/",
    response_model=list[AlertResponse],
    tags=["Price Alerts"],
    summary="List price alerts for a user",
)
def list_alerts(
    user_id: int = Query(..., description="Filter alerts by user"),
    active_only: bool = Query(False, description="Return only unresolved alerts"),
    db: Session = Depends(get_db),
):
    """
    Returns all alerts for a user.  Set `active_only=true` to see only
    alerts still waiting to fire; set `active_only=false` (default) to
    also see already-triggered alerts (in-app notification source, AC6).
    """
    q = db.query(PriceAlert).filter(PriceAlert.user_id == user_id)
    if active_only:
        q = q.filter(PriceAlert.is_active == True)
    return q.order_by(PriceAlert.created_at.desc()).all()


@router.delete(
    "/alerts/{alert_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Price Alerts"],
    summary="Delete a price alert",
)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(PriceAlert).filter(PriceAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found.")
    db.delete(alert)
    db.commit()
    return None
