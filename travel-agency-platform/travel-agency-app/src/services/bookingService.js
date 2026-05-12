import api from './api.js'

const BOOKING_USER_ID_STORAGE_KEY = 'booking_user_id'

function normalizeDate(value, fallback = '') {
  if (!value) return fallback
  const normalized = new Date(value)
  if (Number.isNaN(normalized.getTime())) return String(value)
  return normalized.toISOString().split('T')[0]
}

function normalizeTime(value, fallback = '00:00') {
  const raw = String(value || '').trim()
  if (!raw) return `${fallback}:00`

  const clockMatch = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (clockMatch) {
    const hours = String(Math.min(23, Math.max(0, Number(clockMatch[1])))).padStart(2, '0')
    const minutes = String(Math.min(59, Math.max(0, Number(clockMatch[2])))).padStart(2, '0')
    const seconds = String(Math.min(59, Math.max(0, Number(clockMatch[3] || 0)))).padStart(2, '0')
    return `${hours}:${minutes}:${seconds}`
  }

  return `${fallback}:00`
}

function splitFlightNumber(value) {
  const raw = String(value || '').trim().toUpperCase()
  const match = raw.match(/^([A-Z]{2,3})\s*-?(\d{1,4}[A-Z]?)$/)
  if (match) {
    return {
      airlineCode: match[1],
      flightNumber: match[2],
    }
  }

  return {
    airlineCode: '',
    flightNumber: raw,
  }
}

function normalizeAirportCode(value) {
  const code = String(value || '').trim().toUpperCase().replace(/[^A-Z]/g, '')
  return code.slice(0, 3)
}

function toFlightReservations(payload) {
  const flights = []

  if (payload.flight?.outbound) {
    flights.push(payload.flight.outbound)
  } else if (payload.flight) {
    flights.push(payload.flight)
  }

  if (payload.flight?.return) {
    flights.push(payload.flight.return)
  } else if (payload.returnFlight) {
    flights.push(payload.returnFlight)
  }

  return flights.map((flight) => {
    const split = splitFlightNumber(flight.flightNumber)
    const airlineCode = split.airlineCode || normalizeAirportCode(flight.airline).slice(0, 2)

    return {
      Airline_Code: airlineCode,
      Flight_Number: split.flightNumber,
      Departure_Date: normalizeDate(flight.date, normalizeDate(payload.searchParams?.fromDate)),
      Departure_Time: normalizeTime(flight.departureTime),
      Arrive_Date: normalizeDate(flight.date, normalizeDate(payload.searchParams?.fromDate)),
      Arrive_Time: normalizeTime(flight.arrivalTime),
      Rate: Number(flight.totalPrice ?? 0),
      Origin_Airport_Code: normalizeAirportCode(flight.origin || payload.searchParams?.origin),
      Destination_Airport_Code: normalizeAirportCode(flight.destination || payload.searchParams?.destination),
    }
  })
}

function toAttractionReservations(payload) {
  if (!Array.isArray(payload.activities) || payload.activities.length === 0) return []

  const fallbackDate = normalizeDate(payload.searchParams?.fromDate)

  return payload.activities.map((activity) => ({
    Attraction_Name: String(activity.name || activity.title || 'Attraction'),
    Visit_Date: normalizeDate(activity.date, fallbackDate),
    Ticket_Type: activity.ticketType || activity.category || null,
    Rate: Number(activity.totalPrice ?? activity.price ?? 0),
  }))
}

function toHotelReservations(payload) {
  if (!payload.hotel) return []

  const hotelCode = Number.parseInt(String(payload.hotel.id ?? ''), 10)

  return [
    {
      Hotel_Code: Number.isFinite(hotelCode) ? hotelCode : 0,
      Check_In_Date: normalizeDate(payload.hotel.checkIn, normalizeDate(payload.searchParams?.fromDate)),
      Check_In_Time: normalizeTime(payload.hotel.checkInTime),
      Check_Out_Date: normalizeDate(payload.hotel.checkOut, normalizeDate(payload.searchParams?.toDate || payload.searchParams?.fromDate)),
      Check_Out_Time: normalizeTime(payload.hotel.checkOutTime),
      Rate: Number(payload.hotel.totalPrice ?? 0),
    },
  ]
}

async function resolveUserId(payload) {
  const explicitUserId = Number(payload.userId)
  if (Number.isInteger(explicitUserId) && explicitUserId > 0) return explicitUserId

  const cachedUserId = Number(localStorage.getItem(BOOKING_USER_ID_STORAGE_KEY))
  if (Number.isInteger(cachedUserId) && cachedUserId > 0) return cachedUserId

  throw new Error('Please sign in first before booking.')
}

function buildBookingPayload(payload, userId) {
  const startDate = normalizeDate(payload.searchParams?.fromDate)
  const endDate = normalizeDate(payload.searchParams?.toDate || payload.searchParams?.fromDate)
  const agentId = Number(payload.agentId)

  return {
    User_Id: userId,
    Agent_Id: Number.isInteger(agentId) && agentId > 0 ? agentId : null,
    Start_Date: startDate,
    End_Date: endDate,
    hotel_reservations: toHotelReservations(payload),
    flight_reservations: toFlightReservations(payload),
    attraction_reservations: toAttractionReservations(payload),
  }
}

