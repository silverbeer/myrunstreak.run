import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { resolveLanding } from '@/composables/useLanding'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      redirect: '/dashboard',
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresGuest: true },
    },
    {
      path: '/signup',
      name: 'signup',
      component: () => import('@/views/SignupView.vue'),
      meta: { requiresGuest: true },
    },
    {
      path: '/auth/callback',
      name: 'auth-callback',
      component: () => import('@/views/AuthCallbackView.vue'),
    },
    {
      path: '/auth/reset-password',
      name: 'auth-reset-password',
      component: () => import('@/views/ResetPasswordView.vue'),
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/runs',
      name: 'runs',
      component: () => import('@/views/RunsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/runs/:activityId',
      name: 'run-detail',
      component: () => import('@/views/RunDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach',
      name: 'coach',
      component: () => import('@/views/CoachView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/AdminView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach/:athleteId',
      name: 'athlete-detail',
      component: () => import('@/views/AthleteDetailView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach/:athleteId/build',
      name: 'workout-builder',
      component: () => import('@/views/WorkoutBuilderView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach/:athleteId/build/:templateId',
      name: 'workout-editor',
      component: () => import('@/views/WorkoutBuilderView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach/:athleteId/log',
      name: 'workout-logger',
      component: () => import('@/views/WorkoutSessionLoggerView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/coach/:athleteId/log/:templateId',
      name: 'workout-logger-template',
      component: () => import('@/views/WorkoutSessionLoggerView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/exercises',
      name: 'exercise-catalog',
      component: () => import('@/views/ExerciseCatalogView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/profile',
      name: 'my-profile',
      component: () => import('@/views/MyProfileView.vue'),
      meta: { requiresAuth: true },
    },
  ],
  scrollBehavior(_to, _from, savedPosition) {
    return savedPosition ?? { top: 0 }
  },
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()

  if (!auth.session && !auth.loading) {
    await auth.initialize()
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta.requiresGuest && auth.isAuthenticated) {
    return resolveLanding()
  }

  // '/' is the only implicit entry (its redirect targets the dashboard);
  // route it by role so coaches don't land on a runner page (SB-265).
  // Explicit visits to /dashboard are left alone.
  if (auth.isAuthenticated && to.redirectedFrom?.path === '/') {
    const landing = await resolveLanding()
    if (landing !== '/dashboard') return landing
  }
})

export default router
