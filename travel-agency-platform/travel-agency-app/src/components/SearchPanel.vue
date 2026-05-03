<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  searchParams: { type: Object, required: true },
  loading: { type: Boolean, default: false },
})

const emit = defineEmits(['search', 'clear'])

// ─── Dual-month calendar state ───
const todayDate = new Date()
todayDate.setHours(0, 0, 0, 0)
const calendarAnchor = ref(new Date(todayDate.getFullYear(), todayDate.getMonth(), 1))

const MONTH_NAMES = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const WEEKDAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']

function isoDate(year, month, day) {
  const m = String(month + 1).padStart(2, '0')
  const d = String(day).padStart(2, '0')
  return `${year}-${m}-${d}`
}

function buildMonthGrid(anchor) {
  const year = anchor.getFullYear()
  const month = anchor.getMonth()
  const firstDay = new Date(year, month, 1).getDay() // 0 = Sun
  const daysInMonth = new Date(year, month + 1, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) cells.push(d)
  return { year, month, monthName: MONTH_NAMES[month], cells }
}

const leftMonth = computed(() => buildMonthGrid(calendarAnchor.value))
const rightMonth = computed(() => {
  const next = new Date(calendarAnchor.value)
  next.setMonth(next.getMonth() + 1)
  return buildMonthGrid(next)
})

function shiftMonths(delta) {
  const next = new Date(calendarAnchor.value)
  next.setMonth(next.getMonth() + delta)
  // Don't allow going earlier than today's month
  const minAnchor = new Date(todayDate.getFullYear(), todayDate.getMonth(), 1)
  if (next < minAnchor) return
  calendarAnchor.value = next
}

function isPast(year, month, day) {
  const d = new Date(year, month, day)
  return d < todayDate
}

function isSameDate(iso, year, month, day) {
  return iso === isoDate(year, month, day)
}

function isInRange(year, month, day) {
  const from = props.searchParams.fromDate
  const to = props.searchParams.toDate
  if (!from || !to) return false
  const d = isoDate(year, month, day)
  return d > from && d < to
}

function selectDate(year, month, day) {
  if (isPast(year, month, day)) return
  const iso = isoDate(year, month, day)
  const from = props.searchParams.fromDate
  const to = props.searchParams.toDate
  const isOneWay = props.searchParams.tripType === 'ONEWAY'

  if (isOneWay) {
    props.searchParams.fromDate = iso
    return
  }

  // Round trip — sequence: pick from, then to. Reset on third click.
  if (!from || (from && to)) {
    props.searchParams.fromDate = iso
    props.searchParams.toDate = ''
  } else if (iso <= from) {
    // Picked an earlier date → restart from there
    props.searchParams.fromDate = iso
    props.searchParams.toDate = ''
  } else {
    props.searchParams.toDate = iso
  }
}

const validationError = ref('')
const today = new Date().toISOString().split('T')[0]

// Popover state
const openPopover = ref(null) // 'dates' | 'travelers' | null

function togglePopover(name) {
  openPopover.value = openPopover.value === name ? null : name
}

function closePopover() {
  openPopover.value = null
}

// Close popovers when clicking outside
function handleDocClick(e) {
  if (!e.target.closest?.('.sp-field, .sp-popover')) {
    openPopover.value = null
  }
}

onMounted(() => document.addEventListener('mousedown', handleDocClick))
onBeforeUnmount(() => document.removeEventListener('mousedown', handleDocClick))

function handleTripTypeChange() {
  if (props.searchParams.tripType === 'ONEWAY') {
    props.searchParams.toDate = ''
  }
}

function handleSearch() {
  validationError.value = ''
  closePopover()
  try {
    emit('search')
  } catch (e) {
    validationError.value = e.message
  }
}

function handleClear() {
  validationError.value = ''
  closePopover()
  emit('clear')
}

// Travelers helpers
function bumpAdults(delta) {
  const next = Math.min(9, Math.max(1, Number(props.searchParams.adults || 1) + delta))
  props.searchParams.adults = next
}

function bumpChildren(delta) {
  const next = Math.min(9, Math.max(0, Number(props.searchParams.children || 0) + delta))
  props.searchParams.children = next
}

