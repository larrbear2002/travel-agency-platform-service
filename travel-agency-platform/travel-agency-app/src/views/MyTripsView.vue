<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { tenantConfig } from '../config/tenantConfig.js'
import { bookingService } from '../services/bookingService.js'
import { useAuth } from '../composables/useAuth.js'
import { useSearch } from '../composables/useSearch.js'
import SearchPanel from '../components/SearchPanel.vue'
import FlightList from '../components/FlightList.vue'
import HotelList from '../components/HotelList.vue'
import ActivityList from '../components/ActivityList.vue'
import SummaryPanel from '../components/SummaryPanel.vue'

const { userId, userEmail } = useAuth()

const isLoading = ref(true)
const errorMessage = ref('')
const trips = ref([])

// ── Per-booking edit state: bookingId → { search, results, selections, ui } ──
const editState = ref({})

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDate(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || 'N/A'
  return date.toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' })
}

const tripCountLabel = computed(() => {
  const n = trips.value.length
  return n === 1 ? '1 saved trip' : `${n} saved trips`
})

// ── Data loading ──────────────────────────────────────────────────────────────

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

// ── Edit lifecycle ────────────────────────────────────────────────────────────

function startEdit(trip) {
  // Derive origin/destination from first flight reservation, if present
  const firstFlight = trip.flightReservations[0]
  const lastFlight = trip.flightReservations[trip.flightReservations.length - 1]
  const hasReturn = trip.flightReservations.length > 1
  const origin = firstFlight?.Origin_Airport_Code || ''
  const destination = firstFlight?.Destination_Airport_Code || ''

  // Build per-booking search/booking state using the same composables
  const search = useSearch()
  // Pre-fill search params from existing booking
  Object.assign(search.searchParams, {
    tripType: hasReturn ? 'ROUNDTRIP' : 'ONEWAY',
    origin,
    destination,
    fromDate: trip.startDate || '',
    toDate: hasReturn ? (trip.endDate || '') : '',
    adults: 1,
    children: 0,
  })

  const selections = reactive({
    flight: null,
    returnFlight: null,
    hotel: null,
    isSaving: false,
    saveError: '',
    saveSuccess: false,
  })

  const ui = reactive({ activeTab: 'flights' })

  editState.value[trip.bookingId] = { search, selections, ui, trip }
}

function cancelEdit(bookingId) {
  delete editState.value[bookingId]
}

async function handleSearch(bookingId) {
  const state = editState.value[bookingId]
  if (!state) return
  state.selections.flight = null
  state.selections.returnFlight = null
  state.selections.hotel = null
  await state.search.search()
}

function selectFlight(bookingId, flight) {
  const state = editState.value[bookingId]
  if (!state) return
  state.selections.flight = state.selections.flight?.id === flight.id ? null : flight
}

function selectReturnFlight(bookingId, flight) {
  const state = editState.value[bookingId]
  if (!state) return
  state.selections.returnFlight = state.selections.returnFlight?.id === flight.id ? null : flight
}

function selectHotel(bookingId, hotel) {
  const state = editState.value[bookingId]
  if (!state) return
  state.selections.hotel = state.selections.hotel?.id === hotel.id ? null : hotel
}

function editHasSelections(bookingId) {
  const s = editState.value[bookingId]?.selections
  return !!(s?.flight || s?.returnFlight || s?.hotel)
}

function editTotalPrice(bookingId) {
  const s = editState.value[bookingId]?.selections
  if (!s) return 0
  let total = 0
  if (s.flight) total += s.flight.totalPrice || 0
  if (s.returnFlight) total += s.returnFlight.totalPrice || 0
  if (s.hotel) total += s.hotel.totalPrice || 0
  return total
}

// ── Save ──────────────────────────────────────────────────────────────────────

function normalizeTime(value, fallback = '00:00') {
  const raw = String(value || '').trim()
  if (!raw) return `${fallback}:00`
  const m = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/)
  if (m) {
    const h = String(Math.min(23, Math.max(0, Number(m[1])))).padStart(2, '0')
    const min = String(Math.min(59, Math.max(0, Number(m[2])))).padStart(2, '0')
    const sec = String(Math.min(59, Math.max(0, Number(m[3] || 0)))).padStart(2, '0')
    return `${h}:${min}:${sec}`
  }
  return `${fallback}:00`
}

