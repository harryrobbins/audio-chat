<script setup lang="ts">
// Main application shell
</script>

<template>
  <header class="govuk-header" id="main-header">
    <div class="max-w-7xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-3">
        <!-- SVG Crown/Emblem of the UK Government -->
        <svg class="h-8 w-8 text-govuk-yellow fill-current" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
          <path d="M50 15 L58 35 L78 35 L62 48 L68 68 L50 55 L32 68 L38 48 L22 35 L42 35 Z" />
          <rect x="42" y="72" width="16" height="5" />
          <rect x="45" y="80" width="10" height="5" />
        </svg>
        <div>
          <span class="block text-2xl font-bold tracking-wider font-govuk">GOV.UK</span>
          <span class="block text-xs uppercase tracking-widest text-govuk-grey-3 font-semibold">Department for Agentic Audio Research</span>
        </div>
      </div>
      <div class="hidden sm:flex items-center gap-4 text-sm font-semibold">
        <router-link to="/" class="hover:text-govuk-yellow transition-colors">Dashboard</router-link>
        <span class="text-govuk-grey-2">|</span>
        <span class="text-govuk-green flex items-center gap-1.5">
          <span class="h-2.5 w-2.5 rounded-full bg-govuk-green animate-pulse"></span>
          AI Agents Active
        </span>
      </div>
    </div>
  </header>

  <div class="border-b-4 border-govuk-yellow bg-govuk-white shadow-sm py-2 px-4 mb-6">
    <div class="max-w-7xl mx-auto flex items-center justify-between text-sm text-govuk-grey-1 font-govuk">
      <div class="flex items-center gap-2">
        <span class="font-bold">Kokoro-82M</span>
        <span class="bg-govuk-blue text-white text-[10px] px-1.5 py-0.5 font-bold uppercase rounded">Beta</span>
        <span class="text-govuk-grey-2">|</span>
        <span>Transform documents into dual-speaker British-voice podcasts</span>
      </div>
      <div class="text-xs text-govuk-grey-2">
        Version 0.1.0 (Google ADK v1.1)
      </div>
    </div>
  </div>

  <main class="govuk-container font-govuk min-h-[calc(100vh-140px)]">
    <router-view />
  </main>

  <footer class="bg-govuk-black border-t-8 border-govuk-blue text-govuk-grey-3 py-8 mt-12 text-sm">
    <div class="max-w-7xl mx-auto px-4 flex flex-col md:flex-row justify-between items-center gap-4">
      <div>
        <p class="font-bold text-govuk-white mb-1">Crown Copyright © 2026</p>
        <p>All content is available under the Open Government Licence v3.0, except where otherwise stated.</p>
      </div>
      <div class="flex gap-4">
        <a href="https://github.com/google/adk" target="_blank" class="hover:text-govuk-white underline">Google ADK</a>
        <a href="https://huggingface.co/hexgrad/Kokoro-82M" target="_blank" class="hover:text-govuk-white underline">Kokoro-82M</a>
      </div>
    </div>
  </footer>
</template>

<style>
/* Custom transitions for router view changes */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
