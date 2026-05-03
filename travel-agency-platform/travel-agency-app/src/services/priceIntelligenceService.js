import api from './api.js'

function toAirportCode(value) {
  const code = String(value || '').trim().toUpperCase().replace(/[^A-Z]/g, '').slice(0, 3)
  return code ? `${code}.AIRPORT` : ''
}

export const priceIntelligenceService = {
  async getForecast({ origin, destination, months = 6, cabinClass = 'ECONOMY' }) {
    const fromCode = toAirportCode(origin)
    const toCode = toAirportCode(destination)
    if (!fromCode || !toCode) {
      throw new Error('Please enter valid origin and destination airport codes (e.g. JFK, CDG).')
    }
    return api.get('/flights/price-forecast', {
      params: { from_code: fromCode, to_code: toCode, months, cabin_class: cabinClass },
      timeout: 90000,
    })
  },

  async getCalendar({ origin, destination, yearMonth, cabinClass = 'ECONOMY' }) {
    const fromCode = toAirportCode(origin)
    const toCode = toAirportCode(destination)
    return api.get('/flights/price-calendar', {
      params: { from_code: fromCode, to_code: toCode, year_month: yearMonth, cabin_class: cabinClass },
      timeout: 60000,
    })
  },

  async getPriceHistory({ origin, destination, months = 6, cabinClass = 'ECONOMY' }) {
    const fromCode = toAirportCode(origin)
    const toCode = toAirportCode(destination)
    return api.get('/flights/price-history', {
      params: { from_code: fromCode, to_code: toCode, months, cabin_class: cabinClass },
    })
  },

  async getDealCheck({ origin, destination, currentPrice, cabinClass = 'ECONOMY', months = 6 }) {
    const fromCode = toAirportCode(origin)
    const toCode = toAirportCode(destination)
    return api.get('/flights/deal-check', {
      params: {
        from_code: fromCode,
        to_code: toCode,
        current_price: currentPrice,
        cabin_class: cabinClass,
        months,
      },
    })
  },
}