function normalizeAirport(value) {
  return String(value || '').trim().toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3)
}

function splitFlightNumber(value) {
  const raw = String(value || '').trim().toUpperCase()
  const match = raw.match(/^([A-Z]{2,3})\s*-?(\d{1,4}[A-Z]?)$/)
  if (match) return { airlineCode: match[1], flightNumber: match[2] }
  return { airlineCode: '', flightNumber: raw }
}

async function saveEdit(bookingId) {
  const state = editState.value[bookingId]
  if (!state) return

  const { selections, search, trip } = state
  const { searchParams } = search

  selections.isSaving = true
  selections.saveError = ''
  selections.saveSuccess = false

  try {
    const startDate = searchParams.fromDate
    const endDate = searchParams.toDate || searchParams.fromDate

    // Update booking dates
    await bookingService.updateBooking(bookingId, { startDate, endDate })

    // Update flight reservations
    const flightsToUpdate = [selections.flight, selections.returnFlight].filter(Boolean)
    const existingFlights = trip.flightReservations

    for (let i = 0; i < existingFlights.length; i++) {
      const existing = existingFlights[i]
      const newFlight = flightsToUpdate[i]
      if (!newFlight) continue

      const split = splitFlightNumber(newFlight.flightNumber)
      const airlineCode = split.airlineCode || normalizeAirport(newFlight.airline).slice(0, 2)
      const flightDate = i === 0 ? startDate : endDate

      await bookingService.updateFlightReservation(bookingId, existing.Reservation_No, {
        Airline_Code: airlineCode,
        Flight_Number: split.flightNumber,
        Origin_Airport_Code: normalizeAirport(newFlight.origin),
        Destination_Airport_Code: normalizeAirport(newFlight.destination),
        Departure_Date: flightDate,
        Departure_Time: normalizeTime(newFlight.departureTime),
        Arrive_Date: flightDate,
        Arrive_Time: normalizeTime(newFlight.arrivalTime),
        Rate: Number(newFlight.totalPrice ?? 0),
      })
    }

    // Update hotel reservations
    if (selections.hotel && trip.hotelReservations.length > 0) {
      const existing = trip.hotelReservations[0]
      const hotelCode = Number.parseInt(String(selections.hotel.id ?? existing.Hotel_Code ?? 0), 10)
      await bookingService.updateHotelReservation(bookingId, existing.Reservation_No, {
        Hotel_Code: Number.isFinite(hotelCode) ? hotelCode : existing.Hotel_Code,
        Check_In_Date: selections.hotel.checkIn || startDate,
        Check_In_Time: normalizeTime(selections.hotel.checkInTime || existing.Check_In_Time),
        Check_Out_Date: selections.hotel.checkOut || endDate,
        Check_Out_Time: normalizeTime(selections.hotel.checkOutTime || existing.Check_Out_Time),
        Rate: Number(selections.hotel.totalPrice ?? 0),
      })
    }

    selections.saveSuccess = true
    cancelEdit(bookingId)
    await loadTrips()
  } catch (error) {
    selections.saveError = error.message || 'Failed to save changes.'
  } finally {
    selections.isSaving = false
  }
}

// ── Delete helpers ────────────────────────────────────────────────────────────

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
    if (type === 'flight') await bookingService.deleteFlightReservation(trip.bookingId, reservationNo)
    else if (type === 'hotel') await bookingService.deleteHotelReservation(trip.bookingId, reservationNo)
    else if (type === 'attraction') await bookingService.deleteAttractionReservation(trip.bookingId, reservationNo)
    await loadTrips()
  } catch (error) {
    errorMessage.value = error.message || `Failed to delete ${type} reservation.`
  }
}

