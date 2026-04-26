from typing import List
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.database import get_db
from app.models.booking import Booking, User, HotelReservation, FlightReservation, AttractionReservation
from app.schemas.booking import (
    BookingResponse,
    BookingDetailResponse,
    BookingCreate,
    BookingUpdate,
    HotelReservationResponse,
    FlightReservationResponse,
    HotelReservationUpdate,
    FlightReservationUpdate,
    AttractionReservationResponse,
    AttractionReservationUpdate,
    UserCreate,
    UserResponse,
)

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError


router = APIRouter(tags=["Bookings"])

# ==========================================
# USER ENDPOINTS
# ==========================================

@router.post("/users/", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="Create a new user")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Register a new traveler. The returned **User_Id** is required when creating a booking.
    """
    existing = db.query(User).filter(User.Email == user.Email).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Email '{user.Email}' is already registered.")
    db_user = User(**user.model_dump())
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not create user — email may already exist.") from exc
    db.refresh(db_user)
    return db_user


@router.get("/users/", response_model=List[UserResponse], summary="List all users")
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Retrieve all registered users (paginated)."""
    return db.query(User).offset(skip).limit(limit).all()


# ==========================================
# ENDPOINTS (CRUD)
# ==========================================

# 1. READ: Get all Bookings (with pagination)
@router.get("/bookings/", response_model=List[BookingResponse], summary="List all bookings")
def read_bookings(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Retrieve a list of bookings. Use 'skip' and 'limit' for pagination.
    """
    bookings = db.query(Booking).offset(skip).limit(limit).all()
    return bookings

# 2. READ: Get a specific Booking by ID (with full details)
@router.get("/bookings/{booking_id}", response_model=BookingDetailResponse, summary="Get booking details")
def read_booking(booking_id: int, db: Session = Depends(get_db)):
    """
    Retrieve detailed information about a specific booking, including user details.
    """
    db_booking = db.query(Booking).filter(Booking.Booking_Id == booking_id).first()
    if db_booking is None:
        raise HTTPException(status_code=404, detail=f"Booking with ID {booking_id} not found")
    return db_booking

@router.post("/bookings/", response_model=BookingDetailResponse, status_code=status.HTTP_201_CREATED, summary="Create a new booking")
def create_booking(booking: BookingCreate, db: Session = Depends(get_db)):
    """
    Create a new travel booking.
    * **User_Id** must refer to an existing user (create one via `POST /users/` first).
    * Optionally include **hotel_reservations**, **flight_reservations**, and/or **attraction_reservations** in the same request.
    """
    user_exists = db.query(User).filter(User.User_ID == booking.User_Id).first()
    if not user_exists:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot create booking. User_Id {booking.User_Id} does not exist.",
        )

    booking_data = booking.model_dump(
        exclude={"hotel_reservations", "flight_reservations", "attraction_reservations"}
    )
    db_booking = Booking(**booking_data)
    db.add(db_booking)
    db.flush()

    for hotel in booking.hotel_reservations:
        db.add(HotelReservation(Booking_Id=db_booking.Booking_Id, **hotel.model_dump()))

    for flight in booking.flight_reservations:
        db.add(FlightReservation(Booking_Id=db_booking.Booking_Id, **flight.model_dump()))

    for attraction in booking.attraction_reservations:
        db.add(AttractionReservation(Booking_Id=db_booking.Booking_Id, **attraction.model_dump()))

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Could not save booking — check reservation data.") from exc

    db.refresh(db_booking)
    return db_booking

# 4. UPDATE: Modify an existing Booking
@router.patch("/bookings/{booking_id}", response_model=BookingResponse, summary="Update an existing booking")
def update_booking(booking_id: int, booking_update: BookingUpdate, db: Session = Depends(get_db)):
    """
    Update specific fields (dates or agent) of an existing booking. 
    Only fields provided in the request body will be changed.
    """
    db_booking = db.query(Booking).filter(Booking.Booking_Id == booking_id).first()
    if db_booking is None:
        raise HTTPException(status_code=404, detail=f"Booking with ID {booking_id} not found")

    # Extract update data, excluding fields set to None
    update_data = booking_update.model_dump(exclude_unset=True)
    
    # Apply updates to the model
    for key, value in update_data.items():
        setattr(db_booking, key, value)

    db.commit()
    db.refresh(db_booking)
    return db_booking

# 5. DELETE: Remove an existing Booking
@router.delete("/bookings/{booking_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a booking")
def delete_booking(booking_id: int, db: Session = Depends(get_db)):
    """
    permanently delete a booking from the system.
    """
    db_booking = db.query(Booking).filter(Booking.Booking_Id == booking_id).first()
    if db_booking is None:
        raise HTTPException(status_code=404, detail=f"Booking with ID {booking_id} not found")

    db.delete(db_booking)
    db.commit()
    return None # HTTP 204 requires no content


# 6. UPDATE: Modify a hotel reservation under a booking
@router.patch(
    "/bookings/{booking_id}/hotel-reservations/{reservation_no}",
    response_model=HotelReservationResponse,
    summary="Update a hotel reservation",
)
def update_hotel_reservation(
    booking_id: int,
    reservation_no: int,
    reservation_update: HotelReservationUpdate = Body(
        ...,
        examples={
            "change_stay_dates": {
                "summary": "Change check-in/check-out dates",
                "value": {
                    "Check_In_Date": "2026-06-11",
                    "Check_Out_Date": "2026-06-20"
                },
            },
            "change_rate_and_hotel": {
                "summary": "Move to a different hotel and update rate",
                "value": {
                    "Hotel_Code": 3,
                    "Rate": 349.99
                },
            },
        },
    ),
    db: Session = Depends(get_db),
):
    db_reservation = (
        db.query(HotelReservation)
        .filter(
            HotelReservation.Reservation_No == reservation_no,
            HotelReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel reservation {reservation_no} not found for booking {booking_id}",
        )

    update_data = reservation_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_reservation, key, value)

    db.commit()
    db.refresh(db_reservation)
    return db_reservation


# 7. DELETE: Remove a hotel reservation under a booking
@router.delete(
    "/bookings/{booking_id}/hotel-reservations/{reservation_no}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a hotel reservation",
)
def delete_hotel_reservation(booking_id: int, reservation_no: int, db: Session = Depends(get_db)):
    db_reservation = (
        db.query(HotelReservation)
        .filter(
            HotelReservation.Reservation_No == reservation_no,
            HotelReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Hotel reservation {reservation_no} not found for booking {booking_id}",
        )

    db.delete(db_reservation)
    db.commit()
    return None


# 8. UPDATE: Modify a flight reservation under a booking
@router.patch(
    "/bookings/{booking_id}/flight-reservations/{reservation_no}",
    response_model=FlightReservationResponse,
    summary="Update a flight reservation",
)
def update_flight_reservation(
    booking_id: int,
    reservation_no: int,
    reservation_update: FlightReservationUpdate = Body(
        ...,
        examples={
            "change_departure_time": {
                "summary": "Update departure date and time",
                "value": {
                    "Departure_Date": "2026-06-10",
                    "Departure_Time": "20:15"
                },
            },
            "change_route_and_airline": {
                "summary": "Switch airline and destination airport",
                "value": {
                    "Airline_Code": "DL",
                    "Destination_Airport_Code": "LAX"
                },
            },
        },
    ),
    db: Session = Depends(get_db),
):
    db_reservation = (
        db.query(FlightReservation)
        .filter(
            FlightReservation.Reservation_No == reservation_no,
            FlightReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Flight reservation {reservation_no} not found for booking {booking_id}",
        )

    update_data = reservation_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_reservation, key, value)

    db.commit()
    db.refresh(db_reservation)
    return db_reservation


# 9. DELETE: Remove a flight reservation under a booking
@router.delete(
    "/bookings/{booking_id}/flight-reservations/{reservation_no}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a flight reservation",
)
def delete_flight_reservation(booking_id: int, reservation_no: int, db: Session = Depends(get_db)):
    db_reservation = (
        db.query(FlightReservation)
        .filter(
            FlightReservation.Reservation_No == reservation_no,
            FlightReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Flight reservation {reservation_no} not found for booking {booking_id}",
        )

    db.delete(db_reservation)
    db.commit()
    return None


# 10. UPDATE: Modify an attraction reservation under a booking
@router.patch(
    "/bookings/{booking_id}/attraction-reservations/{reservation_no}",
    response_model=AttractionReservationResponse,
    summary="Update an attraction reservation",
)
def update_attraction_reservation(
    booking_id: int,
    reservation_no: int,
    reservation_update: AttractionReservationUpdate,
    db: Session = Depends(get_db),
):
    db_reservation = (
        db.query(AttractionReservation)
        .filter(
            AttractionReservation.Reservation_No == reservation_no,
            AttractionReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Attraction reservation {reservation_no} not found for booking {booking_id}",
        )

    for key, value in reservation_update.model_dump(exclude_unset=True).items():
        setattr(db_reservation, key, value)

    db.commit()
    db.refresh(db_reservation)
    return db_reservation


# 11. DELETE: Remove an attraction reservation under a booking
@router.delete(
    "/bookings/{booking_id}/attraction-reservations/{reservation_no}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an attraction reservation",
)
def delete_attraction_reservation(booking_id: int, reservation_no: int, db: Session = Depends(get_db)):
    db_reservation = (
        db.query(AttractionReservation)
        .filter(
            AttractionReservation.Reservation_No == reservation_no,
            AttractionReservation.Booking_Id == booking_id,
        )
        .first()
    )
    if db_reservation is None:
        raise HTTPException(
            status_code=404,
            detail=f"Attraction reservation {reservation_no} not found for booking {booking_id}",
        )

    db.delete(db_reservation)
    db.commit()
    return None
