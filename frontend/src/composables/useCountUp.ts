import { ref, watch } from 'vue'

export function useCountUp(target: () => number, durationMs = 900) {
  const value = ref(0)
  let raf: number | null = null

  const prefersReducedMotion = () =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

  const animate = (to: number) => {
    if (raf !== null) cancelAnimationFrame(raf)
    // Reduced-motion: skip the count-up, show the final value immediately.
    if (prefersReducedMotion()) {
      value.value = to
      return
    }
    const from = value.value
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      const eased = 1 - Math.pow(1 - t, 3)
      value.value = Math.round(from + (to - from) * eased)
      if (t < 1) {
        raf = requestAnimationFrame(step)
      } else {
        raf = null
      }
    }
    raf = requestAnimationFrame(step)
  }

  watch(target, (next) => animate(next), { immediate: true })

  return value
}
