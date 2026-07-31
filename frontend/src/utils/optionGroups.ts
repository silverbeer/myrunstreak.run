/**
 * Fold "pick one of N" alternatives into renderable rows (SB-448).
 *
 * Matthew's in-season aerobic day is an either/or — "20 minute steady run, 40
 * minute steady bike, or 5 minute steady jump rope" — not a checklist. Items
 * sharing an `option_group` are alternatives; a null group is mandatory.
 *
 * Every surface that renders a template needs the same fold, so it lives here
 * rather than inside one view.
 */
import type { TemplateItem } from '@/types/workout'

export type TemplateRow =
  | { kind: 'item'; item: TemplateItem }
  | { kind: 'group'; key: string; label: string; items: TemplateItem[] }

/**
 * Group alternatives, preserving order.
 *
 * A group lands at the position of its first member, and later members are
 * absorbed into it — so alternatives listed non-contiguously still render as
 * one block instead of repeating the heading.
 */
export function groupOptionItems(items: TemplateItem[]): TemplateRow[] {
  const rows: TemplateRow[] = []
  const groupIndex = new Map<string, number>()

  for (const item of [...items].sort((a, b) => a.position - b.position)) {
    const key = item.option_group
    if (!key) {
      rows.push({ kind: 'item', item })
      continue
    }
    const existing = groupIndex.get(key)
    if (existing === undefined) {
      groupIndex.set(key, rows.length)
      rows.push({
        kind: 'group',
        key,
        // The label is read from whichever member carries it, so a coach only
        // has to write it once.
        label: item.option_group_label || 'Pick one',
        items: [item],
      })
      continue
    }
    const row = rows[existing]
    if (row.kind === 'group') {
      row.items.push(item)
      if (!row.label && item.option_group_label) row.label = item.option_group_label
    }
  }

  return rows
}
