<script setup>
import { ref } from 'vue'
import SearchPanel from '../components/SearchPanel.vue'
import PriceForecast from '../components/PriceForecast.vue'
import FlightList from '../components/FlightList.vue'
import HotelList from '../components/HotelList.vue'
import ActivityList from '../components/ActivityList.vue'
import SummaryPanel from '../components/SummaryPanel.vue'
import { useSearch } from '../composables/useSearch.js'
import { useBooking } from '../composables/useBooking.js'
import { useAuth } from '../composables/useAuth.js'
import { tenantConfig } from '../config/tenantConfig.js'

const { searchParams, results, loading, errors, dealIntel, hasSearched, search, resetSearch } = useSearch()
const {
  selectedFlight,
  selectedReturnFlight,
  selectedHotel,
  selectedActivities,
  totalPrice,
  hasSelections,
  isBooking,
  bookingResult,
  bookingError,
  selectFlight,
  selectReturnFlight,
  selectHotel,
  clearSelections,
  book,
} = useBooking()
const { isAuthenticated, userEmail } = useAuth()

const activeTab = ref('flights')

const tabs = [
  { key: 'flights', label: 'Flights', icon: '✈️' },
  { key: 'hotels', label: 'Hotels', icon: '🏨' },
  { key: 'activities', label: 'Activities', icon: '🎯' },
]

function handleSearch() {
  search()
  clearSelections()
}

function handleBook() {
  book(searchParams)
}

function handleClear() {
  resetSearch()
  clearSelections()
  activeTab.value = 'flights'
}