function normalizeBookingResponse(response) {
  const bookingReference = response?.bookingReference
    || response?.Booking_Reference
    || response?.reference
    || response?.Reference
    || response?.booking_id
    || response?.Booking_Id
    || response?.id
    || response?.Id

  return {
    success: true,
    bookingReference: bookingReference ? String(bookingReference) : '',
    message: response?.message || response?.Message || 'Your booking has been confirmed!',
    createdAt: response?.createdAt || response?.Created_At || new Date().toISOString(),
    ...response,
  }
}

function normalizeBookingRecord(record) {
  return {
    bookingId: Number(record?.Booking_Id ?? record?.booking_id ?? record?.id ?? 0) || 0,
    userId: Number(record?.User_Id ?? record?.userId ?? 0) || 0,
    agentId: Number(record?.Agent_Id ?? record?.agentId ?? 0) || 0,
    startDate: normalizeDate(record?.Start_Date ?? record?.startDate),
    endDate: normalizeDate(record?.End_Date ?? record?.endDate),
    user: record?.user || null,
    hotelReservations: Array.isArray(record?.hotel_reservations) ? record.hotel_reservations : [],
    flightReservations: Array.isArray(record?.flight_reservations) ? record.flight_reservations : [],
    attractionReservations: Array.isArray(record?.attraction_reservations) ? record.attraction_reservations : [],
  }
}

export const bookingService = {
  async createBooking(payload) {
    // Validate required fields before sending
    if (!payload.flight && !payload.hotel) {
      throw new Error('A booking must include at least a flight or a hotel.')
    }

    const userId = await resolveUserId(payload)
    const requestBody = buildBookingPayload(payload, userId)
    const response = await api.post('/bookings/', requestBody)
    return normalizeBookingResponse(response)
  },

  async updateBooking(bookingId, { startDate, endDate }) {
    const body = {}
    if (startDate) body.Start_Date = startDate
    if (endDate) body.End_Date = endDate
    return api.patch(`/bookings/${bookingId}`, body)
  },

  async updateFlightReservation(bookingId, reservationNo, fields) {
  const body = {}

  if (fields.Airline_Code != null) body.Airline_Code = fields.Airline_Code
  if (fields.Flight_Number != null) body.Flight_Number = fields.Flight_Number
  if (fields.Departure_Date != null) body.Departure_Date = fields.Departure_Date
  if (fields.Departure_Time != null) body.Departure_Time = fields.Departure_Time
  if (fields.Arrive_Date != null) body.Arrive_Date = fields.Arrive_Date
  if (fields.Arrive_Time != null) body.Arrive_Time = fields.Arrive_Time
  if (fields.Rate != null) body.Rate = Number(fields.Rate)

  if (fields.Origin_Airport_Code != null) body.Origin_Airport_Code = fields.Origin_Airport_Code
  if (fields.Destination_Airport_Code != null) body.Destination_Airport_Code = fields.Destination_Airport_Code

  return api.patch(
    `/bookings/${bookingId}/flight-reservations/${reservationNo}`,
    body
  )
},
  
  async updateHotelReservation(bookingId, reservationNo, fields) {
  const body = {}

  if (fields.Hotel_Code != null) body.Hotel_Code = fields.Hotel_Code
  if (fields.Check_In_Date != null) body.Check_In_Date = fields.Check_In_Date
  if (fields.Check_In_Time != null) body.Check_In_Time = fields.Check_In_Time
  if (fields.Check_Out_Date != null) body.Check_Out_Date = fields.Check_Out_Date
  if (fields.Check_Out_Time != null) body.Check_Out_Time = fields.Check_Out_Time
  if (fields.Rate != null) body.Rate = Number(fields.Rate)

  return api.patch(
    `/bookings/${bookingId}/hotel-reservations/${reservationNo}`,
    body
  )
},
  
async updateAttractionReservation(bookingId, reservationNo, fields) {
  const body = {}

  if (fields.Attraction_Name != null) body.Attraction_Name = fields.Attraction_Name
  if (fields.Visit_Date != null) body.Visit_Date = fields.Visit_Date
  if (fields.Ticket_Type != null) body.Ticket_Type = fields.Ticket_Type
  if (fields.Rate != null) body.Rate = Number(fields.Rate)

  return api.patch(
    `/bookings/${bookingId}/attraction-reservations/${reservationNo}`,
    body
  )
},
  async deleteBooking(bookingId) {
    return api.delete(`/bookings/${bookingId}`)
  },

  async deleteFlightReservation(bookingId, reservationNo) {
    return api.delete(`/bookings/${bookingId}/flight-reservations/${reservationNo}`)
  },

  async deleteHotelReservation(bookingId, reservationNo) {
    return api.delete(`/bookings/${bookingId}/hotel-reservations/${reservationNo}`)
  },

  async deleteAttractionReservation(bookingId, reservationNo) {
    return api.delete(`/bookings/${bookingId}/attraction-reservations/${reservationNo}`)
  },

  async listBookings({ userId, agentId }) {
    const normalizedUserId = Number(userId)
    const normalizedAgentId = Number(agentId)

    if (!Number.isInteger(normalizedUserId) || normalizedUserId <= 0) {
      throw new Error('Please sign in first to view saved trips.')
    }

    const bookings = await api.get('/bookings/by-agent-user', {
      params: {
        agent_id: normalizedAgentId,
        user_id: normalizedUserId,
      },
    })

    const detailedBookings = (Array.isArray(bookings) ? bookings : []).map((booking) => {
      return normalizeBookingRecord(booking)
    })

    return detailedBookings.sort((left, right) => {
      return new Date(right.startDate).getTime() - new Date(left.startDate).getTime()
    })
  },
}
