<script setup>
import { computed, ref, watch } from 'vue'
import { priceIntelligenceService } from '../services/priceIntelligenceService.js'

const props = defineProps({
  origin: { type: String, default: '' },
  destination: { type: String, default: '' },
})

const emit = defineEmits(['book-month'])

const isLoading = ref(false)
const errorMessage = ref('')
const forecast = ref(null)

// Number of full months remaining in the current calendar year (including current month).
// e.g. on 2026-05-03 → 8 (May, Jun, Jul, Aug, Sep, Oct, Nov, Dec)
function monthsRemainingInYear() {
  const now = new Date()
  return 12 - now.getMonth()
}

// Loading progress (animated 0 → 95 over ~25s; jumps to 100 when done)
const progress = ref(0)
let progressTimer = null

const monthLabel = (yearMonth) => {
  if (!yearMonth || yearMonth.length < 7) return yearMonth || ''
  const [year, month] = yearMonth.split('-')
  const d = new Date(Number(year), Number(month) - 1, 1)
  return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

const maxPrice = computed(() => {
  if (!forecast.value?.monthly_prices) return 0
  const valid = forecast.value.monthly_prices
    .map((m) => m.cheapest_price)
    .filter((p) => Number.isFinite(p))
  return valid.length ? Math.max(...valid) : 0
})

const bestMonth = computed(() => forecast.value?.deal_summary?.best_month_to_book || null)

const labelClass = computed(() => {
  const label = forecast.value?.deal_summary?.label
  if (label === 'Good Deal') return 'price-forecast__pill--good'
  if (label === 'Expensive') return 'price-forecast__pill--bad'
  return 'price-forecast__pill--avg'
})

// ---- Booking-from-forecast state ----
const selectedMonth = ref('')
const departDate = ref('')
const returnDate = ref('')
const tripType = ref('ROUNDTRIP')

const monthsAvailable = computed(() => forecast.value?.monthly_prices || [])

const selectedMonthPrice = computed(() => {
  const found = monthsAvailable.value.find((m) => m.month === selectedMonth.value)
  return found?.cheapest_price ?? null
})

function firstOfMonth(yearMonth) {
  if (!yearMonth) return ''
  return `${yearMonth}-01`
}

function addDaysIso(iso, days) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  d.setDate(d.getDate() + days)
  return d.toISOString().split('T')[0]
}

watch(selectedMonth, (newMonth) => {
  if (!newMonth) return
  departDate.value = firstOfMonth(newMonth)
  returnDate.value = addDaysIso(departDate.value, 7)
})

watch(bestMonth, (newBest) => {
  if (newBest && !selectedMonth.value) selectedMonth.value = newBest
})

function handleBookThisTrip() {
  if (!departDate.value) return
  emit('book-month', {
    origin: props.origin,
    destination: props.destination,
    fromDate: departDate.value,
    toDate: tripType.value === 'ROUNDTRIP' ? returnDate.value : '',
    tripType: tripType.value,
  })
}

function startProgressAnimation() {
  progress.value = 0
  if (progressTimer) clearInterval(progressTimer)
  progressTimer = setInterval(() => {
    if (progress.value < 95) {
      // ease out: faster near start, slower near end
      const remaining = 95 - progress.value
      progress.value += Math.max(0.4, remaining * 0.04)
    }
  }, 250)
}

function stopProgressAnimation() {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  progress.value = 100
  setTimeout(() => { progress.value = 0 }, 400)
}

async function fetchForecast() {
  errorMessage.value = ''
  forecast.value = null
  selectedMonth.value = ''
  isLoading.value = true
  startProgressAnimation()
  try {
    forecast.value = await priceIntelligenceService.getForecast({
      origin: props.origin,
      destination: props.destination,
      months: monthsRemainingInYear(),
    })
  } catch (error) {
    errorMessage.value = error.message || 'Failed to fetch price forecast.'
  } finally {
    isLoading.value = false
    stopProgressAnimation()
  }
}
</script>

