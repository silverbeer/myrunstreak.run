<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-brand-50 to-orange-100 px-4 py-12">
    <div class="bg-white rounded-2xl shadow-lg p-8 w-full max-w-sm">
      <LoginForm />
    </div>
  </div>
</template>

<script setup lang="ts">
import LoginForm from '@/components/LoginForm.vue'
</script>