function handleForecastBook(payload) {
  if (payload.origin) searchParams.origin = payload.origin
  if (payload.destination) searchParams.destination = payload.destination
  if (payload.fromDate) searchParams.fromDate = payload.fromDate
  if (typeof payload.toDate === 'string') searchParams.toDate = payload.toDate
  if (payload.tripType) searchParams.tripType = payload.tripType
  clearSelections()
  search()
  // Smooth-scroll to the search panel so users see their dates have updated
  setTimeout(() => {
    document.querySelector('.search-panel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 100)
}
</script>

<template>
  <div class="home-view">
    <!-- ╔════════════════════════════════════════════════════════════════╗
         ║  HERO — Expedia-inspired                                       ║
         ╚════════════════════════════════════════════════════════════════╝ -->
    <section v-if="!hasSearched" class="hero-section">
      <div class="hero-section__bg"></div>
      <div class="hero-section__inner">
        <p class="hero-section__eyebrow">{{ tenantConfig.brandName }}</p>
        <h1 class="hero-section__title">
          Find the cheapest month<br/>to fly anywhere.
        </h1>
        <p class="hero-section__sub">
          Scan the rest of the year for the cheapest month to fly. Spot deals before they vanish.
        </p>

        <!-- Unified search + forecast card -->
        <div class="home-card">
          <SearchPanel
            :search-params="searchParams"
            :loading="loading.flights || loading.returnFlights || loading.hotels || loading.activities"
            @search="handleSearch"
            @clear="handleClear"
          />

          <div class="home-card__divider">
            <span>or find the cheapest month for this route</span>
          </div>

          <PriceForecast
            :origin="searchParams.origin"
            :destination="searchParams.destination"
            @book-month="handleForecastBook"
          />
        </div>
      </div>
    </section>

    <!-- ╔════════════════════════════════════════════════════════════════╗
         ║  Compact search bar (post-search)                              ║
         ╚════════════════════════════════════════════════════════════════╝ -->
    <SearchPanel
      v-if="hasSearched"
      :search-params="searchParams"
      :loading="loading.flights || loading.returnFlights || loading.hotels || loading.activities"
      @search="handleSearch"
      @clear="handleClear"
    />

    <PriceForecast
      v-if="hasSearched"
      :origin="searchParams.origin"
      :destination="searchParams.destination"
      @book-month="handleForecastBook"
    />

    <!-- Main Content -->
    <div class="main-content" :class="{ 'main-content--searched': hasSearched }">
      <!-- Feature highlights — only show before searching -->
      <div v-if="!hasSearched" class="features">
        <h2 class="features__title">Why travel smarter with {{ tenantConfig.brandName }}?</h2>
        <div class="features__grid">
          <div class="feature-card feature-card--accent">
            <div class="feature-card__icon">📊</div>
            <h3 class="feature-card__title">6-Month Price Forecast</h3>
            <p class="feature-card__sub">See the cheapest fares for every month ahead — pick the best time to book.</p>
          </div>
          <div class="feature-card">
            <div class="feature-card__icon">⭐</div>
            <h3 class="feature-card__title">Auto Deal Detection</h3>
            <p class="feature-card__sub">Every search is scored against historical prices: Good Deal, Average, or Expensive.</p>
          </div>
          <div class="feature-card">
            <div class="feature-card__icon">💰</div>
            <h3 class="feature-card__title">All-in-One Booking</h3>
            <p class="feature-card__sub">Flights, hotels, and attractions — saved together in one trip you can edit anytime.</p>
          </div>
        </div>

        <div class="cta-strip">
          <div>
            <h3 class="cta-strip__title">New to {{ tenantConfig.brandName }}?</h3>
            <p class="cta-strip__sub">Type any origin and destination above, then click "Find Cheapest Month" to discover the best time to fly.</p>
          </div>
        </div>
      </div>

      <!-- Results layout -->
      <div v-else class="results-layout">
        <!-- Left: Tabbed panels -->
        <div class="results-main">
          <!-- Tabs -->
          <div class="tabs">
            <button
              v-for="tab in tabs"
              :key="tab.key"
              class="tab-btn"
              :class="{ 'tab-btn--active': activeTab === tab.key }"
              @click="activeTab = tab.key"
            >
              <span class="tab-icon">{{ tab.icon }}</span>
              {{ tab.label }}
              <span
                v-if="tab.key === 'flights' && (loading.flights || results.flights.length)"
                class="tab-count"
              >
                {{ loading.flights ? '…' : (searchParams.tripType === 'ROUNDTRIP' ? results.flights.length + results.returnFlights.length : results.flights.length) }}
              </span>
              <span
                v-if="tab.key === 'hotels' && (loading.hotels || results.hotels.length)"
                class="tab-count"
              >
                {{ loading.hotels ? '…' : results.hotels.length }}
              </span>
              <span
                v-if="tab.key === 'activities' && (loading.activities || results.activities.length)"
                class="tab-count"
              >
                {{ loading.activities ? '…' : results.activities.length }}
              </span>
            </button>
          </div>

          <!-- Tab panels -->
          <div class="tab-panel">
            <div v-show="activeTab === 'flights'" class="flight-panels">
              <div class="flight-panels__section">
                <h3 class="flight-panels__title">Outbound flight</h3>
                <FlightList
                  :flights="results.flights"
                  :loading="loading.flights"
                  :error="errors.flights"
                  :selected-flight="selectedFlight"
                  :deal-intel="dealIntel"
                  @select="selectFlight"
                />
              </div>

              <div v-if="searchParams.tripType === 'ROUNDTRIP'" class="flight-panels__section">
                <h3 class="flight-panels__title">Return flight</h3>
                <FlightList
                  :flights="results.returnFlights"
                  :loading="loading.returnFlights"
                  :error="errors.returnFlights"
                  :selected-flight="selectedReturnFlight"
                  :deal-intel="dealIntel"
                  @select="selectReturnFlight"
                />
              </div>
            </div>
            <HotelList
              v-show="activeTab === 'hotels'"
              :hotels="results.hotels"
              :loading="loading.hotels"
              :error="errors.hotels"
              :selected-hotel="selectedHotel"
              @select="selectHotel"
            />
            <ActivityList
              v-show="activeTab === 'activities'"
              :activities="results.activities"
              :loading="loading.activities"
              :error="errors.activities"
            />
          </div>
        </div>

        <!-- Right: Summary panel -->
        <SummaryPanel
          :trip-type="searchParams.tripType"
          :selected-flight="selectedFlight"
          :selected-return-flight="selectedReturnFlight"
          :selected-hotel="selectedHotel"
          :selected-activities="selectedActivities"
          :total-price="totalPrice"
          :has-selections="hasSelections"
          :is-booking="isBooking"
          :booking-result="bookingResult"
          :booking-error="bookingError"
          :is-authenticated="isAuthenticated"
          :user-email="userEmail"
          @book="handleBook"
          @clear="clearSelections"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  display: flex;
  flex-direction: column;
  min-height: calc(100vh - 56px);
  background: var(--color-bg);
}

/* Hero */
.hero {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4rem 2rem;
  background: var(--hero-gradient);
}

.hero__inner {
  text-align: center;
  max-width: 600px;
}

.hero__title {
  font-size: 2.5rem;
  font-weight: 800;
  color: var(--color-primary-dark);
  margin: 0 0 0.75rem;
  line-height: 1.15;
}

.hero__sub {
  font-size: 1.05rem;
  color: var(--color-text-muted);
  margin: 0 0 2.5rem;
  line-height: 1.6;
}

.hero__features {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.hero__feature {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.4rem;
  background: #fff;
  padding: 1rem 1.25rem;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(26, 54, 93, 0.08);
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--color-text);
  min-width: 90px;
}

.hero__feature-icon {
  font-size: 1.8rem;
}

/* ╔════════════════════════════════════════════════════════════╗
   ║  Expedia-style hero                                        ║
   ╚════════════════════════════════════════════════════════════╝ */
.hero-section {
  position: relative;
  padding: 3rem 1.5rem 2.5rem;
  isolation: isolate;
}

.hero-section__bg {
  position: absolute;
  inset: 0;
  z-index: -1;
  overflow: hidden;
  background:
    radial-gradient(ellipse at 80% 20%, rgba(255, 200, 100, 0.45), transparent 55%),
    radial-gradient(ellipse at 20% 90%, rgba(80, 180, 255, 0.4), transparent 55%),
    linear-gradient(135deg, #fff7e6 0%, #e6f1ff 50%, #f4ebff 100%);
}

.hero-section__bg::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    radial-gradient(circle at 15% 25%, rgba(255, 255, 255, 0.6) 1px, transparent 2px),
    radial-gradient(circle at 78% 65%, rgba(255, 255, 255, 0.5) 2px, transparent 3px),
    radial-gradient(circle at 45% 80%, rgba(255, 255, 255, 0.4) 1.5px, transparent 2.5px),
    radial-gradient(circle at 92% 35%, rgba(255, 255, 255, 0.5) 1px, transparent 2px);
  background-size: 200px 180px, 280px 240px, 220px 200px, 240px 220px;
  opacity: 0.6;
  animation: drift 30s linear infinite;
}

@keyframes drift {
  to { background-position: 200px 180px, 280px 240px, 220px 200px, 240px 220px; }
}

.hero-section__inner {
  max-width: 1100px;
  margin: 0 auto;
  text-align: center;
}

.hero-section__eyebrow {
  margin: 0 0 0.5rem;
  font-size: 0.8rem;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-primary-dark);
  opacity: 0.7;
}

.hero-section__title {
  margin: 0 0 1rem;
  font-size: clamp(2rem, 5vw, 3.5rem);
  line-height: 1.05;
  font-weight: 800;
  color: var(--color-primary-dark);
  letter-spacing: -0.02em;
  text-shadow: 0 2px 12px rgba(255, 255, 255, 0.5);
}

.hero-section__sub {
  margin: 0 0 2rem;
  color: var(--color-text);
  font-size: clamp(1rem, 1.4vw, 1.15rem);
  opacity: 0.85;
}

/* ─── Search/Forecast card wrapper ─── */
.home-card {
  background: rgba(255, 255, 255, 0.96);
  backdrop-filter: blur(12px);
  border-radius: 18px;
  padding: 0.5rem;
  box-shadow: 0 12px 40px rgba(26, 54, 93, 0.12);
  max-width: 1100px;
  margin: 0 auto;
  border: 1px solid rgba(255, 255, 255, 0.9);
}

.home-card :deep(.sp),
.home-card :deep(.price-forecast) {
  margin: 0;
  background: transparent;
  border: none;
  box-shadow: none;
}

.home-card :deep(.sp) {
  padding: 1.25rem;
}

.home-card :deep(.price-forecast) {
  padding: 1.25rem 1.5rem;
}

.home-card__divider {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0 1.5rem;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #97a8bd;
}

.home-card__divider::before,
.home-card__divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, #d6dde5, transparent);
}