<template>
  <section class="price-forecast">
    <div class="price-forecast__header">
      <div>
        <h2 class="price-forecast__title">Best Time to Travel</h2>
        <p class="price-forecast__sub">
          Discover the cheapest month to fly over the next 6 months — uses live price snapshots and historical trends.
        </p>
      </div>
      <button
        class="price-forecast__cta"
        :disabled="isLoading || !origin || !destination"
        @click="fetchForecast"
      >
        {{ isLoading ? 'Crunching prices…' : 'Find Cheapest Month' }}
      </button>
    </div>

    <p v-if="!origin || !destination" class="price-forecast__hint">
      Enter origin and destination above to enable the forecast.
    </p>

    <p v-if="errorMessage" class="price-forecast__error">{{ errorMessage }}</p>

    <div v-if="isLoading" class="price-forecast__loading">
      <div class="price-forecast__loading-text">
        <span class="price-forecast__plane">✈️</span>
        Searching the rest of the year for the cheapest fares…
      </div>
      <div class="price-forecast__progress">
        <div class="price-forecast__progress-bar" :style="{ width: `${progress}%` }">
          <div class="price-forecast__progress-stripes"></div>
        </div>
      </div>
      <div class="price-forecast__progress-pct">{{ Math.round(progress) }}%</div>
    </div>

    <div v-if="forecast && !isLoading" class="price-forecast__body">
      <div class="price-forecast__chart">
        <div class="price-forecast__chart-caption">
          Cheapest one-way economy fare for 1 adult, departing the 1st of each remaining month this year (USD).
        </div>
        <div
          v-for="month in forecast.monthly_prices"
          :key="month.month"
          class="price-forecast__bar-row"
          :class="{ 'price-forecast__bar-row--best': month.month === bestMonth }"
        >
          <div class="price-forecast__bar-label">{{ monthLabel(month.month) }}</div>
          <div class="price-forecast__bar-track">
            <div
              class="price-forecast__bar-fill"
              :class="{ 'price-forecast__bar-fill--best': month.month === bestMonth }"
              :style="{
                width: maxPrice > 0 && Number.isFinite(month.cheapest_price)
                  ? `${(month.cheapest_price / maxPrice) * 100}%`
                  : '0%',
              }"
            >
              <span class="price-forecast__bar-price">
                {{ Number.isFinite(month.cheapest_price) ? `$${Math.round(month.cheapest_price)}` : 'N/A' }}
              </span>
            </div>
          </div>
          <span v-if="month.month === bestMonth" class="price-forecast__star">⭐ BEST</span>
        </div>
      </div>

      <div v-if="forecast.deal_summary" class="price-forecast__summary">
        <div class="price-forecast__pill" :class="labelClass">
          {{ forecast.deal_summary.label }}
        </div>
        <div class="price-forecast__advice">{{ forecast.deal_summary.advice }}</div>
        <div class="price-forecast__stats">
          <div><span>Lowest</span><strong>${{ forecast.deal_summary.lowest_price }}</strong></div>
          <div><span>Average</span><strong>${{ forecast.deal_summary.average_price }}</strong></div>
          <div><span>Highest</span><strong>${{ forecast.deal_summary.highest_price }}</strong></div>
        </div>
      </div>
    </div>

    <!-- Book This Trip panel — appears once forecast is loaded -->
    <div v-if="forecast && !isLoading && monthsAvailable.length" class="price-forecast__book">
      <div class="price-forecast__book-header">
        <h3 class="price-forecast__book-title">⭐ Book Your Trip</h3>
        <p class="price-forecast__book-sub">Cheapest month is pre-selected — change any field to customize.</p>
      </div>

      <div class="price-forecast__book-grid">
        <label class="price-forecast__field">
          Travel Month
          <select v-model="selectedMonth" class="price-forecast__input">
            <option v-for="m in monthsAvailable" :key="m.month" :value="m.month">
              {{ monthLabel(m.month) }}{{ Number.isFinite(m.cheapest_price) ? ` — $${Math.round(m.cheapest_price)}` : '' }}{{ m.month === bestMonth ? ' ⭐' : '' }}
            </option>
          </select>
        </label>

        <label class="price-forecast__field">
          Trip Type
          <select v-model="tripType" class="price-forecast__input">
            <option value="ROUNDTRIP">Round trip</option>
            <option value="ONEWAY">One way</option>
          </select>
        </label>

        <label class="price-forecast__field">
          Departure
          <input v-model="departDate" type="date" class="price-forecast__input" />
        </label>

        <label v-if="tripType === 'ROUNDTRIP'" class="price-forecast__field">
          Return
          <input v-model="returnDate" type="date" class="price-forecast__input" />
        </label>
      </div>

      <div class="price-forecast__book-footer">
        <div class="price-forecast__est">
          <span class="price-forecast__est-label">From (1 adult · one-way · economy)</span>
          <strong class="price-forecast__est-price">
            {{ Number.isFinite(selectedMonthPrice) ? `$${Math.round(selectedMonthPrice)}` : '—' }}
          </strong>
          <span class="price-forecast__est-note">
            Final fare depends on trip type, passengers, and exact dates.
          </span>
        </div>
        <button class="price-forecast__book-btn" :disabled="!departDate" @click="handleBookThisTrip">
          Search This Trip →
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.price-forecast {
  background: linear-gradient(135deg, #f6f9ff 0%, #eef4ff 100%);
  border: 1px solid var(--color-border);
  border-radius: 18px;
  padding: 1.5rem;
  margin: 1rem auto;
  max-width: 1200px;
  box-shadow: 0 6px 18px rgba(26, 54, 93, 0.05);
}

.price-forecast__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.price-forecast__title {
  margin: 0;
  font-size: 1.25rem;
  color: var(--color-primary-dark);
}

.price-forecast__sub {
  margin: 0.25rem 0 0;
  color: var(--color-text-muted);
  font-size: 0.9rem;
  max-width: 60ch;
}

.price-forecast__cta {
  background: var(--color-primary-dark);
  color: #fff;
  border: none;
  padding: 0.65rem 1.25rem;
  border-radius: 10px;
  font-weight: 700;
  cursor: pointer;
  transition: opacity 0.15s;
}

.price-forecast__cta:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.price-forecast__hint {
  margin: 0.75rem 0 0;
  color: var(--color-text-muted);
  font-size: 0.85rem;
  font-style: italic;
}

.price-forecast__error {
  margin: 0.75rem 0 0;
  color: #c0392b;
  font-weight: 600;
}

.price-forecast__loading {
  margin: 1rem 0 0;
  padding: 1.25rem;
  background: #fff;
  border-radius: 12px;
  color: var(--color-text-muted);
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.price-forecast__loading-text {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 600;
  color: var(--color-primary-dark);
}

.price-forecast__plane {
  display: inline-block;
  font-size: 1.2rem;
  animation: plane-fly 1.6s ease-in-out infinite;
}

@keyframes plane-fly {
  0%, 100% { transform: translateX(0) rotate(0deg); }
  50%      { transform: translateX(8px) rotate(-8deg); }
}

.price-forecast__progress {
  height: 14px;
  background: #eef2f7;
  border-radius: 999px;
  overflow: hidden;
  position: relative;
}

.price-forecast__progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #4a78b8, #2ecc71);
  border-radius: 999px;
  transition: width 0.25s ease-out;
  position: relative;
  overflow: hidden;
}

.price-forecast__progress-stripes {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(
    45deg,
    rgba(255, 255, 255, 0.25) 25%,
    transparent 25%,
    transparent 50%,
    rgba(255, 255, 255, 0.25) 50%,
    rgba(255, 255, 255, 0.25) 75%,
    transparent 75%,
    transparent
  );
  background-size: 24px 24px;
  animation: stripe-slide 1s linear infinite;
}

@keyframes stripe-slide {
  from { background-position: 0 0; }
  to   { background-position: 24px 0; }
}

.price-forecast__progress-pct {
  text-align: right;
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--color-primary-dark);
}

