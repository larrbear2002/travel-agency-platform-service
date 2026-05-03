<script setup>
import { computed, onMounted, ref } from 'vue'
import { tenantConfig } from '../config/tenantConfig.js'
import { bookingService } from '../services/bookingService.js'
import { useAuth } from '../composables/useAuth.js'

const { userId, userEmail } = useAuth()

const isLoading = ref(true)
const errorMessage = ref('')
const trips = ref([])

// editState keyed by bookingId — null means not editing
const editState = ref({})
const isSaving = ref({})
const saveError = ref({})

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'N/A'
  return date.toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

const tripCountLabel = computed(() => {
  const tripCount = trips.value.length
  return tripCount === 1 ? '1 saved trip' : `${tripCount} saved trips`
})

async function loadTrips() {
  isLoading.value = true
  errorMessage.value = ''
  try {
    trips.value = await bookingService.listBookings({
      userId: userId.value,
      agentId: tenantConfig.agentId,
    })
  } catch (error) {
    errorMessage.value = error.message || 'Unable to load saved trips.'
    trips.value = []
  } finally {
    isLoading.value = false
  }
}

function startEdit(trip) {
  editState.value[trip.bookingId] = {
    startDate: trip.startDate,
    endDate: trip.endDate,
    flightReservations: trip.flightReservations.map((f) => ({
      Reservation_No: f.Reservation_No,
      Departure_Date: f.Departure_Date,
      Departure_Time: f.Departure_Time,
      Arrive_Date: f.Arrive_Date,
      Arrive_Time: f.Arrive_Time,
      Rate: f.Rate,
    })),
    hotelReservations: trip.hotelReservations.map((h) => ({
      Reservation_No: h.Reservation_No,
      Check_In_Date: h.Check_In_Date,
      Check_Out_Date: h.Check_Out_Date,
      Rate: h.Rate,
    })),
    attractionReservations: (trip.attractionReservations || []).map((a) => ({
      Reservation_No: a.Reservation_No,
      Attraction_Name: a.Attraction_Name,
      Visit_Date: a.Visit_Date,
      Ticket_Type: a.Ticket_Type,
      Rate: a.Rate,
    })),
  }
  saveError.value[trip.bookingId] = ''
}

function cancelEdit(bookingId) {
  delete editState.value[bookingId]
  delete saveError.value[bookingId]
}

async function saveEdit(trip) {
  const state = editState.value[trip.bookingId]
  if (!state) return

  isSaving.value[trip.bookingId] = true
  saveError.value[trip.bookingId] = ''

  try {
    await bookingService.updateBooking(trip.bookingId, {
      startDate: state.startDate,
      endDate: state.endDate,
    })

    for (const f of state.flightReservations) {
      await bookingService.updateFlightReservation(trip.bookingId, f.Reservation_No, {
        Departure_Date: f.Departure_Date,
        Departure_Time: f.Departure_Time,
        Arrive_Date: f.Arrive_Date,
        Arrive_Time: f.Arrive_Time,
        Rate: Number(f.Rate) || undefined,
      })
    }

    for (const h of state.hotelReservations) {
      await bookingService.updateHotelReservation(trip.bookingId, h.Reservation_No, {
        Check_In_Date: h.Check_In_Date,
        Check_Out_Date: h.Check_Out_Date,
        Rate: Number(h.Rate) || undefined,
      })
    }

    for (const a of state.attractionReservations) {
      await bookingService.updateAttractionReservation(trip.bookingId, a.Reservation_No, {
        Attraction_Name: a.Attraction_Name,
        Visit_Date: a.Visit_Date,
        Ticket_Type: a.Ticket_Type || null,
        Rate: Number(a.Rate) || undefined,
      })
    }

    cancelEdit(trip.bookingId)
    await loadTrips()
  } catch (error) {
    saveError.value[trip.bookingId] = error.message || 'Failed to save changes.'
  } finally {
    isSaving.value[trip.bookingId] = false
  }
}

async function deleteTrip(trip) {
  if (!window.confirm(`Delete booking #${trip.bookingId}? This cannot be undone.`)) return
  try {
    await bookingService.deleteBooking(trip.bookingId)
    await loadTrips()
  } catch (error) {
    errorMessage.value = error.message || 'Failed to delete booking.'
  }
}

