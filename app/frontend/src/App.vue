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

export default {
  name: 'App',
  components: {
    TheSidebar,
  },
}
</script>

<style>
/* Global styles */
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial,
    'Noto Sans', sans-serif, 'Apple Color Emoji', 'Segoe UI Emoji', 'Segoe UI Symbol',
    'Noto Color Emoji';
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  background-color: #f4f6f9;
}

.app-layout {
  display: flex;
}

.main-content {
  margin-left: 220px; /* Corresponds to sidebar width */
  flex-grow: 1;
  padding: 0;
  height: 100vh;
  overflow-y: auto;
}

/* Common component styles (can be moved to a separate file later) */
.page-container {
  padding: 1rem 2rem;
}
.page-header {
  border-bottom: 1px solid #e0e0e0;
  padding-bottom: 1rem;
  margin-bottom: 1.5rem;
}
.page-header h1 {
  font-size: 1.8rem;
  margin-bottom: 0.25rem;
}
.page-header p {
  color: #666;
  margin: 0;
}
.error-message {
  color: #e74c3c;
  background-color: #fdd;
  border: 1px solid #e74c3c;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}
.card {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  padding: 1.5rem;
  margin-bottom: 1.5rem;
}
.card-title {
  margin-top: 0;
  margin-bottom: 1.5rem;
  font-size: 1.4rem;
  display: flex;
  align-items: center;
}
.step {
  background-color: #1abc9c;
  color: white;
  border-radius: 50%;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 0.75rem;
}
.file-input-group,
.select-group {
  margin-bottom: 1rem;
}
.file-input-group:last-child,
.select-group:last-child {
  margin-bottom: 0;
}
.file-input-wrapper {
  display: flex;
  align-items: center;
}
.file-input-display {
  flex-grow: 1;
  border: 1px solid #ccc;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  background-color: #f9f9f9;
  color: #888;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-right: 0.5rem;
}
.file-input-display.has-file {
  background-color: #e8f5e9;
  color: #2e7d32;
}
.select-group {
  display: flex;
  gap: 1rem;
}
.select-item {
  display: flex;
  flex-direction: column;
}
.select-item label {
  margin-bottom: 0.25rem;
  font-size: 0.9rem;
  color: #555;
}
select {
  padding: 0.5rem;
  border-radius: 4px;
  border: 1px solid #ccc;
  background-color: white;
}
.btn-primary {
  background-color: #3498db;
  color: white;
  border: none;
  padding: 12px 24px;
  font-size: 1.1rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}
.btn-primary:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
}
.btn-primary:hover:not(:disabled) {
  background-color: #2980b9;
}
.file-input-btn {
  background-color: #95a5a6;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 5px 15px rgba(0,0,0,0.5);
  width: 90%;
  max-width: 600px;
}
.modal-content {
  padding: 2rem;
}
.modal-title {
  margin-top: 0;
  color: #2c3e50;
}
.modal-progress {
  margin: 1.5rem 0;
}
.progress-bar {
  background: #ecf0f1;
  border-radius: 4px;
  overflow: hidden;
}
.progress-fill {
  height: 20px;
  background: #1abc9c;
  transition: width 0.3s;
}
.progress-text {
  text-align: center;
  font-weight: bold;
  color: #34495e;
  margin-top: 0.5rem;
}
.modal-logs {
  max-height: 200px;
  overflow-y: auto;
  background: #f9f9f9;
  border: 1px solid #eee;
  padding: 0.75rem;
  border-radius: 4px;
}
.modal-log-item {
  display: flex;
  align-items: center;
  padding: 0.25rem 0;
}
.modal-log-item .icon {
  margin-right: 0.5rem;
}
.modal-complete-icon, .modal-error-icon, .modal-warning-icon {
  font-size: 3rem;
  text-align: center;
  margin-bottom: 1rem;
}
.modal-complete-icon { color: #27ae60; }
.modal-error-icon { color: #c0392b; }
.modal-warning-icon { color: #f39c12; }
.modal-result {
  margin: 1.5rem 0;
  background: #f9f9f9;
  border-radius: 4px;
  padding: 1rem;
}
.modal-result-item {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 0;
  border-bottom: 1px solid #eee;
}
.modal-result-item:last-child {
  border-bottom: none;
}
.modal-result-item .label {
  color: #555;
}
.modal-result-item .value {
  font-weight: bold;
}
.modal-result-item .value.highlight {
  color: #1abc9c;
  font-size: 1.2rem;
}
.modal-actions {
  text-align: right;
  margin-top: 1.5rem;
}
.btn-modal-close {
  background: #7f8c8d;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
}
.btn-modal-close:hover {
  background: #95a5a6;
}
.modal-error-message {
  background-color: #fff2f2;
  color: #c0392b;
  border: 1px solid #f5c6cb;
  padding: 1rem;
  border-radius: 4px;
  word-break: break-all;
}
.modal-school-list {
  max-height: 200px;
  overflow-y: auto;
  background: #f9f9f9;
  border: 1px solid #eee;
  padding: 0.75rem;
  border-radius: 4px;
  margin-top: 1rem;
}
.modal-school-item {
  padding: 0.25rem;
}
</style>