// Display strings
const datesLabel = computed(() => {
  const formatDay = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
  }
  const from = formatDay(props.searchParams.fromDate)
  const to = formatDay(props.searchParams.toDate)
  if (props.searchParams.tripType === 'ONEWAY') {
    return from || 'Pick a departure date'
  }
  if (from && to) return `${from} → ${to}`
  if (from) return `${from} → ?`
  return 'Pick travel dates'
})

const travelersLabel = computed(() => {
  const adults = Number(props.searchParams.adults || 1)
  const children = Number(props.searchParams.children || 0)
  const total = adults + children
  const travelerWord = total === 1 ? 'traveler' : 'travelers'
  if (children > 0) return `${total} ${travelerWord} (${adults} adult${adults>1?'s':''}, ${children} ${children>1?'children':'child'})`
  return `${total} ${travelerWord}`
})
</script>

<template>
  <div class="sp">
    <!-- Trip type pill toggle -->
    <div class="sp-trip-type">
      <button
        type="button"
        class="sp-trip-type__btn"
        :class="{ 'sp-trip-type__btn--active': searchParams.tripType === 'ROUNDTRIP' }"
        @click="searchParams.tripType = 'ROUNDTRIP'; handleTripTypeChange()"
      >Round trip</button>
      <button
        type="button"
        class="sp-trip-type__btn"
        :class="{ 'sp-trip-type__btn--active': searchParams.tripType === 'ONEWAY' }"
        @click="searchParams.tripType = 'ONEWAY'; handleTripTypeChange()"
      >One-way</button>
    </div>

    <!-- Main row -->
    <div class="sp-row">
      <!-- FROM -->
      <label class="sp-field">
        <span class="sp-field__icon">📍</span>
        <div class="sp-field__body">
          <span class="sp-field__label">Leaving from</span>
          <input
            v-model="searchParams.origin"
            class="sp-field__input"
            type="text"
            placeholder="Origin (e.g. JFK)"
            autocomplete="off"
          />
        </div>
      </label>

      <!-- TO -->
      <label class="sp-field">
        <span class="sp-field__icon">📍</span>
        <div class="sp-field__body">
          <span class="sp-field__label">Going to</span>
          <input
            v-model="searchParams.destination"
            class="sp-field__input"
            type="text"
            placeholder="Destination (e.g. CDG)"
            autocomplete="off"
          />
        </div>
      </label>

      <!-- DATES (popover) -->
      <div class="sp-field sp-field--button" :class="{ 'sp-field--open': openPopover === 'dates' }">
        <button type="button" class="sp-field__trigger" @click="togglePopover('dates')">
          <span class="sp-field__icon">📅</span>
          <div class="sp-field__body">
            <span class="sp-field__label">Dates</span>
            <span class="sp-field__value" :class="{ 'sp-field__value--placeholder': !searchParams.fromDate }">
              {{ datesLabel }}
            </span>
          </div>
        </button>

        <div v-if="openPopover === 'dates'" class="sp-popover sp-popover--cal" @mousedown.stop>
          <div class="sp-cal-help">
            {{ searchParams.tripType === 'ONEWAY'
              ? 'Pick your departure date.'
              : (!searchParams.fromDate
                  ? 'Step 1: Pick your departure date.'
                  : (!searchParams.toDate ? 'Step 2: Pick your return date.' : 'Click any new date to start over.')
                )
            }}
          </div>
          <div class="sp-cal">
            <button
              type="button"
              class="sp-cal__nav sp-cal__nav--prev"
              :disabled="(leftMonth.year === todayDate.getFullYear() && leftMonth.month === todayDate.getMonth())"
              @click="shiftMonths(-1)"
              aria-label="Previous month"
            >‹</button>

            <div class="sp-cal__month">
              <div class="sp-cal__title">{{ leftMonth.monthName }} {{ leftMonth.year }}</div>
              <div class="sp-cal__weekdays">
                <span v-for="w in WEEKDAY_LABELS" :key="`l-${w}`">{{ w }}</span>
              </div>
              <div class="sp-cal__grid">
                <button
                  v-for="(day, i) in leftMonth.cells"
                  :key="`l-${i}`"
                  type="button"
                  class="sp-cal__day"
                  :class="{
                    'sp-cal__day--empty': day === null,
                    'sp-cal__day--past': day !== null && isPast(leftMonth.year, leftMonth.month, day),
                    'sp-cal__day--start': day !== null && isSameDate(searchParams.fromDate, leftMonth.year, leftMonth.month, day),
                    'sp-cal__day--end':   day !== null && isSameDate(searchParams.toDate, leftMonth.year, leftMonth.month, day),
                    'sp-cal__day--in-range': day !== null && isInRange(leftMonth.year, leftMonth.month, day),
                  }"
                  :disabled="day === null || isPast(leftMonth.year, leftMonth.month, day)"
                  @click="day !== null && selectDate(leftMonth.year, leftMonth.month, day)"
                >{{ day === null ? '' : day }}</button>
              </div>
            </div>

            <div class="sp-cal__month">
              <div class="sp-cal__title">{{ rightMonth.monthName }} {{ rightMonth.year }}</div>
              <div class="sp-cal__weekdays">
                <span v-for="w in WEEKDAY_LABELS" :key="`r-${w}`">{{ w }}</span>
              </div>
              <div class="sp-cal__grid">
                <button
                  v-for="(day, i) in rightMonth.cells"
                  :key="`r-${i}`"
                  type="button"
                  class="sp-cal__day"
                  :class="{
                    'sp-cal__day--empty': day === null,
                    'sp-cal__day--past': day !== null && isPast(rightMonth.year, rightMonth.month, day),
                    'sp-cal__day--start': day !== null && isSameDate(searchParams.fromDate, rightMonth.year, rightMonth.month, day),
                    'sp-cal__day--end':   day !== null && isSameDate(searchParams.toDate, rightMonth.year, rightMonth.month, day),
                    'sp-cal__day--in-range': day !== null && isInRange(rightMonth.year, rightMonth.month, day),
                  }"
                  :disabled="day === null || isPast(rightMonth.year, rightMonth.month, day)"
                  @click="day !== null && selectDate(rightMonth.year, rightMonth.month, day)"
                >{{ day === null ? '' : day }}</button>
              </div>
            </div>

            <button type="button" class="sp-cal__nav sp-cal__nav--next" @click="shiftMonths(1)" aria-label="Next month">›</button>
          </div>
          <div class="sp-popover__footer">
            <button type="button" class="sp-popover__btn-primary" @click="closePopover">Done</button>
          </div>
        </div>
      </div>

      <!-- TRAVELERS (popover) -->
      <div class="sp-field sp-field--button" :class="{ 'sp-field--open': openPopover === 'travelers' }">
        <button type="button" class="sp-field__trigger" @click="togglePopover('travelers')">
          <span class="sp-field__icon">👤</span>
          <div class="sp-field__body">
            <span class="sp-field__label">Travelers</span>
            <span class="sp-field__value">{{ travelersLabel }}</span>
          </div>
        </button>

        <div v-if="openPopover === 'travelers'" class="sp-popover sp-popover--travelers" @mousedown.stop>
          <div class="sp-counter">
            <div>
              <div class="sp-counter__label">Adults</div>
              <div class="sp-counter__sub">Age 18+</div>
            </div>
            <div class="sp-counter__controls">
              <button type="button" class="sp-counter__btn" :disabled="searchParams.adults <= 1" @click="bumpAdults(-1)">−</button>
              <span class="sp-counter__value">{{ searchParams.adults }}</span>
              <button type="button" class="sp-counter__btn" :disabled="searchParams.adults >= 9" @click="bumpAdults(1)">+</button>
            </div>
          </div>
          <div class="sp-counter">
            <div>
              <div class="sp-counter__label">Children</div>
              <div class="sp-counter__sub">Ages 0–17</div>
            </div>
            <div class="sp-counter__controls">
              <button type="button" class="sp-counter__btn" :disabled="searchParams.children <= 0" @click="bumpChildren(-1)">−</button>
              <span class="sp-counter__value">{{ searchParams.children }}</span>
              <button type="button" class="sp-counter__btn" :disabled="searchParams.children >= 9" @click="bumpChildren(1)">+</button>
            </div>
          </div>
          <div class="sp-popover__footer">
            <button type="button" class="sp-popover__btn-primary" @click="closePopover">Done</button>
          </div>
        </div>
      </div>

      <!-- SEARCH -->
      <button class="sp-search" :disabled="loading" @click="handleSearch">
        <span v-if="loading" class="sp-spinner" />
        <span v-else>Search</span>
      </button>
    </div>

    <!-- Secondary actions -->
    <div class="sp-secondary">
      <button v-if="searchParams.origin || searchParams.destination || searchParams.fromDate" type="button" class="sp-secondary__btn" :disabled="loading" @click="handleClear">
        Clear
      </button>
      <p v-if="validationError" class="sp-error">{{ validationError }}</p>
    </div>
  </div>