async function deleteReservation(trip, type, reservationNo) {
  if (!window.confirm(`Remove this ${type} reservation from booking #${trip.bookingId}?`)) return
  try {
    if (type === 'flight') {
      await bookingService.deleteFlightReservation(trip.bookingId, reservationNo)
    } else if (type === 'hotel') {
      await bookingService.deleteHotelReservation(trip.bookingId, reservationNo)
    } else if (type === 'attraction') {
      await bookingService.deleteAttractionReservation(trip.bookingId, reservationNo)
    }
    await loadTrips()
  } catch (error) {
    errorMessage.value = error.message || `Failed to delete ${type} reservation.`
  }
}

onMounted(() => {
  loadTrips()
})
</script>

<template>
  <div class="my-trips-view">
    <div class="my-trips-view__hero">
      <div>
        <p class="my-trips-view__eyebrow">Agent {{ tenantConfig.agentId }}</p>
        <h1 class="my-trips-view__title">My Trips</h1>
        <p class="my-trips-view__sub">
          Saved trips for {{ userEmail || `User ${userId}` }} with {{ tenantConfig.brandName }}.
        </p>
      </div>
      <div class="my-trips-view__summary">{{ tripCountLabel }}</div>
    </div>

    <div v-if="isLoading" class="state-card">Loading saved trips...</div>
    <div v-else-if="errorMessage" class="state-card state-card--error">{{ errorMessage }}</div>
    <div v-else-if="trips.length === 0" class="state-card">No saved trips found for this user and agent.</div>

    <div v-else class="trips-list">
      <article v-for="trip in trips" :key="trip.bookingId" class="trip-card">
        <div class="trip-card__header">
          <div>
            <p class="trip-card__meta">Booking #{{ trip.bookingId }}</p>
            <h2 class="trip-card__title">{{ formatDate(trip.startDate) }} to {{ formatDate(trip.endDate) }}</h2>
          </div>
          <div class="trip-card__actions">
            <div class="trip-card__pill">
            {{ trip.flightReservations.length }} flights ·
            {{ trip.hotelReservations.length }} hotels ·
            {{ (trip.attractionReservations || []).length }} attractions
          </div>
            <button
              v-if="!editState[trip.bookingId]"
              class="btn btn--edit"
              @click="startEdit(trip)"
            >Edit</button>
            <button
              v-if="!editState[trip.bookingId]"
              class="btn btn--delete"
              @click="deleteTrip(trip)"
            >Delete</button>
          </div>
        </div>

        <!-- VIEW MODE -->
        <template v-if="!editState[trip.bookingId]">
          <section class="trip-section">
            <h3 class="trip-section__title">Flight Details</h3>
            <p v-if="trip.flightReservations.length === 0" class="trip-section__empty">No flights saved for this trip.</p>
            <div v-else class="reservation-grid">
              <div v-for="flight in trip.flightReservations" :key="`${trip.bookingId}-${flight.Reservation_No}`" class="reservation-card">
                <button class="reservation-card__remove" title="Remove this flight" @click="deleteReservation(trip, 'flight', flight.Reservation_No)">×</button>
                <div class="reservation-card__title">Flight Reservation</div>
                <div><strong>Airline code:</strong> {{ flight.Airline_Code || 'N/A' }}</div>
                <div><strong>Flight number:</strong> {{ flight.Flight_Number || 'N/A' }}</div>
                <div>{{ flight.Origin_Airport_Code }} to {{ flight.Destination_Airport_Code }}</div>
                <div>Departure: {{ formatDate(flight.Departure_Date) }} {{ flight.Departure_Time }}</div>
                <div>Arrival: {{ formatDate(flight.Arrive_Date) }} {{ flight.Arrive_Time }}</div>
                <div>Rate: ${{ Number(flight.Rate || 0).toLocaleString() }}</div>
              </div>
            </div>
          </section>

          <section class="trip-section">
            <h3 class="trip-section__title">Hotel Details</h3>
            <p v-if="trip.hotelReservations.length === 0" class="trip-section__empty">No hotel saved for this trip.</p>
            <div v-else class="reservation-grid">
              <div v-for="hotel in trip.hotelReservations" :key="`${trip.bookingId}-${hotel.Reservation_No}`" class="reservation-card">
                <button class="reservation-card__remove" title="Remove this hotel" @click="deleteReservation(trip, 'hotel', hotel.Reservation_No)">×</button>
                <div class="reservation-card__title">Hotel Reservation</div>
                <div><strong>Hotel Code:</strong> {{ hotel.Hotel_Code || 'N/A' }}</div>
                <div>Check in: {{ formatDate(hotel.Check_In_Date) }} {{ hotel.Check_In_Time }}</div>
                <div>Check out: {{ formatDate(hotel.Check_Out_Date) }} {{ hotel.Check_Out_Time }}</div>
                <div>Rate: ${{ Number(hotel.Rate || 0).toLocaleString() }}</div>
              </div>
            </div>
          </section>

          <section class="trip-section">
            <h3 class="trip-section__title">Attractions</h3>
            <p v-if="!(trip.attractionReservations || []).length" class="trip-section__empty">No attractions saved for this trip.</p>
            <div v-else class="reservation-grid">
              <div v-for="attraction in trip.attractionReservations" :key="`${trip.bookingId}-att-${attraction.Reservation_No}`" class="reservation-card">
                <button class="reservation-card__remove" title="Remove this attraction" @click="deleteReservation(trip, 'attraction', attraction.Reservation_No)">×</button>
                <div class="reservation-card__title">Attraction Reservation</div>
                <div><strong>{{ attraction.Attraction_Name || 'Attraction' }}</strong></div>
                <div>Visit date: {{ formatDate(attraction.Visit_Date) }}</div>
                <div v-if="attraction.Ticket_Type">Ticket: {{ attraction.Ticket_Type }}</div>
                <div>Rate: ${{ Number(attraction.Rate || 0).toLocaleString() }}</div>
              </div>
            </div>
          </section>
        </template>

        <!-- EDIT MODE -->
        <template v-else>
          <form class="edit-form" @submit.prevent="saveEdit(trip)">
            <fieldset class="edit-fieldset">
              <legend class="edit-legend">Trip Dates</legend>
              <div class="edit-row">
                <label class="edit-label">
                  Start Date
                  <input v-model="editState[trip.bookingId].startDate" type="date" class="edit-input" required />
                </label>
                <label class="edit-label">
                  End Date
                  <input v-model="editState[trip.bookingId].endDate" type="date" class="edit-input" required />
                </label>
              </div>
            </fieldset>

            <fieldset
              v-for="(flight, fi) in editState[trip.bookingId].flightReservations"
              :key="`edit-flight-${flight.Reservation_No}`"
              class="edit-fieldset"
            >
              <legend class="edit-legend">Flight {{ fi + 1 }} (Reservation #{{ flight.Reservation_No }})</legend>
              <div class="edit-row">
                <label class="edit-label">
                  Departure Date
                  <input v-model="flight.Departure_Date" type="date" class="edit-input" />
                </label>
                <label class="edit-label">
                  Departure Time
                  <input v-model="flight.Departure_Time" type="time" class="edit-input" />
                </label>
                <label class="edit-label">
                  Arrival Date
                  <input v-model="flight.Arrive_Date" type="date" class="edit-input" />
                </label>
                <label class="edit-label">
                  Arrival Time
                  <input v-model="flight.Arrive_Time" type="time" class="edit-input" />
                </label>
                <label class="edit-label">
                  Rate ($)
                  <input v-model="flight.Rate" type="number" min="0" step="0.01" class="edit-input" />
                </label>
              </div>
            </fieldset>

            <fieldset
              v-for="(hotel, hi) in editState[trip.bookingId].hotelReservations"
              :key="`edit-hotel-${hotel.Reservation_No}`"
              class="edit-fieldset"
            >
              <legend class="edit-legend">Hotel {{ hi + 1 }} (Reservation #{{ hotel.Reservation_No }})</legend>
              <div class="edit-row">
                <label class="edit-label">
                  Check-In Date
                  <input v-model="hotel.Check_In_Date" type="date" class="edit-input" />
                </label>
                <label class="edit-label">
                  Check-Out Date
                  <input v-model="hotel.Check_Out_Date" type="date" class="edit-input" />
                </label>
                <label class="edit-label">
                  Rate ($)
                  <input v-model="hotel.Rate" type="number" min="0" step="0.01" class="edit-input" />
                </label>
              </div>
            </fieldset>

            <fieldset
              v-for="(attraction, ai) in editState[trip.bookingId].attractionReservations"
              :key="`edit-attraction-${attraction.Reservation_No}`"
              class="edit-fieldset"
            >
              <legend class="edit-legend">Attraction {{ ai + 1 }} (Reservation #{{ attraction.Reservation_No }})</legend>
              <div class="edit-row">
                <label class="edit-label">
                  Attraction Name
                  <input v-model="attraction.Attraction_Name" type="text" class="edit-input" />
                </label>
                <label class="edit-label">
                  Visit Date
                  <input v-model="attraction.Visit_Date" type="date" class="edit-input" />
                </label>
                <label class="edit-label">
                  Ticket Type
                  <input v-model="attraction.Ticket_Type" type="text" class="edit-input" placeholder="Standard / VIP / etc." />
                </label>
                <label class="edit-label">
                  Rate ($)
                  <input v-model="attraction.Rate" type="number" min="0" step="0.01" class="edit-input" />
                </label>
              </div>
            </fieldset>

            <p v-if="saveError[trip.bookingId]" class="edit-error">{{ saveError[trip.bookingId] }}</p>

            <div class="edit-actions">
              <button type="submit" class="btn btn--save" :disabled="isSaving[trip.bookingId]">
                {{ isSaving[trip.bookingId] ? 'Saving…' : 'Save Changes' }}
              </button>
              <button type="button" class="btn btn--cancel" :disabled="isSaving[trip.bookingId]" @click="cancelEdit(trip.bookingId)">
                Cancel
              </button>
            </div>
          </form>
        </template>
      </article>
    </div>
  </div>
</template>

<style scoped>
.my-trips-view {
  min-height: calc(100vh - 56px);
  background: var(--color-bg);
  padding: 2rem;
}

.my-trips-view__hero {
  max-width: 1200px;
  margin: 0 auto 1.5rem;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 1rem;
}

.my-trips-view__eyebrow {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--color-accent-dark);
}

.my-trips-view__title {
  margin: 0;
  font-size: 2rem;
  color: var(--color-primary-dark);
}

.my-trips-view__sub {
  margin: 0.5rem 0 0;
  color: var(--color-text-muted);
}

.my-trips-view__summary {
  padding: 0.6rem 0.9rem;
  border-radius: 999px;
  background: #fff;
  border: 1px solid var(--color-border);
  color: var(--color-text);
  font-weight: 700;
}

.state-card {
  max-width: 1200px;
  margin: 0 auto;
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 2rem;
  color: var(--color-text-muted);
}

.state-card--error {
  color: #c0392b;
}

.trips-list {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.trip-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  padding: 1.5rem;
  box-shadow: 0 10px 24px rgba(26, 54, 93, 0.06);
}

.trip-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1.25rem;
}

.trip-card__actions {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.trip-card__meta {
  margin: 0 0 0.35rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
}

.trip-card__title {
  margin: 0;
  color: var(--color-primary-dark);
  font-size: 1.2rem;
}

.trip-card__pill {
  padding: 0.45rem 0.75rem;
  border-radius: 999px;
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  font-size: 0.85rem;
  font-weight: 700;
  white-space: nowrap;
}

.trip-section + .trip-section {
  margin-top: 1.25rem;
}

.trip-section__title {
  margin: 0 0 0.75rem;
  color: var(--color-text);
  font-size: 1rem;
}

.trip-section__empty {
  margin: 0;
  color: var(--color-text-muted);
}

.reservation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}

.reservation-card {
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 1rem;
  background: #fcfdff;
  color: var(--color-text);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.reservation-card__title {
  font-weight: 700;
  color: var(--color-primary-dark);
}

.btn {
  padding: 0.45rem 1rem;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: opacity 0.15s;
}

.btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn--edit {
  background: var(--color-primary-bg);
  color: var(--color-primary-dark);
  border: 1px solid var(--color-primary-dark);
}

.btn--delete {
  background: #fff;
  color: #c0392b;
  border: 1px solid #c0392b;
}

.btn--delete:hover {
  background: #c0392b;
  color: #fff;
}

.reservation-card {
  position: relative;
}

.reservation-card__remove {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  border: 1px solid var(--color-border);
  background: #fff;
  color: #c0392b;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
}

.reservation-card__remove:hover {
  background: #c0392b;
  color: #fff;
  border-color: #c0392b;
}

.btn--save {
  background: var(--color-primary-dark);
  color: #fff;
}

.btn--cancel {
  background: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
}

.edit-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.edit-fieldset {
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 1rem;
}

.edit-legend {
  font-size: 0.85rem;
  font-weight: 700;
  color: var(--color-primary-dark);
  padding: 0 0.4rem;
}

.edit-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}

.edit-label {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  font-weight: 600;
}

.edit-input {
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 0.9rem;
  color: var(--color-text);
  background: #fff;
}

.edit-error {
  color: #c0392b;
  font-size: 0.85rem;
  margin: 0;
}

.edit-actions {
  display: flex;
  gap: 0.75rem;
}

@media (max-width: 768px) {
  .my-trips-view {
    padding: 1rem;
  }

  .my-trips-view__hero,
  .trip-card__header {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>