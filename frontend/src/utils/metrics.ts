// Display conversion at the presentation edge: the backend stores canonical units
// (km, kg, reps), the UI shows miles / pounds / reps. See docs/UNITS.md.

const KM_TO_MI = 0.621371
const KG_TO_LB = 2.20462

/** Unit label shown to the user for a stored unit. */
export function displayUnit(storedUnit: string): string {
  if (storedUnit === 'km') return 'mi'
  if (storedUnit === 'kg') return 'lb'
  return storedUnit
}

/** Convert a stored value into its display unit. */
export function toDisplay(storedUnit: string, value: number): number {
  if (storedUnit === 'km') return value * KM_TO_MI
  if (storedUnit === 'kg') return value * KG_TO_LB
  return value
}

/** Convert a user-entered display value back to the stored (canonical) unit. */
export function toStored(storedUnit: string, displayValue: number): number {
  if (storedUnit === 'km') return displayValue / KM_TO_MI
  if (storedUnit === 'kg') return displayValue / KG_TO_LB
  return displayValue
}

/** Sensible decimal places for a display value by unit. */
export function displayDecimals(storedUnit: string): number {
  if (storedUnit === 'reps' || storedUnit === 'session') return 0
  return 1
}