</template>

<style scoped>
.sp {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 1rem 1.25rem;
}

/* Trip type toggle */
.sp-trip-type {
  display: inline-flex;
  background: #f3f6fa;
  padding: 0.25rem;
  border-radius: 999px;
  align-self: flex-start;
}

.sp-trip-type__btn {
  background: transparent;
  border: none;
  padding: 0.4rem 1rem;
  border-radius: 999px;
  font-size: 0.85rem;
  font-weight: 600;
  color: #6b7785;
  cursor: pointer;
  transition: all 0.15s;
}

.sp-trip-type__btn--active {
  background: #fff;
  color: #1a365d;
  box-shadow: 0 2px 6px rgba(26, 54, 93, 0.12);
}

/* Main row */
.sp-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1.4fr 1fr auto;
  gap: 0.5rem;
  align-items: stretch;
}

@media (max-width: 1024px) {
  .sp-row {
    grid-template-columns: 1fr 1fr;
  }
  .sp-search { grid-column: span 2; }
}

@media (max-width: 540px) {
  .sp-row { grid-template-columns: 1fr; }
  .sp-search { grid-column: span 1; }
}

/* Field card */
.sp-field {
  position: relative;
  display: flex;
  align-items: stretch;
  background: #fff;
  border: 1.5px solid #d6dde5;
  border-radius: 12px;
  transition: border-color 0.15s, box-shadow 0.15s;
  cursor: text;
  min-height: 64px;
}

