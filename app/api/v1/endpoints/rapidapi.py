from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints.price_intelligence import _check_and_trigger_alerts
from app.core.database import get_db
from app.core.rapidapi_client import RapidApiError, get_rapidapi_client
from app.models.price_intelligence import PriceSnapshot
from app.services.rapidapi_service import RapidApiService

router = APIRouter()

def get_rapidapi_service() -> RapidApiService:
    return RapidApiService(get_rapidapi_client())


def _extract_min_price(data: object) -> float | None:
    """Best-effort extraction of the lowest price from a booking.com flight response."""
    prices: list[float] = []
    try:
        offers = data.get("flightOffers") or data.get("data", {}).get("flightOffers", [])
        for offer in offers or []:
            pb = offer.get("priceBreakdown", {})
            total = pb.get("total", {})
            if "units" in total:
                prices.append(float(total["units"]) + float(total.get("nanos", 0)) / 1e9)
    except Exception:
        pass
    return min(prices) if prices else None


@router.get("/locations/search", tags=["Search - Locations"], summary="Resolve a city name to Booking.com dest_ids")
async def search_locations(
    name: str = Query(..., description="City or place name, e.g. 'New York'"),
    locale: str = Query("en-gb"),
    service: RapidApiService = Depends(get_rapidapi_service),
):
    """
    Returns Booking.com location entries (with `dest_id`, `dest_type`, `name`, etc.)
    for the given query. Use this to convert a city name into a `dest_id` before
    calling /hotels/search or /attractions/search.
    """
    try:
        return service.search_locations(name=name, locale=locale)
    except RapidApiError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/attractions/search", tags=["Search - Attractions"])
async def search_attractions(
    start_date: str = Query(..., description="Format: YYYY-MM-DD"),
    end_date: str = Query(..., description="Format: YYYY-MM-DD"),
    dest_id: str = Query(..., description="Destination ID, e.g. 20088325"),
    locale: str = Query("en-gb"),
    page_number: int = Query(0, ge=0),
    currency: str = Query("AED"),
    order_by: str = Query("attr_book_score"),
    service: RapidApiService = Depends(get_rapidapi_service),
):
    try:
        return service.search_attractions(
            start_date=start_date,
            end_date=end_date,
            dest_id=dest_id,
            locale=locale,
            page_number=page_number,
            currency=currency,
            order_by=order_by,
        )
    except RapidApiError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/hotels/search", tags=["Search - Hotels"])
async def search_hotels(
    page_number: int = Query(0, ge=0),
    dest_type: str = Query("city"),
    dest_id: str = Query(..., description="Example: -553173"),
    units: str = Query("metric"),
    children_number: int = Query(0, ge=0),
    locale: str = Query("en-gb"),
    categories_filter_ids: str | None = Query(None),
    children_ages: str | None = Query(None, description="Comma-separated ages, e.g. 5,0"),
    include_adjacency: bool = Query(True),
    filter_by_currency: str = Query("AED"),
    order_by: str = Query("popularity"),
    checkin_date: str = Query(..., description="Format: YYYY-MM-DD"),
    checkout_date: str = Query(..., description="Format: YYYY-MM-DD"),
    room_number: int = Query(1, ge=1),
    adults_number: int = Query(1, ge=1),
    service: RapidApiService = Depends(get_rapidapi_service),
):
    try:
        return service.search_hotels(
            page_number=page_number,
            dest_type=dest_type,
            dest_id=dest_id,
            units=units,
            children_number=children_number,
            locale=locale,
            categories_filter_ids=categories_filter_ids,
            children_ages=children_ages,
            include_adjacency=include_adjacency,
            filter_by_currency=filter_by_currency,
            order_by=order_by,
            checkin_date=checkin_date,
            checkout_date=checkout_date,
            room_number=room_number,
            adults_number=adults_number,
        )
    except RapidApiError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error


@router.get("/flights/search", tags=["Search - Flights"])
async def search_flights(
    depart_date: str = Query(..., description="Format: YYYY-MM-DD"),
    from_code: str = Query(..., description="Example: ONT.AIRPORT"),
    to_code: str = Query(..., description="Example: NYC.CITY"),
    adults: int = Query(1, ge=1),
    locale: str = Query("en-gb"),
    page_number: int = Query(0, ge=0),
    currency: str = Query("AED"),
    order_by: str = Query("BEST"),
    flight_type: str = Query("ONEWAY"),
    cabin_class: str = Query("ECONOMY"),
    children_ages: str | None = Query(None, description="Comma-separated ages, e.g. 5,0"),
    return_date: str | None = Query(None, description="Format: YYYY-MM-DD"),
    service: RapidApiService = Depends(get_rapidapi_service),
    db: Session = Depends(get_db),
):
    try:
        result = service.search_flights(
            depart_date=depart_date,
            from_code=from_code,
            to_code=to_code,
            adults=adults,
            locale=locale,
            page_number=page_number,
            currency=currency,
            order_by=order_by,
            flight_type=flight_type,
            cabin_class=cabin_class,
            children_ages=children_ages,
            return_date=return_date,
        )
    except RapidApiError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error

    # Auto-record the lowest observed price for trend history (US.1 / AC2)
    # and check if any price alerts should fire (US.2 / AC5).
    min_price = _extract_min_price(result)
    if min_price is not None:
        db.add(PriceSnapshot(
            from_code=from_code,
            to_code=to_code,
            depart_date=depart_date,
            cabin_class=cabin_class,
            price=min_price,
            recorded_at=datetime.utcnow(),
        ))
        db.commit()
        _check_and_trigger_alerts(db, from_code, to_code, cabin_class, min_price)

    return result


