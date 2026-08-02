/**
 * Plain-English cause for a failed request (SB-501).
 *
 * Gabe's whole experience of SB-522 was one line of red text reading
 * "HTTP 422". SB-523 fixed that on the print sheet; the logger had the same
 * problem, so the wording lives here rather than being written twice and
 * drifting.
 *
 * The raw message stays visible next to this, small — useful when debugging,
 * not shouted at the person using the app.
 */
export function explainStatus(status: number | null | undefined, action = 'load this'): string {
  switch (status) {
    case 401:
    case 403:
      return `You may not have access, or your session expired. Try signing in again.`
    case 404:
      return `We couldn't find it — it may have been deleted.`
    case 409:
      return `That conflicts with something already saved.`
    case 422:
      return `Something in the request was wrong, so the server turned it down. This is a bug on our side, not something you did.`
    default:
      if (status && status >= 500) return `The server had a problem. Trying again usually works.`
      return `Check your connection and try again — we couldn't ${action}.`
  }
}

/** The HTTP status apiCall attached to an error, when it has one. */
export function statusOf(e: unknown): number | null {
  return (e as { status?: number })?.status ?? null
}