.sp-field:hover {
  border-color: #97a8bd;
}

.sp-field:focus-within,
.sp-field--open {
  border-color: #1a73e8;
  box-shadow: 0 0 0 3px rgba(26, 115, 232, 0.15);
}

.sp-field--button {
  cursor: pointer;
}

.sp-field__trigger {
  display: flex;
  align-items: stretch;
  width: 100%;
  background: transparent;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: left;
}

.sp-field__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.1rem;
  padding: 0 0 0 0.85rem;
  flex-shrink: 0;
  pointer-events: none;
}

.sp-field__body {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0.5rem 0.85rem;
  flex: 1;
  min-width: 0;
}

.sp-field__label {
  font-size: 0.7rem;
  font-weight: 700;
  color: #6b7785;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 0.15rem;
}

.sp-field__input {
  background: transparent;
  border: none;
  padding: 0;
  font-size: 1rem;
  font-weight: 600;
  color: #1a2332;
  outline: none;
  width: 100%;
}

.sp-field__input::placeholder {
  color: #97a8bd;
  font-weight: 500;
}

.sp-field__value {
  font-size: 1rem;
  font-weight: 600;
  color: #1a2332;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sp-field__value--placeholder {
  color: #97a8bd;
  font-weight: 500;
}

/* Popovers */
.sp-popover {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  min-width: 320px;
  background: #fff;
  border: 1px solid #d6dde5;
  border-radius: 14px;
  padding: 1rem;
  box-shadow: 0 16px 40px rgba(15, 30, 60, 0.18);
  z-index: 1000;
  animation: sp-popover-in 0.15s ease-out;
}

