<template>
  <div id="app" class="min-h-screen flex flex-col">
    <AppHeader v-if="showChrome" />
    <main class="flex-grow">
      <RouterView />
    </main>
    <AppFooter v-if="showChrome" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, RouterView } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import AppFooter from './components/AppFooter.vue'

const route = useRoute()
// Hide header/footer on login and auth callback pages
const showChrome = computed(() =>
  !['login', 'auth-callback'].includes(route.name as string)
)
</script>