onMounted(() => { loadTrips() })
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

        <!-- ── Card header ─────────────────────────────────────────────── -->
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

        <!-- ── VIEW MODE ──────────────────────────────────────────────── -->
        <template v-if="!editState[trip.bookingId]">
          <section class="trip-section">
            <h3 class="trip-section__title">Flight Details</h3>
            <p v-if="trip.flightReservations.length === 0" class="trip-section__empty">No flights saved for this trip.</p>
            <div v-else class="reservation-grid">
              <div
                v-for="flight in trip.flightReservations"
                :key="`${trip.bookingId}-${flight.Reservation_No}`"
                class="reservation-card"
              >
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
              <div
                v-for="hotel in trip.hotelReservations"
                :key="`${trip.bookingId}-${hotel.Reservation_No}`"
                class="reservation-card"
              >
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
              <div
                v-for="attraction in trip.attractionReservations"
                :key="`${trip.bookingId}-att-${attraction.Reservation_No}`"
                class="reservation-card"
              >
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

        <!-- ── EDIT MODE — same UI as new booking ────────────────────── -->
        <template v-else>
          <div class="edit-mode">
            <!-- Instruction banner -->
            <div class="edit-mode__banner">
              <span class="edit-mode__banner-icon">✏️</span>
              <div>
                <strong>Editing Booking #{{ trip.bookingId }}</strong>
                <p class="edit-mode__banner-sub">
                  Search for new options below, select your preferred flight and hotel, then click
                  <em>Save Changes</em> to update this booking.
                </p>
              </div>
              <button class="btn btn--cancel" @click="cancelEdit(trip.bookingId)">✕ Cancel</button>
            </div>

            <!-- Search panel (same as HomeView) -->
            <SearchPanel
              :search-params="editState[trip.bookingId].search.searchParams"
              :loading="editState[trip.bookingId].search.loading.flights ||
                        editState[trip.bookingId].search.loading.hotels ||
                        editState[trip.bookingId].search.loading.activities"
              @search="handleSearch(trip.bookingId)"
              @clear="editState[trip.bookingId].search.resetSearch()"
            />

            <!-- Results + summary layout (shown after search) -->
            <div
              v-if="editState[trip.bookingId].search.hasSearched"
              class="edit-results-layout"
            >
              <!-- Left: tabbed results -->
              <div class="edit-results-main">
                <!-- Tabs -->
                <div class="tabs">
                  <button
                    v-for="tab in [
                      { key: 'flights', label: 'Flights', icon: '✈️' },
                      { key: 'hotels',  label: 'Hotels',  icon: '🏨' },
                      { key: 'activities', label: 'Activities', icon: '🎯' },
                    ]"
                    :key="tab.key"
                    class="tab-btn"
                    :class="{ 'tab-btn--active': editState[trip.bookingId].ui.activeTab === tab.key }"
                    @click="editState[trip.bookingId].ui.activeTab = tab.key"
                  >
                    <span>{{ tab.icon }}</span> {{ tab.label }}
                    <span
                      v-if="tab.key === 'flights' && editState[trip.bookingId].search.results.flights.length"
                      class="tab-count"
                    >{{ editState[trip.bookingId].search.results.flights.length }}</span>
                    <span
                      v-if="tab.key === 'hotels' && editState[trip.bookingId].search.results.hotels.length"
                      class="tab-count"
                    >{{ editState[trip.bookingId].search.results.hotels.length }}</span>
                    <span
                      v-if="tab.key === 'activities' && editState[trip.bookingId].search.results.activities.length"
                      class="tab-count"
                    >{{ editState[trip.bookingId].search.results.activities.length }}</span>
                  </button>
                </div>

                <!-- Tab panels -->
                <div class="tab-panel">
                  <div
                    v-show="editState[trip.bookingId].ui.activeTab === 'flights'"
                    class="flight-panels"
                  >
                    <div class="flight-panels__section">
                      <h3 class="flight-panels__title">Outbound flight</h3>
                      <FlightList
                        :flights="editState[trip.bookingId].search.results.flights"
                        :loading="editState[trip.bookingId].search.loading.flights"
                        :error="editState[trip.bookingId].search.errors.flights"
                        :selected-flight="editState[trip.bookingId].selections.flight"
                        :deal-intel="editState[trip.bookingId].search.dealIntel"
                        @select="selectFlight(trip.bookingId, $event)"
                      />
                    </div>
                    <div
                      v-if="editState[trip.bookingId].search.searchParams.tripType === 'ROUNDTRIP'"
                      class="flight-panels__section"
                    >
                      <h3 class="flight-panels__title">Return flight</h3>
                      <FlightList
                        :flights="editState[trip.bookingId].search.results.returnFlights"
                        :loading="editState[trip.bookingId].search.loading.returnFlights"
                        :error="editState[trip.bookingId].search.errors.returnFlights"
                        :selected-flight="editState[trip.bookingId].selections.returnFlight"
                        :deal-intel="editState[trip.bookingId].search.dealIntel"
                        @select="selectReturnFlight(trip.bookingId, $event)"
                      />
                    </div>
                  </div>

                  <HotelList
                    v-show="editState[trip.bookingId].ui.activeTab === 'hotels'"
                    :hotels="editState[trip.bookingId].search.results.hotels"
                    :loading="editState[trip.bookingId].search.loading.hotels"
                    :error="editState[trip.bookingId].search.errors.hotels"
                    :selected-hotel="editState[trip.bookingId].selections.hotel"
                    @select="selectHotel(trip.bookingId, $event)"
                  />

                  <ActivityList
                    v-show="editState[trip.bookingId].ui.activeTab === 'activities'"
                    :activities="editState[trip.bookingId].search.results.activities"
                    :loading="editState[trip.bookingId].search.loading.activities"
                    :error="editState[trip.bookingId].search.errors.activities"
                  />
                </div>
              </div>

              <!-- Right: summary panel -->
              <div class="edit-summary-wrapper">
                <SummaryPanel
                  :trip-type="editState[trip.bookingId].search.searchParams.tripType"
                  :selected-flight="editState[trip.bookingId].selections.flight"
                  :selected-return-flight="editState[trip.bookingId].selections.returnFlight"
                  :selected-hotel="editState[trip.bookingId].selections.hotel"
                  :selected-activities="[]"
                  :total-price="editTotalPrice(trip.bookingId)"
                  :has-selections="editHasSelections(trip.bookingId)"
                  :is-booking="editState[trip.bookingId].selections.isSaving"
                  :booking-result="null"
                  :booking-error="editState[trip.bookingId].selections.saveError || null"
                  :is-authenticated="true"
                  :user-email="userEmail"
                  @book="saveEdit(trip.bookingId)"
                  @clear="editState[trip.bookingId].selections.flight = null;
                          editState[trip.bookingId].selections.returnFlight = null;
                          editState[trip.bookingId].selections.hotel = null;"
                >
                  <!-- Override the "Book Now" label slot isn't available, so we wrap -->
                </SummaryPanel>

                <!-- Save Changes button sits below the summary panel -->
                <div class="edit-save-bar">
                  <p v-if="editState[trip.bookingId].selections.saveError" class="edit-save-bar__error">
                    ⚠️ {{ editState[trip.bookingId].selections.saveError }}
                  </p>
                  <button
                    class="btn btn--save"
                    :disabled="!editHasSelections(trip.bookingId) || editState[trip.bookingId].selections.isSaving"
                    @click="saveEdit(trip.bookingId)"
                  >
                    {{ editState[trip.bookingId].selections.isSaving ? 'Saving…' : '💾 Save Changes' }}
                  </button>
                </div>
              </div>
            </div>

            <!-- Pre-search hint -->
            <div v-else class="edit-hint">
              <span class="edit-hint__icon">🔍</span>
              <p>Update the route or dates above, then click <strong>Search</strong> to browse new options for this booking.</p>
            </div>
          </div>
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

