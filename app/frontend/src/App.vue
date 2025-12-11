<template>
  <div class="container">
    <!-- ヘッダー -->
    <header class="header">
      <h1>スクールフォト 売上集計システム</h1>
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

    <!-- Step 3: 出力オプション -->
    <div v-if="currentStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">3</span>
        出力オプション
      </h2>

      <div class="checkbox-group">
        <label class="checkbox-item">
          <input type="checkbox" v-model="options.exportExcel" disabled checked>
          <span>Excel報告書を出力</span>
        </label>
        <label class="checkbox-item">
          <input type="checkbox" v-model="options.saveToDb">
          <span>データベースに保存（ダッシュボード用）</span>
        </label>
        <label class="checkbox-item">
          <input type="checkbox" v-model="options.publishDashboard">
          <span>ダッシュボードを自動更新・公開</span>
        </label>
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

    <!-- 処理中画面 -->
    <div v-if="currentStep === 'processing'" class="card">
      <h2 class="card-title">処理状況</h2>

      <div class="progress-container">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="progress-text">{{ progress }}%</div>
      </div>

      <div class="log-container">
        <div
          v-for="(log, index) in logs"
          :key="index"
          :class="['log-item', log.status]"
        >
          <span class="icon">{{ getLogIcon(log.status) }}</span>
          <span>{{ log.message }}</span>
        </div>
      </div>
    </div>

    <!-- 完了画面 -->
    <div v-if="currentStep === 'result'" class="card result-card">
      <div class="result-icon">✅</div>
      <h2 class="result-title">集計完了</h2>

      <div class="result-summary">
        <div class="summary-item">
          <span class="summary-label">総売上</span>
          <span class="summary-value highlight">{{ formatCurrency(result.total_sales) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">├ 直取引</span>
          <span class="summary-value">{{ formatCurrency(result.direct_sales) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">└ 写真館・学校</span>
          <span class="summary-value">{{ formatCurrency(result.studio_sales) }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">実施学校数</span>
          <span class="summary-value">{{ result.school_count }}校</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">売上/学校</span>
          <span class="summary-value">{{ formatCurrency(result.sales_per_school) }}</span>
        </div>
      </div>

      <div class="action-buttons">
        <button class="btn-success" @click="downloadExcel">
          📥 Excelダウンロード
        </button>
        <button class="btn-secondary" @click="resetForm">
          新規集計を開始
        </button>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'App',
  data() {
    const currentDate = new Date()
    const currentMonth = currentDate.getMonth() + 1
    const currentYear = currentMonth >= 4
      ? currentDate.getFullYear()
      : currentDate.getFullYear() - 1

    return {
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
      error: null
    }
  },
  computed: {
    fiscalYears() {
      const currentYear = new Date().getFullYear()
      return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i)
    },
    canStart() {
      return this.files.sales && this.files.accounts && this.files.master
    }
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
      this.currentStep = 'processing'
      this.progress = 0
      this.logs = []

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
        this.currentStep = 'result'

      } catch (err) {
        this.error = err.message || '処理中にエラーが発生しました'
        this.currentStep = 'upload'
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
    }
  }
}
</script>
