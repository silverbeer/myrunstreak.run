import type { TemplateBlock, TemplateItem } from '@/types/workout'

export interface BlockGroup {
  /** The circuit these items belong to, or null for items outside any. */
  block: TemplateBlock | null
  items: TemplateItem[]
}

/**
 * Split a section's items into circuits, in position order (SB-527).
 *
 * Partitioned rather than bucketed: a circuit stays contiguous, so the order
 * the coach wrote survives and an item that sits between two circuits does not
 * get swept into either. Items outside any block form an unlabelled group that
 * renders exactly as it did before circuits existed.
 *
 * Extracted from the print sheet (SB-528) when the card had to learn the same
 * shape (SB-543) — two copies of this would drift, and the screen disagreeing
 * with the paper about what the workout is, is the bug being fixed.
 */
export function groupByBlock(items: TemplateItem[], blocks: TemplateBlock[]): BlockGroup[] {
  const byId = new Map(blocks.map((b) => [b.id, b]))
  const groups: BlockGroup[] = []
  for (const item of items) {
    const block = (item.block_id && byId.get(item.block_id)) || null
    const last = groups[groups.length - 1]
    if (last && last.block?.id === block?.id) last.items.push(item)
    else groups.push({ block, items: [item] })
  }
  return groups
}

/**
 * How many rounds this group is done for.
 *
 * Rounds live on the circuit (SB-527); the template's own `rounds` is the
 * fallback for the blockless case — every template until that migration
 * backfilled, and any simple one since.
 */
export function roundsFor(group: BlockGroup, templateRounds: number | undefined): number {
  return group.block?.rounds ?? templateRounds ?? 1
}

/**
 * True when a template's own `rounds` still means something.
 *
 * Once its rounds live on blocks, `workout_templates.rounds` stays 1 and
 * showing it reads as "1 Round" on a workout done twice — the card stated the
 * opposite of the prescription for as long as circuits have existed (SB-543).
 */
export function templateRoundsAreMeaningful(blocks: TemplateBlock[] | undefined): boolean {
  return !blocks?.length
}
