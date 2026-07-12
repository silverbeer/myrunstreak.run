import type { RunFilters, Unit } from '@/types/runs'

/** Result of parsing a natural-language run query (SB-269).
 *  `chips` are human labels for what was understood; `ignored` is what wasn't. */
export interface ParsedRunQuery {
  filters: RunFilters
  chips: string[]
  ignored: string[]
}

const KM_PER_MI = 1.609344

const WEATHER_WORDS: Record<string, string> = {
  rain: 'rainy',
  rainy: 'rainy',
  wet: 'rainy',
  sun: 'sunny',
  sunny: 'sunny',
  clear: 'sunny',
  cloud: 'cloudy',
  cloudy: 'cloudy',
  overcast: 'cloudy',
  snow: 'snowy',
  snowy: 'snowy',
  wind: 'windy',
  windy: 'windy',
}

// Temperature qualifiers (C) — 'hot' matches the detail view's heat threshold.
const TEMP_WORDS: Record<string, Partial<RunFilters>> = {
  hot: { temp_min: 24 },
  warm: { temp_min: 20 },
  cool: { temp_max: 15 },
  cold: { temp_max: 5 },
  freezing: { temp_max: 0 },
}

const SORT_WORDS: Record<string, Pick<RunFilters, 'sort' | 'order'>> = {
  fastest: { sort: 'pace', order: 'asc' },
  slowest: { sort: 'pace', order: 'desc' },
  longest: { sort: 'distance', order: 'desc' },
  shortest: { sort: 'distance', order: 'asc' },
  hottest: { sort: 'temperature', order: 'desc' },
  coldest: { sort: 'temperature', order: 'asc' },
}

const MONTHS = [
  'january', 'february', 'march', 'april', 'may', 'june',
  'july', 'august', 'september', 'october', 'november', 'december',
]

const SEASONS: Record<string, [number, number]> = {
  spring: [3, 5],
  summer: [6, 8],
  fall: [9, 11],
  autumn: [9, 11],
  winter: [12, 2], // spans the year boundary
}

const STOPWORDS = new Set([
  'run', 'runs', 'runner', 'in', 'the', 'a', 'an', 'of', 'on', 'at', 'my',
  'with', 'and', 'from', 'during', 'all', 'show', 'me', 'find', 'pace',
])

const iso = (d: Date) => d.toISOString().slice(0, 10)

/** "9:30" or "9" -> minutes as float (9.5 / 9). */
const parseClock = (s: string): number | null => {
  const m = s.match(/^(\d{1,2})(?::(\d{2}))?$/)
  if (!m) return null
  return Number(m[1]) + (m[2] ? Number(m[2]) / 60 : 0)
}

/**
 * Parse a free-text query like "rainy 5 milers last summer" or
 * "hot runs under 9:30" into run filters. Deterministic token grammar —
 * every understood token becomes a visible chip, so the translation is
 * transparent. Distances/paces are interpreted in the user's unit.
 */
