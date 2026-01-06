<template>
  <div class="app-layout">
    <TheSidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<script>
import TheSidebar from './components/layout/TheSidebar.vue'
import './assets/theme.css'
import './assets/element-dark.css'

export default {
  name: 'App',
  components: {
    TheSidebar,
  },
}
</script>

<style>
/* App Layout */
.app-layout {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  flex-grow: 1;
  margin-left: var(--sidebar-width);
  height: 100vh;
  overflow-y: auto;
  background-color: var(--bg-body);
}

/* Page Container */
.page-container {
  padding: var(--space-xl);
}
</style>