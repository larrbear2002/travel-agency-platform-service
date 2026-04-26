# ==========================================
# SQLALCHEMY MODELS (Zone 2 of ERD)
# ==========================================

from sqlalchemy import Column, Integer, String, ForeignKey, Date, Float
from sqlalchemy.orm import relationship
from app.core.database import Base # Import Base from your core config

class User(Base):
    __tablename__ = "users"
    User_ID = Column(Integer, primary_key=True, index=True, autoincrement=True)
    First_Name = Column(String, nullable=False)
    Last_Name = Column(String, nullable=False)
    Email = Column(String, unique=True, nullable=False, index=True)
    Phone_Number = Column(String)
    # AC1: tenant isolation — 1 = Agency A, 2 = Agency B, etc.
    Agency_Id = Column(Integer, nullable=True, index=True)

    bookings = relationship("Booking", back_populates="user")

class Booking(Base):
    __tablename__ = "bookings"
    Booking_Id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    User_Id = Column(Integer, ForeignKey("users.User_ID"), nullable=False)
    Agent_Id = Column(Integer, nullable=True)
    Start_Date = Column(Date, nullable=False)
    End_Date = Column(Date, nullable=False)

    user = relationship("User", back_populates="bookings")
    hotel_reservations = relationship("HotelReservation", back_populates="booking", cascade="all, delete-orphan")
    flight_reservations = relationship("FlightReservation", back_populates="booking", cascade="all, delete-orphan")
    attraction_reservations = relationship("AttractionReservation", back_populates="booking", cascade="all, delete-orphan")


class HotelReservation(Base):
    __tablename__ = "hotel_reservations"
    Reservation_No = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Booking_Id = Column(Integer, ForeignKey("bookings.Booking_Id"), nullable=False)
    Hotel_Code = Column(Integer, nullable=False)
    Check_In_Date = Column(Date, nullable=False)
    Check_In_Time = Column(String, nullable=True)
    Check_Out_Date = Column(Date, nullable=False)
    Check_Out_Time = Column(String, nullable=True)
    Rate = Column(Float, nullable=True)

    booking = relationship("Booking", back_populates="hotel_reservations")


class FlightReservation(Base):
    __tablename__ = "flight_reservations"
    Reservation_No = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Booking_Id = Column(Integer, ForeignKey("bookings.Booking_Id"), nullable=False)
    Airline_Code = Column(String, nullable=False)
    Flight_Number = Column(String, nullable=False)
    Departure_Date = Column(Date, nullable=False)
    Departure_Time = Column(String, nullable=False)
    Arrive_Date = Column(Date, nullable=False)
    Arrive_Time = Column(String, nullable=False)
    Rate = Column(Float, nullable=True)
    Origin_Airport_Code = Column(String, nullable=False)
    Destination_Airport_Code = Column(String, nullable=False)

    booking = relationship("Booking", back_populates="flight_reservations")


class AttractionReservation(Base):
    __tablename__ = "attraction_reservations"
    Reservation_No = Column(Integer, primary_key=True, index=True, autoincrement=True)
    Booking_Id = Column(Integer, ForeignKey("bookings.Booking_Id"), nullable=False)
    Attraction_Name = Column(String, nullable=False)
    Visit_Date = Column(Date, nullable=False)
    Ticket_Type = Column(String, nullable=True)
    Rate = Column(Float, nullable=True)

    booking = relationship("Booking", back_populates="attraction_reservations")

