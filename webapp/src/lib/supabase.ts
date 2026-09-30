import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Missing Supabase environment variables')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

const originalSignOut = supabase.auth.signOut.bind(supabase.auth)
supabase.auth.signOut = async (options?: any) => {
  localStorage.removeItem('demo_session')
  window.location.href = '/login'
  return originalSignOut(options)
}