/* ╔════════════════════════════════════════════════════════════╗
   ║  Feature cards (below hero, pre-search)                    ║
   ╚════════════════════════════════════════════════════════════╝ */
.features {
  max-width: 1100px;
  margin: 3rem auto 2rem;
  padding: 0 1.5rem;
}

.features__title {
  text-align: center;
  font-size: clamp(1.5rem, 3vw, 2rem);
  margin: 0 0 2rem;
  color: var(--color-primary-dark);
  font-weight: 800;
  letter-spacing: -0.01em;
}

.features__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1.25rem;
}

.feature-card {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 1.75rem;
  text-align: left;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.feature-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 28px rgba(26, 54, 93, 0.08);
}

.feature-card--accent {
  background: linear-gradient(135deg, #fff8e1 0%, #fff 100%);
  border: 1px solid #f9d175;
  position: relative;
}

.feature-card--accent::before {
  content: 'POPULAR';
  position: absolute;
  top: 1rem;
  right: 1rem;
  background: linear-gradient(90deg, #f39c12, #e67e22);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 800;
  letter-spacing: 0.1em;
  padding: 0.2rem 0.55rem;
  border-radius: 4px;
}

.feature-card__icon {
  font-size: 2.5rem;
  margin-bottom: 0.75rem;
}

.feature-card__title {
  margin: 0 0 0.5rem;
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--color-primary-dark);
}

.feature-card__sub {
  margin: 0;
  color: var(--color-text-muted);
  font-size: 0.95rem;
  line-height: 1.5;
}

/* ─── CTA strip ─── */
.cta-strip {
  margin-top: 2rem;
  padding: 1.5rem 2rem;
  border-radius: 16px;
  background: linear-gradient(135deg, var(--color-primary-dark) 0%, #2c5896 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.cta-strip__title {
  margin: 0 0 0.25rem;
  font-size: 1.2rem;
  font-weight: 800;
}

.cta-strip__sub {
  margin: 0;
  opacity: 0.85;
  font-size: 0.92rem;
}

.cta-strip__btn {
  background: #fff;
  color: var(--color-primary-dark);
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 10px;
  font-size: 0.95rem;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
  white-space: nowrap;
}

.cta-strip__btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.15);
}

