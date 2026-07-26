// Shared vitest setup (SB-345).
//
// The happy-dom test environment doesn't provide window.localStorage /
// sessionStorage here, so any test that touches them — or that loads a module
// which does at import time (useSync, useUserPreferences, and views/routers that
// pull them in) — crashes with "Cannot read properties of undefined". This
// installs a minimal in-memory Storage on window + globalThis when absent, so
// storage-backed code runs in tests without per-file shims.

class MemoryStorage implements Storage {
  private store = new Map<string, string>()

  get length(): number {
    return this.store.size
  }

  key(index: number): string | null {
    return Array.from(this.store.keys())[index] ?? null
  }

  getItem(key: string): string | null {
    return this.store.has(key) ? (this.store.get(key) as string) : null
  }

  setItem(key: string, value: string): void {
    this.store.set(key, String(value))
  }

  removeItem(key: string): void {
    this.store.delete(key)
  }

  clear(): void {
    this.store.clear()
  }
}

function install(name: 'localStorage' | 'sessionStorage'): void {
  const storage = new MemoryStorage()
  const targets: object[] = [globalThis]
  if (typeof window !== 'undefined') targets.push(window)
  for (const target of targets) {
    if (!(name in target) || (target as Record<string, unknown>)[name] == null) {
      Object.defineProperty(target, name, { value: storage, configurable: true, writable: true })
    }
  }
}

install('localStorage')
install('sessionStorage')
