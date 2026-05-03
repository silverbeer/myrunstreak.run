import { createClient } from '@supabase/supabase-js'

const getConfig = () => {
  if (typeof window !== 'undefined') {
    const { hostname } = window.location

    if (hostname === 'localhost' || hostname === '127.0.0.1') {
      return {
        url: 'http://localhost:54321',
        anonKey:
          'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0', // pragma: allowlist secret
      }
    }
  }

  return {
    url: import.meta.env.VITE_SUPABASE_URL as string,
    anonKey: import.meta.env.VITE_SUPABASE_ANON_KEY as string,
  }
}

const { url, anonKey } = getConfig()

export const supabase = createClient(url, anonKey, {
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true,
  },
})

export const getOAuthRedirectUrl = (): string => {
  if (typeof window !== 'undefined') {
    const { protocol, hostname, port } = window.location
    const portSuffix = port && port !== '80' && port !== '443' ? `:${port}` : ''
    return `${protocol}//${hostname}${portSuffix}/auth/callback`
  }
  return 'http://localhost:5174/auth/callback'
}

export default supabase