@keyframes sp-popover-in {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

.sp-popover--cal {
  min-width: 660px;
  left: 50%;
  transform: translateX(-50%);
  right: auto;
}

.sp-popover--travelers {
  min-width: 320px;
}

.sp-cal-help {
  font-size: 0.85rem;
  color: #6b7785;
  margin-bottom: 0.85rem;
  font-weight: 500;
}

.sp-cal {
  display: grid;
  grid-template-columns: 32px 1fr 1fr 32px;
  gap: 1rem;
  align-items: start;
}

.sp-cal__nav {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid #d6dde5;
  background: #fff;
  color: #1a2332;
  font-size: 1.4rem;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.5rem;
  transition: all 0.15s;
  line-height: 1;
}

.sp-cal__nav:hover:not(:disabled) {
  background: #1a73e8;
  color: #fff;
  border-color: #1a73e8;
}

.sp-cal__nav:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.sp-cal__month {
  min-width: 0;
}

.sp-cal__title {
  text-align: center;
  font-size: 0.95rem;
  font-weight: 800;
  color: #1a2332;
  margin-bottom: 0.5rem;
}

.sp-cal__weekdays {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  text-align: center;
  font-size: 0.7rem;
  font-weight: 700;
  color: #97a8bd;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.sp-cal__grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 2px;
}

.sp-cal__day {
  aspect-ratio: 1 / 1;
  border: none;
  background: transparent;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  color: #1a2332;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sp-cal__day:hover:not(:disabled):not(.sp-cal__day--empty) {
  background: #e3effd;
  color: #1a73e8;
}

.sp-cal__day--empty {
  cursor: default;
  pointer-events: none;
}

.sp-cal__day--past {
  color: #c5cdd6;
  cursor: not-allowed;
  text-decoration: line-through;
}

.sp-cal__day--past:hover {
  background: transparent;
  color: #c5cdd6;
}

.sp-cal__day--in-range {
  background: #d6eaff;
  color: #1a2332;
  border-radius: 0;
}

.sp-cal__day--start,
.sp-cal__day--end {
  background: #1a73e8 !important;
  color: #fff !important;
  font-weight: 800;
}

.sp-cal__day--start {
  border-radius: 8px 0 0 8px;
}

.sp-cal__day--end {
  border-radius: 0 8px 8px 0;
}

.sp-cal__day--start.sp-cal__day--end {
  border-radius: 8px;
}

@media (max-width: 720px) {
  .sp-popover--cal {
    min-width: unset;
    width: calc(100vw - 1rem);
    left: 50%;
    transform: translateX(-50%);
  }
  .sp-cal {
    grid-template-columns: 28px 1fr 28px;
  }
  .sp-cal__month:nth-child(3) {
    display: none;
  }
}

@media (max-width: 540px) {
  .sp-popover {
    min-width: unset;
    width: calc(100vw - 2rem);
    left: 0;
  }
}

.sp-popover__footer {
  margin-top: 0.85rem;
  display: flex;
  justify-content: flex-end;
  padding-top: 0.5rem;
  border-top: 1px solid #f0f3f7;
}

.sp-popover__btn-primary {
  background: #1a73e8;
  color: #fff;
  border: none;
  padding: 0.55rem 1.4rem;
  border-radius: 999px;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s;
}

.sp-popover__btn-primary:hover {
  background: #1557b0;
}

/* Counter rows */
.sp-counter {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.7rem 0;
  border-bottom: 1px solid #f0f3f7;
}

.sp-counter:last-of-type {
  border-bottom: none;
  margin-bottom: 0.5rem;
}

.sp-counter__label {
  font-size: 1rem;
  font-weight: 700;
  color: #1a2332;
}

.sp-counter__sub {
  font-size: 0.78rem;
  color: #6b7785;
  margin-top: 0.1rem;
}

.sp-counter__controls {
  display: flex;
  align-items: center;
  gap: 0.85rem;
}

.sp-counter__btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1.5px solid #1a73e8;
  background: #fff;
  color: #1a73e8;
  font-size: 1.2rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sp-counter__btn:hover:not(:disabled) {
  background: #1a73e8;
  color: #fff;
}

.sp-counter__btn:disabled {
  border-color: #d6dde5;
  color: #d6dde5;
  cursor: not-allowed;
}

.sp-counter__value {
  font-size: 1.1rem;
  font-weight: 700;
  color: #1a2332;
  min-width: 1.5ch;
  text-align: center;
}

/* Search button */
.sp-search {
  background: linear-gradient(135deg, #1a73e8 0%, #1557b0 100%);
  color: #fff;
  border: none;
  border-radius: 12px;
  padding: 0 2rem;
  font-size: 1rem;
  font-weight: 800;
  cursor: pointer;
  transition: transform 0.1s, box-shadow 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 64px;
  box-shadow: 0 4px 12px rgba(26, 115, 232, 0.3);
}

.sp-search:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 18px rgba(26, 115, 232, 0.4);
}

.sp-search:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sp-spinner {
  width: 18px;
  height: 18px;
  border: 2.5px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: sp-spin 0.7s linear infinite;
}

@keyframes sp-spin {
  to { transform: rotate(360deg); }
}

/* Secondary row */
.sp-secondary {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-height: 1.2rem;
}

.sp-secondary__btn {
  background: transparent;
  border: none;
  color: #6b7785;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}

.sp-secondary__btn:hover {
  color: #1a73e8;
}

.sp-error {
  margin: 0;
  color: #c0392b;
  font-size: 0.88rem;
  font-weight: 600;
}
</style>