export function parseRunQuery(
  query: string,
  unit: Unit,
  today: Date = new Date(),
): ParsedRunQuery {
  const filters: RunFilters = {}
  const chips: string[] = []
  const ignored: string[] = []

  const toKm = (v: number) => (unit === 'mi' ? v * KM_PER_MI : v)
  const paceToKm = (v: number) => (unit === 'mi' ? v / KM_PER_MI : v)
  const year = today.getFullYear()

  const setRange = (from: Date, to: Date, label: string) => {
    filters.date_from = iso(from)
    filters.date_to = iso(to)
    chips.push(label)
  }

  // Normalize: keep :,-,digits; split words.
  const tokens = query
    .toLowerCase()
    .replace(/[^\w:.\-\s]/g, ' ')
    .split(/\s+/)
    .filter(Boolean)

  let i = 0
  while (i < tokens.length) {
    const tok = tokens[i]
    const next = tokens[i + 1] ?? ''
    const prev = tokens[i - 1] ?? ''

    // --- pace comparisons: "under 9:30", "sub 9", "faster than 9:00" ---
    if (['under', 'sub', 'below', 'faster'].includes(tok)) {
      const target = next === 'than' ? tokens[i + 2] : next
      const mins = target ? parseClock(target) : null
      if (mins !== null) {
        filters.pace_max = Number(paceToKm(mins).toFixed(4))
        chips.push(`pace under ${target}/${unit}`)
        i += next === 'than' ? 3 : 2
        continue
      }
    }
    if (['over', 'above', 'slower'].includes(tok)) {
      const target = next === 'than' ? tokens[i + 2] : next
      const mins = target ? parseClock(target) : null
      if (mins !== null && mins > 3) {
        filters.pace_min = Number(paceToKm(mins).toFixed(4))
        chips.push(`pace over ${target}/${unit}`)
        i += next === 'than' ? 3 : 2
        continue
      }
    }

    // --- distance: "5 miler(s)", "5 mi", "10 km", "5k" ---
    const dm = tok.match(/^(\d+(?:\.\d+)?)(k|km|mi|mile|miles|miler|milers)?$/)
    if (dm) {
      const value = Number(dm[1])
      let suffix = dm[2]
      if (!suffix && /^(mi|mile|miles|miler|milers|km|k)$/.test(next)) {
        suffix = next
        i += 1
      }
      if (suffix) {
        const km = suffix.startsWith('k') ? value : value * KM_PER_MI
        filters.distance_min = Number((km - 0.5).toFixed(3))
        filters.distance_max = Number((km + 0.5).toFixed(3))
        chips.push(`~${value} ${suffix.startsWith('k') ? 'km' : 'mi'}`)
        i += 1
        continue
      }
      // Bare 4-digit year
      if (/^(19|20)\d{2}$/.test(tok)) {
        setRange(new Date(Date.UTC(value, 0, 1)), new Date(Date.UTC(value, 11, 31)), tok)
        i += 1
        continue
      }
    }

    // --- long/short shorthands ---
    if (tok === 'long') {
      filters.distance_min = Number(toKm(5).toFixed(3))
      chips.push(`5+ ${unit}`)
      i += 1
      continue
    }
    if (tok === 'short') {
      filters.distance_max = Number(toKm(3).toFixed(3))
      chips.push(`< 3 ${unit}`)
      i += 1
      continue
    }

    // --- sort words ---
    if (tok in SORT_WORDS) {
      Object.assign(filters, SORT_WORDS[tok])
      chips.push(tok)
      i += 1
      continue
    }

    // --- weather / temperature ---
    if (tok in WEATHER_WORDS) {
      filters.weather_type = WEATHER_WORDS[tok]
      chips.push(WEATHER_WORDS[tok])
      i += 1
      continue
    }
    if (tok in TEMP_WORDS) {
      Object.assign(filters, TEMP_WORDS[tok])
      chips.push(tok)
      i += 1
      continue
    }

    // --- seasons (optionally preceded by "last"/"this") ---
    if (tok in SEASONS) {
      const [m1, m2] = SEASONS[tok]
      let y = year
      const currentMonth = today.getMonth() + 1
      const startedThisYear = currentMonth >= m1 || (m1 > m2 && currentMonth <= m2)
      if (prev === 'last') y = startedThisYear ? y - 1 : y - 1
      else if (!startedThisYear) y = y - 1
      const from = new Date(Date.UTC(y, m1 - 1, 1))
      const endYear = m1 > m2 ? y + 1 : y
      const to = new Date(Date.UTC(endYear, m2, 0)) // day 0 = last day of month m2
      setRange(from, to, `${prev === 'last' ? 'last ' : ''}${tok} ${y}`)
      i += 1
      continue
    }

    // --- month names (optional trailing year) ---
    const monthIdx = MONTHS.indexOf(tok)
    if (monthIdx >= 0) {
      let y = year
      if (/^(19|20)\d{2}$/.test(next)) {
        y = Number(next)
        i += 1
      } else if (monthIdx + 1 > today.getMonth() + 1) {
        y = year - 1 // "december" said in July means last December
      }
      setRange(
        new Date(Date.UTC(y, monthIdx, 1)),
        new Date(Date.UTC(y, monthIdx + 1, 0)),
        `${tok} ${y}`,
      )
      i += 1
      continue
    }

    // --- relative years ---
    if (tok === 'last' && next === 'year') {
      setRange(new Date(Date.UTC(year - 1, 0, 1)), new Date(Date.UTC(year - 1, 11, 31)), `${year - 1}`)
      i += 2
      continue
    }
    if (tok === 'this' && next === 'year') {
      setRange(new Date(Date.UTC(year, 0, 1)), today, `${year}`)
      i += 2
      continue
    }
    if (tok === 'last' && (next in SEASONS || MONTHS.includes(next))) {
      i += 1 // consumed by the season/month branch via `prev`
      continue
    }

    if (!STOPWORDS.has(tok)) ignored.push(tok)
    i += 1
  }

  return { filters, chips, ignored }
}
