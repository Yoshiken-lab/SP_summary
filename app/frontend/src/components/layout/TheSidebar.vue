<template>
  <nav class="sidebar">
    <div class="sidebar-header">
      <h2>SP Sales</h2>
    </div>
    <ul class="nav-list">
      <li class="nav-item">
        <router-link to="/monthly" class="nav-link">
          <span class="icon">🌙</span>
          <span class="text">月次集計</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/cumulative" class="nav-link">
          <span class="icon">📊</span>
          <span class="text">累積集計</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/publish" class="nav-link">
          <span class="icon">🚀</span>
          <span class="text">実績反映</span>
        </router-link>
      </li>
      <li class="nav-item">
        <router-link to="/data" class="nav-link">
          <span class="icon">🔍</span>
          <span class="text">データ確認</span>
        </router-link>
      </li>
    </ul>
  </nav>
</template>

<script>
export default {
  name: 'TheSidebar',
}
</script>

<style scoped>
.sidebar {
  width: 220px;
  background-color: #2c3e50;
  color: #ecf0f1;
  display: flex;
  flex-direction: column;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
}

.sidebar-header {
  padding: 20px;
  text-align: center;
  border-bottom: 1px solid #34495e;
}

.sidebar-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: #1abc9c;
}

.nav-list {
  list-style: none;
  padding: 0;
  margin: 20px 0;
  flex-grow: 1;
}

.nav-item {
  margin: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  padding: 15px 20px;
  color: #ecf0f1;
  text-decoration: none;
  transition: background-color 0.3s;
  font-size: 1.1rem;
}

.nav-link:hover {
  background-color: #34495e;
}

.nav-link .icon {
  margin-right: 15px;
  font-size: 1.2rem;
}

/* スタイルは後で調整 */
.router-link-exact-active {
  background-color: #1abc9c;
  color: #ffffff;
  font-weight: bold;
}
</style>