.state-card--error { color: #c0392b; }

.trips-list {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* ── Trip card ── */
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

/* ── View mode sections ── */
.trip-section + .trip-section { margin-top: 1.25rem; }
.trip-section__title { margin: 0 0 0.75rem; color: var(--color-text); font-size: 1rem; }
.trip-section__empty { margin: 0; color: var(--color-text-muted); }

.reservation-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}

.reservation-card {
  position: relative;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  padding: 1rem;
  background: #fcfdff;
  color: var(--color-text);
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.reservation-card__title { font-weight: 700; color: var(--color-primary-dark); }

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

.reservation-card__remove:hover { background: #c0392b; color: #fff; border-color: #c0392b; }

/* ── Buttons ── */
.btn {
  padding: 0.45rem 1rem;
  border-radius: 8px;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: opacity 0.15s;
}

.btn:disabled { opacity: 0.55; cursor: not-allowed; }

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

.btn--delete:hover { background: #c0392b; color: #fff; }

.btn--cancel {
  background: transparent;
  color: var(--color-text-muted);
  border: 1px solid var(--color-border);
  white-space: nowrap;
}

.btn--save {
  background: var(--color-primary-dark);
  color: #fff;
  padding: 0.65rem 1.5rem;
  font-size: 0.95rem;
  border-radius: 10px;
  width: 100%;
}

.btn--save:hover:not(:disabled) { opacity: 0.9; }

/* ── Edit mode wrapper ── */
.edit-mode {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Instruction banner */
.edit-mode__banner {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.9rem 1rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 12px;
}

.edit-mode__banner-icon { font-size: 1.4rem; flex-shrink: 0; }

.edit-mode__banner strong { font-size: 0.95rem; color: var(--color-primary-dark); }

.edit-mode__banner-sub {
  margin: 0.2rem 0 0;
  font-size: 0.82rem;
  color: var(--color-text-muted);
  line-height: 1.5;
}

.edit-mode__banner .btn--cancel { margin-left: auto; flex-shrink: 0; }

/* Results layout — mirrors HomeView */
.edit-results-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  min-height: 500px;
  border: 1px solid var(--color-border);
  border-radius: 14px;
  overflow: hidden;
}

.edit-results-main {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
}

/* Tabs — identical to HomeView */
.tabs {
  display: flex;
  background: #fff;
  border-bottom: 1px solid var(--color-border);
  padding: 0 1rem;
  gap: 0.25rem;
  flex-shrink: 0;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.75rem 1rem;
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--color-text-muted);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s;
  margin-bottom: -1px;
  white-space: nowrap;
}

.tab-btn:hover { color: var(--color-text); }
.tab-btn--active { color: var(--color-primary); border-bottom-color: var(--color-primary); }

.tab-count {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 12px;
}

.tab-btn--active .tab-count { background: var(--color-primary); color: #fff; }

.tab-panel {
  flex: 1;
  overflow-y: auto;
  background: var(--color-bg);
}

.flight-panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  align-items: start;
  padding: 0.75rem;
}

.flight-panels__section {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.flight-panels__title {
  margin: 0;
  padding: 0.85rem 1rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
  background: #fafcff;
}

/* Summary wrapper */
.edit-summary-wrapper {
  display: flex;
  flex-direction: column;
  background: #fff;
  overflow-y: auto;
}

.edit-save-bar {
  padding: 0.75rem 1.25rem 1.25rem;
  border-top: 1px solid var(--color-border);
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.edit-save-bar__error {
  margin: 0;
  font-size: 0.82rem;
  color: #c0392b;
}

/* Pre-search hint */
.edit-hint {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 1.25rem;
  background: #fafcff;
  border: 1px dashed var(--color-border);
  border-radius: 12px;
  color: var(--color-text-muted);
  font-size: 0.88rem;
}

.edit-hint__icon { font-size: 1.5rem; flex-shrink: 0; }
.edit-hint p { margin: 0; }

/* Responsive */
@media (max-width: 900px) {
  .edit-results-layout { grid-template-columns: 1fr; }
  .edit-results-main { border-right: none; border-bottom: 1px solid var(--color-border); }
  .flight-panels { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .my-trips-view { padding: 1rem; }
  .my-trips-view__hero, .trip-card__header { flex-direction: column; align-items: flex-start; }
  .edit-mode__banner { flex-wrap: wrap; }
}
</style>