.price-forecast__body {
  margin-top: 1.25rem;
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1.25rem;
}

@media (max-width: 768px) {
  .price-forecast__body {
    grid-template-columns: 1fr;
  }
}

.price-forecast__chart {
  background: #fff;
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
}

.price-forecast__chart-caption {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  font-style: italic;
  margin-bottom: 0.25rem;
}

.price-forecast__bar-row {
  display: grid;
  grid-template-columns: 90px 1fr 70px;
  align-items: center;
  gap: 0.5rem;
}

.price-forecast__bar-label {
  font-size: 0.85rem;
  color: var(--color-text-muted);
  font-weight: 600;
}

.price-forecast__bar-track {
  background: #eef2f7;
  border-radius: 6px;
  height: 28px;
  overflow: hidden;
  position: relative;
}

.price-forecast__bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #6498d4, #4a78b8);
  display: flex;
  align-items: center;
  padding: 0 0.65rem;
  transition: width 0.4s ease-out;
  min-width: 50px;
}

.price-forecast__bar-fill--best {
  background: linear-gradient(90deg, #2ecc71, #27ae60);
}

.price-forecast__bar-price {
  color: #fff;
  font-weight: 700;
  font-size: 0.85rem;
  white-space: nowrap;
}

.price-forecast__star {
  font-size: 0.75rem;
  font-weight: 700;
  color: #27ae60;
  white-space: nowrap;
}

.price-forecast__summary {
  background: #fff;
  border-radius: 12px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.price-forecast__pill {
  align-self: flex-start;
  padding: 0.4rem 0.85rem;
  border-radius: 999px;
  font-weight: 700;
  font-size: 0.85rem;
}

.price-forecast__pill--good {
  background: #d4edda;
  color: #155724;
}

.price-forecast__pill--avg {
  background: #fff3cd;
  color: #856404;
}

.price-forecast__pill--bad {
  background: #f8d7da;
  color: #721c24;
}

.price-forecast__advice {
  color: var(--color-text);
  font-size: 0.95rem;
  line-height: 1.4;
}

.price-forecast__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.5rem;
  margin-top: auto;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-border);
}

