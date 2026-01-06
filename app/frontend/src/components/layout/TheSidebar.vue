<template>
  <nav class="sidebar">
    <div class="brand">
      <div class="brand-icon"></div>
      <span class="brand-text">
        SP ADMIN <span class="brand-sub">PRO</span>
      </span>
    </div>
    
    <ul class="nav-menu">
      <li class="nav-item">
        <router-link to="/monthly" class="nav-link">
          <span class="icon">📅</span>
          <span class="text">月次集計</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/cumulative" class="nav-link">
          <span class="icon">📈</span>
          <span class="text">累積集計</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/publish" class="nav-link">
          <span class="icon">⚡</span>
          <span class="text">実績反映</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/data" class="nav-link">
          <span class="icon">💾</span>
          <span class="text">データベース確認</span>
        </router-link>
      </li>
    </ul>

    <div class="system-status">
      <div class="status-indicator">
        <div class="status-dot"></div>
        <span>サーバー稼働中</span>
      </div>
    </div>
  </nav>
</template>

<script>
export default {
  name: 'TheSidebar',
}
</script>

<style scoped>
.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  padding: var(--space-lg);
  z-index: 100;
}

/* Brand */
.brand {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 2.5rem;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.brand-icon {
  width: 24px;
  height: 24px;
  background: var(--gradient-brand);
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.brand-text {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
}

.brand-sub {
  font-weight: 400;
  opacity: 0.5;
}

/* Navigation Menu */
.nav-menu {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex-grow: 1;
}

.nav-item {
  margin: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9rem;
  transition: all var(--transition-fast);
  position: relative;
}

.nav-link:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.nav-link .icon {
  font-size: 1.2rem;
  flex-shrink: 0;
}

/* Active State */
.nav-link.router-link-exact-active,
.nav-link.router-link-active {
  background: rgba(88, 166, 255, 0.1);
  color: var(--accent-blue);
  font-weight: 500;
  border-left: 2px solid var(--accent-blue);
  padding-left: calc(1rem - 2px);
}

/* System Status */
.system-status {
  margin-top: auto;
  border-top: 1px solid var(--border-color);
  padding-top: var(--space-lg);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.8rem;
  color: var(--accent-green);
}

.status-dot {
  width: 8px;
  height: 8px;
  background: var(--accent-green);
  border-radius: 50%;
  box-shadow: 0 0 10px rgba(35, 134, 54, 0.5);
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}
</style>