@router.get("/flights/price-calendar", tags=["Price Intelligence"])
async def get_flight_price_calendar(
    from_code: str = Query(..., description="Origin code, e.g. LAX.AIRPORT"),
    to_code: str = Query(..., description="Destination code, e.g. JFK.AIRPORT"),
    year_month: str = Query(..., description="Format: YYYY-MM, e.g. 2026-06"),
    cabin_class: str = Query("ECONOMY", description="ECONOMY | BUSINESS | FIRST"),
    currency: str = Query("USD"),
    service: RapidApiService = Depends(get_rapidapi_service),
    db: Session = Depends(get_db),
):
    """
    Returns the cheapest price for a sample of dates across the requested month.
    Searches the 1st and 15th of the month (2 data points) using the live
    Booking.com flight search, then records each price as a snapshot.
    """
    import calendar
    from datetime import date

    try:
        year, month = int(year_month[:4]), int(year_month[5:7])
    except (ValueError, IndexError):
        raise HTTPException(status_code=422, detail="year_month must be in YYYY-MM format, e.g. 2026-06")

    _, days_in_month = calendar.monthrange(year, month)
    sample_days = [1, min(15, days_in_month)]

    results = []
    for day in sample_days:
        depart_date = date(year, month, day).isoformat()
        try:
            result = service.search_flights(
                depart_date=depart_date,
                from_code=from_code,
                to_code=to_code,
                adults=1,
                cabin_class=cabin_class,
                currency=currency,
                locale="en-gb",
                page_number=0,
                order_by="BEST",
                flight_type="ONEWAY",
            )
            min_price = _extract_min_price(result)
            if min_price is not None:
                db.add(PriceSnapshot(
                    from_code=from_code,
                    to_code=to_code,
                    depart_date=depart_date,
                    cabin_class=cabin_class,
                    price=min_price,
                    recorded_at=datetime.utcnow(),
                ))
                _check_and_trigger_alerts(db, from_code, to_code, cabin_class, min_price)
            results.append({"date": depart_date, "price": min_price})
        except RapidApiError:
            results.append({"date": depart_date, "price": None})

    db.commit()
    return {
        "from_code": from_code,
        "to_code": to_code,
        "cabin_class": cabin_class,
        "currency": currency,
        "year_month": year_month,
        "prices": results,
    }


@router.get("/flights/price-forecast", tags=["Price Intelligence"])
async def get_flight_price_forecast(
    from_code: str = Query(..., description="Origin code, e.g. SFO.AIRPORT"),
    to_code: str = Query(..., description="Destination code, e.g. CDG.AIRPORT"),
    months: int = Query(6, ge=1, le=12, description="How many months ahead to scan (max 12)"),
    cabin_class: str = Query("ECONOMY", description="ECONOMY | BUSINESS | FIRST"),
    currency: str = Query("USD"),
    service: RapidApiService = Depends(get_rapidapi_service),
    db: Session = Depends(get_db),
):
    """
    **Early-Bird Planner endpoint.**

    Fetches the cheapest flight price on the 1st of each month for the next
    `months` months, saves every price as a snapshot, then immediately runs a
    deal assessment so the user knows whether prices are trending up or down
    and whether now is a good time to book.

    Designed for users planning trips 6 months in advance (US.1 / US.3 / AC2 / AC7-8).
    Note: makes one live API call per month — allow a few seconds to respond.
    """
    from datetime import date
    from app.api.v1.endpoints.price_intelligence import _compute_label

    today = date.today()
    monthly_prices = []

    for i in range(months):
        month_offset = today.month + i
        year = today.year + (month_offset - 1) // 12
        month = ((month_offset - 1) % 12) + 1
        depart_date = date(year, month, 1).isoformat()

        try:
            result = service.search_flights(
                depart_date=depart_date,
                from_code=from_code,
                to_code=to_code,
                adults=1,
                cabin_class=cabin_class,
                currency=currency,
                locale="en-gb",
                page_number=0,
                order_by="BEST",
                flight_type="ONEWAY",
            )
            min_price = _extract_min_price(result)
            if min_price is not None:
                db.add(PriceSnapshot(
                    from_code=from_code,
                    to_code=to_code,
                    depart_date=depart_date,
                    cabin_class=cabin_class,
                    price=min_price,
                    recorded_at=datetime.utcnow(),
                ))
                _check_and_trigger_alerts(db, from_code, to_code, cabin_class, min_price)
            monthly_prices.append({"month": f"{year}-{month:02d}", "cheapest_price": min_price})
        except RapidApiError:
            monthly_prices.append({"month": f"{year}-{month:02d}", "cheapest_price": None})

    db.commit()

    valid_prices = [p["cheapest_price"] for p in monthly_prices if p["cheapest_price"] is not None]
    deal_summary = None
    if len(valid_prices) >= 2:
        average = round(sum(valid_prices) / len(valid_prices), 2)
        lowest = min(valid_prices)
        highest = max(valid_prices)
        best_month = next(p["month"] for p in monthly_prices if p["cheapest_price"] == lowest)
        label = _compute_label(lowest, average)
        deal_summary = {
            "average_price": average,
            "lowest_price": lowest,
            "highest_price": highest,
            "best_month_to_book": best_month,
            "label": label,
            "advice": (
                f"The cheapest month is {best_month} at ${lowest:.2f}. "
                f"The 6-month average is ${average:.2f}. "
                f"Booking in {best_month} is a '{label}'."
            ),
        }

    return {
        "from_code": from_code,
        "to_code": to_code,
        "cabin_class": cabin_class,
        "currency": currency,
        "months_scanned": months,
        "monthly_prices": monthly_prices,
        "deal_summary": deal_summary,
    }