@media (max-width: 600px) {
  .hero-section { padding: 2rem 1rem 1.5rem; }
  .home-modes { width: 100%; }
  .home-modes__tab { flex: 1; padding: 0.6rem 0.5rem; font-size: 0.85rem; }
  .cta-strip { flex-direction: column; text-align: center; }
}

/* Results */
.main-content {
  flex: 1;
}

.main-content--searched {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.results-layout {
  display: grid;
  grid-template-columns: 1fr 300px;
  height: calc(100vh - 56px - 90px); /* viewport - header - search panel */
  overflow: hidden;
}

.results-main {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--color-border);
}

/* Tabs */
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

.tab-btn:hover {
  color: var(--color-text);
}

.tab-btn--active {
  color: var(--color-primary);
  border-bottom-color: var(--color-primary);
}

.tab-icon {
  font-size: 1rem;
}

.tab-count {
  background: var(--color-primary-bg);
  color: var(--color-primary);
  font-size: 0.7rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 12px;
}

.tab-btn--active .tab-count {
  background: var(--color-primary);
  color: #fff;
}

/* Tab panel */
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
}

.flight-panels__section {
  background: #fff;
  border: 1px solid var(--color-border);
  border-radius: 12px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 240px);
  min-height: 400px;
}

.flight-panels__section > :deep(*:last-child) {
  flex: 1;
  overflow-y: auto;
}

.flight-panels__title {
  margin: 0;
  padding: 0.85rem 1rem;
  font-size: 0.9rem;
  font-weight: 700;
  color: var(--color-text);
  border-bottom: 1px solid var(--color-border);
  background: #fafcff;
  position: sticky;
  top: 0;
  z-index: 1;
}

@media (max-width: 1024px) {
  .flight-panels {
    grid-template-columns: 1fr;
  }
  .flight-panels__section {
    max-height: 60vh;
  }
}
</style>