.price-forecast__stats > div {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.price-forecast__stats span {
  font-size: 0.75rem;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.price-forecast__stats strong {
  font-size: 1rem;
  color: var(--color-primary-dark);
}

/* ---- Book This Trip panel ---- */
.price-forecast__book {
  margin-top: 1.25rem;
  background: #fff;
  border: 2px solid #2ecc71;
  border-radius: 14px;
  padding: 1.25rem;
  box-shadow: 0 8px 24px rgba(46, 204, 113, 0.12);
  animation: panel-slide-in 0.4s ease-out;
}

@keyframes panel-slide-in {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.price-forecast__book-header {
  margin-bottom: 1rem;
}

.price-forecast__book-title {
  margin: 0;
  color: #27ae60;
  font-size: 1.1rem;
}

.price-forecast__book-sub {
  margin: 0.25rem 0 0;
  color: var(--color-text-muted);
  font-size: 0.85rem;
}

.price-forecast__book-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.price-forecast__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: var(--color-text-muted);
  font-weight: 600;
}

.price-forecast__input {
  padding: 0.5rem 0.65rem;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  font-size: 0.9rem;
  color: var(--color-text);
  background: #fff;
  font-weight: 500;
}

.price-forecast__input:focus {
  outline: none;
  border-color: #27ae60;
  box-shadow: 0 0 0 3px rgba(46, 204, 113, 0.15);
}

.price-forecast__book-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 1rem;
  padding-top: 0.75rem;
  border-top: 1px solid #ecf0f1;
  flex-wrap: wrap;
}

.price-forecast__est {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.price-forecast__est-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-text-muted);
}

.price-forecast__est-price {
  font-size: 1.5rem;
  color: #27ae60;
  font-weight: 800;
}

.price-forecast__est-note {
  font-size: 0.7rem;
  color: var(--color-text-muted);
  font-style: italic;
  max-width: 32ch;
}

.price-forecast__book-btn {
  background: linear-gradient(90deg, #2ecc71, #27ae60);
  color: #fff;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 10px;
  font-weight: 700;
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.15s;
  box-shadow: 0 4px 12px rgba(46, 204, 113, 0.25);
}

.price-forecast__book-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(46, 204, 113, 0.35);
}

.price-forecast__book-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  box-shadow: none;
}
</style>
