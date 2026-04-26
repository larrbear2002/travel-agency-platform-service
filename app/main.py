from fastapi import FastAPI
from sqlalchemy import inspect, text

from app.core.database import Base, engine
import app.models  # registers all ORM models before create_all

from app.api.v1.router import api_router

Base.metadata.create_all(bind=engine)

# Runtime migrations: add columns that may be missing from pre-existing databases.
def _run_migrations():
    inspector = inspect(engine)
    with engine.connect() as conn:
        existing_user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "Agency_Id" not in existing_user_cols:
            conn.execute(text('ALTER TABLE users ADD COLUMN "Agency_Id" INTEGER'))
            conn.commit()

_run_migrations()

app = FastAPI(
    title="Travel Agency Platform API",
    description=(
        "## Group 2 — Search APIs\n"
        "Search for **Flights**, **Hotels**, and **Attractions** via Booking.com (RapidAPI).\n\n"
        "## Group 2 — Booking & Persistence APIs\n"
        "Create and manage travel **Bookings** with nested Flight, Hotel, and Attraction reservations "
        "persisted to the database.\n\n"
        "### Quick-start\n"
        "1. `POST /api/v1/users/` — create a user.\n"
        "2. Use a Search endpoint to find travel options.\n"
        "3. `POST /api/v1/bookings/` — create a booking using the User_Id from step 1.\n"
    ),
    version="2.0.0",
    contact={"name": "Travel Agency Platform Team"},
)
app.include_router(api_router, prefix="/api/v1")

