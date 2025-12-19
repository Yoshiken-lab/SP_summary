<template>
  <div class="page-container">
    <!-- ヘッダー -->
    <header class="page-header">
      <h1>月次集計</h1>
      <p>CSVデータから売上を集計し、Excel報告書を作成します</p>
    </header>

    <!-- エラー表示 -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- Step 1: ファイル選択 -->
    <div v-if="currentStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">1</span>
        データファイルを選択
      </h2>

      <div class="file-input-group">
        <label>売上データ (CSV)</label>
        <div class="file-input-wrapper">
          <div :class="['file-input-display', { 'has-file': files.sales }]">
            {{ files.sales ? files.sales.name : 'ファイルが選択されていません' }}
          </div>
          <input
            type="file"
            accept=".csv"
            @change="e => selectFile('sales', e)"
            ref="salesInput"
            style="display: none"
          >
          <button class="file-input-btn" @click="$refs.salesInput.click()">
            選択...
          </button>
        </div>
      </div>

      <div class="file-input-group">
        <label>会員データ (CSV)</label>
        <div class="file-input-wrapper">
          <div :class="['file-input-display', { 'has-file': files.accounts }]">
            {{ files.accounts ? files.accounts.name : 'ファイルが選択されていません' }}
          </div>
          <input
            type="file"
            accept=".csv"
            @change="e => selectFile('accounts', e)"
            ref="accountsInput"
            style="display: none"
          >
          <button class="file-input-btn" @click="$refs.accountsInput.click()">
            選択...
          </button>
        </div>
      </div>

      <div class="file-input-group">
        <label>担当者マスタ (XLSX)</label>
        <div class="file-input-wrapper">
          <div :class="['file-input-display', { 'has-file': files.master }]">
            {{ files.master ? files.master.name : 'ファイルが選択されていません' }}
          </div>
          <input
            type="file"
            accept=".xlsx,.xls"
            @change="e => selectFile('master', e)"
            ref="masterInput"
            style="display: none"
          >
          <button class="file-input-btn" @click="$refs.masterInput.click()">
            選択...
          </button>
        </div>
      </div>
    </div>

    <!-- Step 2: 対象期間 -->
    <div v-if="currentStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">2</span>
        対象期間を選択
      </h2>

      <div class="select-group">
        <div class="select-item">
          <label>年度</label>
          <select v-model="options.fiscalYear">
            <option v-for="year in fiscalYears" :key="year" :value="year">
              {{ year }}年度
            </option>
          </select>
        </div>
        <div class="select-item">
          <label>月</label>
          <select v-model="options.month">
            <option v-for="month in 12" :key="month" :value="month">
              {{ month }}月
            </option>
          </select>
        </div>
      </div>
    </div>

    <!-- 実行ボタン -->
    <div v-if="currentStep === 'upload'">
      <button
        class="btn-primary"
        @click="startAggregation"
        :disabled="!canStart"
      >
        🚀 集計を実行
      </button>
    </div>

    <!-- 月次集計モーダル -->
    <div v-if="monthlyModalVisible" class="modal-overlay" @click.self="closeMonthlyModalIfComplete">
      <div class="modal-container">
        <!-- 処理中 -->
        <div v-if="monthlyModalStep === 'processing'" class="modal-content">
          <h2 class="modal-title">月次集計中...</h2>
          <div class="modal-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: progress + '%' }"></div>
            </div>
            <div class="progress-text">{{ progress }}%</div>
          </div>
          <div class="modal-logs">
            <div
              v-for="(log, index) in logs"
              :key="index"
              :class="['modal-log-item', log.status]"
            >
              <span class="icon">{{ getLogIcon(log.status) }}</span>
              <span>{{ log.message }}</span>
            </div>
          </div>
        </div>
        <!-- 完了 -->
        <div v-if="monthlyModalStep === 'complete'" class="modal-content">
          <div class="modal-complete-icon">✅</div>
          <h2 class="modal-title">月次集計完了！</h2>
          <div class="modal-result">
            <div class="modal-result-item">
              <span class="label">総売上</span>
              <span class="value highlight">{{ formatCurrency(result.total_sales) }}</span>
            </div>
            <div class="modal-result-item">
              <span class="label">├ 直取引</span>
              <span class="value">{{ formatCurrency(result.direct_sales) }}</span>
            </div>
            <div class="modal-result-item">
              <span class="label">└ 写真館・学校</span>
              <span class="value">{{ formatCurrency(result.studio_sales) }}</span>
            </div>
            <div class="modal-result-item">
              <span class="label">実施学校数</span>
              <span class="value">{{ result.school_count }}校</span>
            </div>
            <div class="modal-result-item">
              <span class="label">売上/学校</span>
              <span class="value">{{ formatCurrency(result.sales_per_school) }}</span>
            </div>
          </div>
          <div class="modal-actions">
            <button class="btn-modal-close" @click="closeMonthlyModal">
              閉じる
            </button>
          </div>
        </div>
        <!-- エラー -->
        <div v-if="monthlyModalStep === 'error'" class="modal-content">
          <div class="modal-error-icon">❌</div>
          <h2 class="modal-title">エラーが発生しました</h2>
          <p class="modal-error-message">{{ monthlyModalError }}</p>
          <button class="btn-modal-close" @click="closeMonthlyModal">
            閉じる
          </button>
        </div>
      </div>
    </div>

    <!-- マスタ不一致エラーモーダル -->
    <div v-if="masterMismatchError" class="modal-overlay" @click.self="closeMasterMismatchError">
      <div class="modal-container modal-warning">
        <div class="modal-content">
          <div class="modal-warning-icon">⚠️</div>
          <h2 class="modal-title">担当者マスタに未登録の学校があります</h2>
          <p class="modal-description">
            以下の学校が担当者マスタ（XLSX）に登録されていません。<br>
            マスタを更新してから、再度集計を実行してください。
          </p>
          <div class="modal-school-list">
            <div
              v-for="school in masterMismatchError.schools"
              :key="school"
              class="modal-school-item"
            >
              {{ school }}
            </div>
          </div>
          <button class="btn-modal-close" @click="closeMasterMismatchError">
            ファイル選択に戻る
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MonthlyAggregation',
  data() {
    const currentDate = new Date()
    const currentMonth = currentDate.getMonth() + 1
    const currentYear = currentMonth >= 4
      ? currentDate.getFullYear()
      : currentDate.getFullYear() - 1

    return {
      // === 月次集計用 ===
      currentStep: 'upload', // upload, processing, result
      files: {
        sales: null,
        accounts: null,
        master: null
      },
      options: {
        fiscalYear: currentYear,
        month: currentMonth,
        exportExcel: true,
        saveToDb: true,
        publishDashboard: false
      },
      progress: 0,
      logs: [],
      result: null,
      sessionId: null,
      error: null,
      masterMismatchError: null,

      // === 月次集計モーダル用 ===
      monthlyModalVisible: false,
      monthlyModalStep: 'processing', // processing, complete, error
      monthlyModalError: '',
    }
  },
  computed: {
    fiscalYears() {
      const currentYear = new Date().getFullYear()
      return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i)
    },
    canStart() {
      return this.files.sales && this.files.accounts && this.files.master
    },
  },
  methods: {
    selectFile(type, event) {
      const file = event.target.files[0]
      if (file) {
        this.files[type] = file
        this.error = null
      }
    },

    async startAggregation() {
      this.error = null
      this.progress = 0
      this.logs = []

      // モーダルを表示
      this.monthlyModalVisible = true
      this.monthlyModalStep = 'processing'
      this.monthlyModalError = ''

      try {
        // Step 1: ファイルアップロード
        this.addLog('ファイルをアップロード中...', 'processing')
        await this.uploadFiles()
        this.updateLog(0, 'ファイルアップロード完了', 'success')
        this.progress = 20

        // Step 2: 集計実行
        this.addLog('売上データを読み込み中...', 'processing')
        this.progress = 30

        this.addLog('全体売上を集計中...', 'pending')
        this.addLog('事業所別集計中...', 'pending')
        this.addLog('担当者別集計中...', 'pending')
        this.addLog('イベント別集計中...', 'pending')
        this.addLog('会員率計算中...', 'pending')
        this.addLog('Excel出力中...', 'pending')

        const result = await this.runAggregation()

        // ログ更新
        for (let i = 1; i <= 7; i++) {
          this.updateLog(i, this.logs[i].message.replace('中...', '完了'), 'success')
        }
        this.progress = 90

        // Step 3: DB保存（オプション）
        if (this.options.saveToDb) {
          this.addLog('データベースに保存中...', 'processing')
          await this.saveToDatabase()
          this.updateLog(this.logs.length - 1, 'データベース保存完了', 'success')
        }

        // Step 4: ダッシュボード公開（オプション）
        if (this.options.publishDashboard) {
          this.addLog('ダッシュボードを公開中...', 'processing')
          await this.publishDashboard()
          this.updateLog(this.logs.length - 1, 'ダッシュボード公開完了', 'success')
        }

        this.progress = 100
        this.result = result.summary
        this.monthlyModalStep = 'complete'

      } catch (err) {
        // マスタ不一致エラーの場合は専用画面を表示
        if (err.message === 'MASTER_MISMATCH') {
          this.monthlyModalVisible = false
          return
        }
        this.monthlyModalStep = 'error'
        this.monthlyModalError = err.message || '処理中にエラーが発生しました'
      }
    },

    async uploadFiles() {
      const formData = new FormData()
      formData.append('sales_file', this.files.sales)
      formData.append('accounts_file', this.files.accounts)
      formData.append('master_file', this.files.master)

      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      this.sessionId = data.session_id
    },

    async runAggregation() {
      const response = await fetch('/api/aggregate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.sessionId,
          fiscal_year: this.options.fiscalYear,
          month: this.options.month
        })
      })

      const data = await response.json()
      if (data.status !== 'success') {
        // マスタ不一致エラーの場合は特別処理
        if (data.error_type === 'master_mismatch') {
          this.masterMismatchError = {
            message: data.message,
            schools: data.unmatched_schools
          }
          throw new Error('MASTER_MISMATCH')
        }
        throw new Error(data.message)
      }

      return data
    },

    async saveToDatabase() {
      const response = await fetch('/api/save-db', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: this.sessionId })
      })

      const data = await response.json()
      if (data.status !== 'success') {
        console.warn('DB保存に失敗:', data.message)
      }
    },

    async publishDashboard() {
      const response = await fetch('/api/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      const data = await response.json()
      if (data.status !== 'success') {
        console.warn('公開に失敗:', data.message)
      }
    },

    downloadExcel() {
      window.open(`/api/download/${this.sessionId}`, '_blank')
    },

    addLog(message, status) {
      this.logs.push({ message, status })
    },

    updateLog(index, message, status) {
      if (this.logs[index]) {
        this.logs[index].message = message
        this.logs[index].status = status
      }
    },

    getLogIcon(status) {
      switch (status) {
        case 'success': return '✅'
        case 'processing': return '🔄'
        case 'pending': return '⏳'
        case 'error': return '❌'
        default: return '•'
      }
    },

    formatCurrency(value) {
      if (!value && value !== 0) return '-'
      return '¥' + Math.round(value).toLocaleString()
    },

    resetForm() {
      this.currentStep = 'upload'
      this.files = { sales: null, accounts: null, master: null }
      this.progress = 0
      this.logs = []
      this.result = null
      this.sessionId = null
      this.error = null
      this.masterMismatchError = null
      this.monthlyModalVisible = false
    },

    closeMonthlyModal() {
      this.monthlyModalVisible = false
      if (this.monthlyModalStep === 'complete') {
        this.resetForm()
      }
    },

    closeMonthlyModalIfComplete() {
      if (this.monthlyModalStep === 'complete' || this.monthlyModalStep === 'error') {
        this.closeMonthlyModal()
      }
    },

    closeMasterMismatchError() {
      this.masterMismatchError = null
      this.currentStep = 'upload'
    },
  }
}
</script>

<style scoped>
/* App.vueからコピーしたスタイル。必要に応じて調整 */
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
