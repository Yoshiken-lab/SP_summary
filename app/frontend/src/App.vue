<template>
  <div class="container">
    <!-- ヘッダー -->
    <header class="header">
      <h1>スクールフォト 売上集計システム</h1>
      <p>CSVデータから売上を集計し、Excel報告書を作成します</p>
    </header>

    <!-- タブ切り替え -->
    <div class="tab-container">
      <button
        :class="['tab-btn', { active: activeTab === 'monthly' }]"
        @click="switchTab('monthly')"
      >
        月次集計
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'cumulative' }]"
        @click="switchTab('cumulative')"
      >
        累積集計
      </button>
      <button
        :class="['tab-btn', { active: activeTab === 'publish' }]"
        @click="switchTab('publish')"
      >
        実績反映
      </button>
    </div>

    <!-- エラー表示 -->
    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- マスタ不一致エラー表示 -->
    <div v-if="masterMismatchError" class="card error-card">
      <div class="error-icon">⚠️</div>
      <h2 class="error-title">担当者マスタに未登録の学校があります</h2>
      <p class="error-description">
        以下の学校が担当者マスタ（XLSX）に登録されていません。<br>
        マスタを更新してから、再度集計を実行してください。
      </p>
      <div class="unmatched-schools">
        <div class="unmatched-school-item" v-for="school in masterMismatchError.schools" :key="school">
          {{ school }}
        </div>
      </div>
      <button class="btn-secondary" @click="closeMasterMismatchError">
        ファイル選択に戻る
      </button>
    </div>

    <!-- ========== 月次集計タブ ========== -->
    <div v-if="activeTab === 'monthly'">

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

    </div><!-- 月次集計タブ終了 -->

    <!-- ========== 累積集計タブ ========== -->
    <div v-if="activeTab === 'cumulative'">

    <!-- Step 1: 月次集計ファイルを追加 -->
    <div v-if="cumulativeStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">1</span>
        月次集計ファイルを追加
      </h2>

      <!-- ファイル追加UI -->
      <div class="file-add-section">
        <div class="file-add-row">
          <div class="file-input-wrapper" style="flex: 2;">
            <div :class="['file-input-display', { 'has-file': newFileToAdd }]">
              {{ newFileToAdd ? newFileToAdd.name : 'ファイルが選択されていません' }}
            </div>
            <input
              type="file"
              accept=".xlsx,.xls"
              @change="onNewFileSelect"
              ref="newFileInput"
              style="display: none"
            >
            <button class="file-input-btn" @click="$refs.newFileInput.click()">
              選択...
            </button>
          </div>
          <div class="select-item" style="min-width: 100px;">
            <select v-model="newFileYear">
              <option v-for="year in availableYears" :key="year" :value="year">
                {{ year }}年
              </option>
            </select>
          </div>
          <div class="select-item" style="min-width: 80px;">
            <select v-model="newFileMonth">
              <option v-for="month in 12" :key="month" :value="month">
                {{ month }}月
              </option>
            </select>
          </div>
          <button class="btn-add" @click="addInputFile" :disabled="!newFileToAdd">
            追加
          </button>
        </div>
        <p class="file-hint">※月次集計で出力されたExcelファイルを選択し、対象年月を指定して追加してください</p>
      </div>

      <!-- 追加済みファイル一覧 -->
      <div v-if="cumulativeInputFiles.length > 0" class="file-list">
        <h3 class="file-list-title">追加済みファイル（{{ cumulativeInputFiles.length }}件）</h3>
        <div class="file-list-items">
          <div v-for="(item, index) in cumulativeInputFiles" :key="index" class="file-list-item">
            <span class="file-name">{{ item.file.name }}</span>
            <span class="file-period">{{ item.year }}年{{ item.month }}月分</span>
            <button class="file-remove-btn" @click="removeInputFile(index)">削除</button>
          </div>
        </div>
      </div>

      <div v-if="cumulativeInputFiles.length > 0" class="fiscal-year-info">
        対象年度: <strong>{{ calculatedFiscalYear }}年度</strong>
        （出力ファイル: SP_年度累計_{{ calculatedFiscalYear }}.xlsx）
      </div>
    </div>

    <!-- Step 2: 既存累積ファイル（オプション） -->
    <div v-if="cumulativeStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">2</span>
        既存の累積ファイル（オプション）
      </h2>

      <div class="file-input-group">
        <label>既存の年度累計ファイルのパス</label>
        <div class="file-input-wrapper">
          <input
            type="text"
            v-model="existingFilePath"
            class="path-input"
            placeholder="例: C:\Users\username\Downloads\SP_年度累計_2024.xlsx"
          >
          <button v-if="existingFilePath" class="file-clear-btn" @click="existingFilePath = ''">
            クリア
          </button>
        </div>
        <p class="file-hint">
          ※既存ファイルのパスを入力すると、そのファイルに月別データを追記・上書き保存します<br>
          ※空欄の場合は、ダウンロードフォルダに新規ファイルを作成します
        </p>
      </div>
    </div>

    <!-- 実行ボタン -->
    <div v-if="cumulativeStep === 'upload'">
      <button
        class="btn-primary"
        @click="startCumulativeAggregation"
        :disabled="!canStartCumulative"
      >
        📊 累積集計を実行（{{ cumulativeInputFiles.length }}ファイル）
      </button>
    </div>

    <!-- 処理中画面 -->
    <div v-if="cumulativeStep === 'processing'" class="card">
      <h2 class="card-title">処理状況</h2>

      <div class="progress-container">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: cumulativeProgress + '%' }"></div>
        </div>
        <div class="progress-text">{{ cumulativeProgress }}%</div>
      </div>

      <div class="log-container">
        <div
          v-for="(log, index) in cumulativeLogs"
          :key="index"
          :class="['log-item', log.status]"
        >
          <span class="icon">{{ getLogIcon(log.status) }}</span>
          <span>{{ log.message }}</span>
        </div>
      </div>
    </div>

    <!-- 完了画面 -->
    <div v-if="cumulativeStep === 'result'" class="card result-card">
      <div class="result-icon">✅</div>
      <h2 class="result-title">累積集計完了</h2>

      <div class="result-summary">
        <div class="summary-item">
          <span class="summary-label">対象年度</span>
          <span class="summary-value">{{ cumulativeResult.fiscalYear }}年度</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">処理ファイル数</span>
          <span class="summary-value">{{ cumulativeResult.processedCount }}件</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">追記月</span>
          <span class="summary-value">{{ cumulativeResult.processedMonths }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">学校別データ</span>
          <span class="summary-value">{{ cumulativeResult.schoolCount }}件</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">イベント別データ</span>
          <span class="summary-value">{{ cumulativeResult.eventCount }}件</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">保存先</span>
          <span class="summary-value output-path">{{ cumulativeResult.outputPath }}</span>
        </div>
      </div>

      <div class="action-buttons" style="justify-content: center;">
        <button class="btn-secondary" @click="resetCumulativeForm">
          新規累積集計を開始
        </button>
      </div>
    </div>

    </div><!-- 累積集計タブ終了 -->

    <!-- ========== 実績反映タブ ========== -->
    <div v-if="activeTab === 'publish'">

    <!-- セクション1: データ反映 -->
    <div class="card">
      <h2 class="card-title">
        <span class="step">1</span>
        月次集計ファイルを追加
      </h2>

      <div class="file-add-section">
        <div class="file-add-row">
          <div class="file-input-wrapper" style="flex: 1;">
            <div :class="['file-input-display', { 'has-file': publishNewFile }]">
              {{ publishNewFile ? publishNewFile.name : 'ファイルが選択されていません' }}
            </div>
            <input
              type="file"
              accept=".xlsx,.xls"
              @change="selectPublishFile"
              ref="publishFileInput"
              style="display: none"
            >
            <button class="file-input-btn" @click="$refs.publishFileInput.click()">
              選択...
            </button>
          </div>
          <button
            class="btn-add"
            @click="addPublishFile"
            :disabled="!publishNewFile"
          >
            追加
          </button>
        </div>
        <p class="file-hint">※月次集計で出力されたExcelファイル（SP_SalesResult_YYYYMM.xlsx）を選択してください</p>
      </div>

      <!-- 追加済みファイル一覧 -->
      <div v-if="publishFiles.length > 0" class="file-list">
        <h3 class="file-list-title">追加済みファイル（{{ publishFiles.length }}件）</h3>
        <div class="file-list-item" v-for="(item, index) in publishFiles" :key="index">
          <span class="file-name">{{ item.file.name }}</span>
          <button class="file-remove-btn" @click="removePublishFile(index)">削除</button>
        </div>
      </div>
    </div>

    <!-- 重複警告ダイアログ -->
    <div v-if="publishDuplicateWarning" class="card warning-card">
      <div class="warning-icon">⚠️</div>
      <h3 class="warning-title">重複データの警告</h3>
      <p class="warning-message">
        以下の月のデータは既にデータベースに存在します。<br>
        続行すると上書きされます。
      </p>
      <div class="duplicate-list">
        <span v-for="month in publishDuplicateWarning.months" :key="month" class="duplicate-item">
          {{ month }}
        </span>
      </div>
      <div class="action-buttons">
        <button class="btn-secondary" @click="cancelPublish">キャンセル</button>
        <button class="btn-warning" @click="confirmPublish">上書きして続行</button>
      </div>
    </div>

    <!-- 実行ボタン -->
    <div v-if="!publishDuplicateWarning && publishStep === 'upload'">
      <button
        class="btn-primary"
        @click="startPublish"
        :disabled="publishFiles.length === 0"
      >
        📊 実績を反映（{{ publishFiles.length }}ファイル）
      </button>
    </div>

    <!-- 処理中画面 -->
    <div v-if="publishStep === 'processing'" class="card">
      <h2 class="card-title">処理状況</h2>
      <div class="progress-container">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: publishProgress + '%' }"></div>
        </div>
        <div class="progress-text">{{ publishProgress }}%</div>
      </div>
      <div class="log-container">
        <div
          v-for="(log, index) in publishLogs"
          :key="index"
          :class="['log-item', log.status]"
        >
          <span class="icon">{{ getLogIcon(log.status) }}</span>
          <span>{{ log.message }}</span>
        </div>
      </div>
    </div>

    <!-- 反映結果 -->
    <div v-if="publishStep === 'result'" class="card result-card">
      <div class="result-icon">✅</div>
      <h2 class="result-title">実績反映完了</h2>
      <div class="result-summary">
        <div class="summary-item">
          <span class="summary-label">反映ファイル数</span>
          <span class="summary-value">{{ publishResult.fileCount }}件</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">ダッシュボード</span>
          <span class="summary-value highlight">生成済み</span>
        </div>
      </div>
      <button class="btn-secondary" @click="resetPublishForm" style="margin-top: 16px;">
        新規反映を開始
      </button>
    </div>

    <!-- セクション2: ダッシュボード公開 -->
    <div class="card" style="margin-top: 24px;">
      <h2 class="card-title">
        <span class="step">2</span>
        ダッシュボード公開
      </h2>

      <div class="dashboard-status">
        <div class="status-item">
          <span class="status-label">最終生成日時</span>
          <span class="status-value">{{ dashboardStatus.lastGenerated || '未生成' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">最終公開日時</span>
          <span class="status-value">{{ dashboardStatus.lastPublished || '未公開' }}</span>
        </div>
        <div v-if="dashboardStatus.hasUnpublishedChanges" class="status-notice">
          ※未公開の更新があります
        </div>
      </div>

      <div class="action-buttons" style="margin-top: 16px;">
        <button
          class="btn-secondary"
          @click="previewDashboard"
          :disabled="!dashboardStatus.lastGenerated"
        >
          🔍 プレビュー
        </button>
        <button
          class="btn-primary"
          @click="publishDashboard"
          :disabled="!dashboardStatus.lastGenerated"
        >
          🚀 ダッシュボードを公開
        </button>
      </div>
    </div>

    </div><!-- 実績反映タブ終了 -->

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
      // タブ管理
      activeTab: 'monthly', // monthly, cumulative, publish

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

      // === 累積集計用 ===
      cumulativeStep: 'upload', // upload, processing, result
      existingFilePath: '', // 既存ファイルのパス（テキスト入力）
      cumulativeFiles: {
        existing: null
      },
      // 複数ファイル用
      cumulativeInputFiles: [], // [{file: File, year: number, month: number}, ...]
      newFileToAdd: null,
      newFileYear: currentDate.getFullYear(),
      newFileMonth: currentMonth,
      cumulativeProgress: 0,
      cumulativeLogs: [],
      cumulativeResult: null,
      cumulativeSessionId: null,

      // === 実績反映用 ===
      publishStep: 'upload', // upload, processing, result
      publishFiles: [], // [{file: File}, ...]
      publishNewFile: null,
      publishProgress: 0,
      publishLogs: [],
      publishResult: null,
      publishSessionId: null,
      publishDuplicateWarning: null, // {months: ['2025年4月', ...]}
      dashboardStatus: {
        lastGenerated: null,
        lastPublished: null,
        hasUnpublishedChanges: false
      }
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
    // 累積集計用
    availableYears() {
      const currentYear = new Date().getFullYear()
      return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i)
    },
    calculatedFiscalYear() {
      // 追加済みファイルの最初のファイルから年度を計算
      if (this.cumulativeInputFiles.length > 0) {
        const firstFile = this.cumulativeInputFiles[0]
        return firstFile.month >= 4 ? firstFile.year : firstFile.year - 1
      }
      // デフォルト
      const currentDate = new Date()
      const currentMonth = currentDate.getMonth() + 1
      return currentMonth >= 4 ? currentDate.getFullYear() : currentDate.getFullYear() - 1
    },
    canStartCumulative() {
      return this.cumulativeInputFiles.length > 0
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
        // マスタ不一致エラーの場合は専用画面を表示
        if (err.message === 'MASTER_MISMATCH') {
          this.currentStep = 'upload'
          return
        }
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
    },

    closeMasterMismatchError() {
      this.masterMismatchError = null
      this.currentStep = 'upload'
    },

    // === タブ切り替え ===
    switchTab(tab) {
      this.activeTab = tab
      this.error = null
    },

    // === 累積集計用メソッド ===
    selectCumulativeFile(type, event) {
      const file = event.target.files[0]
      if (file) {
        this.cumulativeFiles[type] = file
        this.error = null
      }
    },

    // 新しいファイルを選択
    onNewFileSelect(event) {
      const file = event.target.files[0]
      if (file) {
        this.newFileToAdd = file
        this.error = null
      }
    },

    // ファイルをリストに追加
    addInputFile() {
      if (!this.newFileToAdd) return

      this.cumulativeInputFiles.push({
        file: this.newFileToAdd,
        year: this.newFileYear,
        month: this.newFileMonth
      })

      // リセット
      this.newFileToAdd = null
      if (this.$refs.newFileInput) {
        this.$refs.newFileInput.value = ''
      }
    },

    // ファイルをリストから削除
    removeInputFile(index) {
      this.cumulativeInputFiles.splice(index, 1)
    },

    async startCumulativeAggregation() {
      this.error = null
      this.cumulativeStep = 'processing'
      this.cumulativeProgress = 0
      this.cumulativeLogs = []

      try {
        // Step 1: ファイルアップロード
        this.addCumulativeLog(`${this.cumulativeInputFiles.length}件のファイルをアップロード中...`, 'processing')
        await this.uploadCumulativeFiles()
        this.updateCumulativeLog(0, `${this.cumulativeInputFiles.length}件のファイルアップロード完了`, 'success')
        this.cumulativeProgress = 30

        // Step 2: 累積集計実行
        this.addCumulativeLog('累積集計を実行中...', 'processing')

        const result = await this.runCumulativeAggregation()

        // ログ更新
        this.updateCumulativeLog(1, '累積集計完了', 'success')
        this.cumulativeProgress = 100

        this.cumulativeResult = result
        this.cumulativeStep = 'result'

      } catch (err) {
        this.error = err.message || '処理中にエラーが発生しました'
        this.cumulativeStep = 'upload'
      }
    },

    async uploadCumulativeFiles() {
      const formData = new FormData()

      // 複数の入力ファイルと年月情報を追加
      const filesInfo = []
      this.cumulativeInputFiles.forEach((item, index) => {
        formData.append(`input_file_${index}`, item.file)
        filesInfo.push({
          index: index,
          year: item.year,
          month: item.month
        })
      })
      formData.append('files_info', JSON.stringify(filesInfo))

      // 既存ファイルのパスがあれば追加
      if (this.existingFilePath) {
        formData.append('existing_file_path', this.existingFilePath)
      }

      // 年度情報
      formData.append('fiscal_year', this.calculatedFiscalYear)

      const response = await fetch('/api/cumulative/upload-multiple', {
        method: 'POST',
        body: formData
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      this.cumulativeSessionId = data.session_id
    },

    clearExistingFile() {
      this.cumulativeFiles.existing = null
      if (this.$refs.cumulativeExistingInput) {
        this.$refs.cumulativeExistingInput.value = ''
      }
    },

    async runCumulativeAggregation() {
      const response = await fetch('/api/cumulative/aggregate-multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.cumulativeSessionId
        })
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      return data
    },

    downloadCumulativeExcel() {
      window.open(`/api/cumulative/download/${this.cumulativeSessionId}`, '_blank')
    },

    addCumulativeLog(message, status) {
      this.cumulativeLogs.push({ message, status })
    },

    updateCumulativeLog(index, message, status) {
      if (this.cumulativeLogs[index]) {
        this.cumulativeLogs[index].message = message
        this.cumulativeLogs[index].status = status
      }
    },

    resetCumulativeForm() {
      this.cumulativeStep = 'upload'
      this.cumulativeFiles = { existing: null }
      this.existingFilePath = ''
      this.cumulativeInputFiles = []
      this.newFileToAdd = null
      this.cumulativeProgress = 0
      this.cumulativeLogs = []
      this.cumulativeResult = null
      this.cumulativeSessionId = null
      this.error = null
    },

    // ========== 実績反映用メソッド ==========

    selectPublishFile(event) {
      const file = event.target.files[0]
      if (file) {
        this.publishNewFile = file
      }
    },

    addPublishFile() {
      if (this.publishNewFile) {
        this.publishFiles.push({ file: this.publishNewFile })
        this.publishNewFile = null
        if (this.$refs.publishFileInput) {
          this.$refs.publishFileInput.value = ''
        }
      }
    },

    removePublishFile(index) {
      this.publishFiles.splice(index, 1)
    },

    async startPublish() {
      this.error = null
      this.publishDuplicateWarning = null

      try {
        // 重複チェック
        const checkResponse = await fetch('/api/publish/check-duplicates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filenames: this.publishFiles.map(f => f.file.name)
          })
        })

        const checkData = await checkResponse.json()
        if (checkData.status !== 'success') {
          throw new Error(checkData.message)
        }

        if (checkData.duplicates && checkData.duplicates.length > 0) {
          // 重複あり → 警告表示
          this.publishDuplicateWarning = { months: checkData.duplicates }
        } else {
          // 重複なし → そのまま実行
          await this.executePublish()
        }
      } catch (err) {
        this.error = err.message || '処理中にエラーが発生しました'
      }
    },

    cancelPublish() {
      this.publishDuplicateWarning = null
    },

    async confirmPublish() {
      this.publishDuplicateWarning = null
      await this.executePublish()
    },

    async executePublish() {
      this.publishStep = 'processing'
      this.publishProgress = 0
      this.publishLogs = []

      try {
        // Step 1: ファイルアップロード
        this.addPublishLog('ファイルをアップロード中...', 'processing')
        await this.uploadPublishFiles()
        this.updatePublishLog(0, 'ファイルアップロード完了', 'success')
        this.publishProgress = 30

        // Step 2: DB反映実行
        this.addPublishLog('データベースに反映中...', 'processing')
        const result = await this.runPublishImport()
        this.updatePublishLog(1, 'データベース反映完了', 'success')
        this.publishProgress = 70

        // Step 3: ダッシュボード生成
        this.addPublishLog('ダッシュボードを生成中...', 'processing')
        await this.generateDashboard()
        this.updatePublishLog(2, 'ダッシュボード生成完了', 'success')
        this.publishProgress = 100

        this.publishResult = result
        this.publishStep = 'result'

        // ダッシュボード状態を更新
        await this.fetchDashboardStatus()

      } catch (err) {
        this.error = err.message || '処理中にエラーが発生しました'
        this.publishStep = 'upload'
      }
    },

    async uploadPublishFiles() {
      const formData = new FormData()
      this.publishFiles.forEach((item, index) => {
        formData.append(`file_${index}`, item.file)
      })
      formData.append('file_count', this.publishFiles.length)

      const response = await fetch('/api/publish/upload', {
        method: 'POST',
        body: formData
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      this.publishSessionId = data.session_id
    },

    async runPublishImport() {
      const response = await fetch('/api/publish/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.publishSessionId
        })
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      return data
    },

    async generateDashboard() {
      const response = await fetch('/api/publish/generate-dashboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      })

      const data = await response.json()
      if (data.status !== 'success') {
        throw new Error(data.message)
      }

      return data
    },

    async fetchDashboardStatus() {
      try {
        const response = await fetch('/api/publish/dashboard-status')
        const data = await response.json()
        if (data.status === 'success') {
          this.dashboardStatus = data.dashboard
        }
      } catch (err) {
        console.error('ダッシュボード状態取得エラー:', err)
      }
    },

    previewDashboard() {
      window.open('/api/publish/preview', '_blank')
    },

    async publishDashboard() {
      try {
        const response = await fetch('/api/publish/publish-dashboard', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })

        const data = await response.json()
        if (data.status !== 'success') {
          throw new Error(data.message)
        }

        alert('ダッシュボードを公開しました')
        await this.fetchDashboardStatus()
      } catch (err) {
        this.error = err.message || '公開中にエラーが発生しました'
      }
    },

    addPublishLog(message, status) {
      this.publishLogs.push({ message, status })
    },

    updatePublishLog(index, message, status) {
      if (this.publishLogs[index]) {
        this.publishLogs[index].message = message
        this.publishLogs[index].status = status
      }
    },

    resetPublishForm() {
      this.publishStep = 'upload'
      this.publishFiles = []
      this.publishNewFile = null
      this.publishProgress = 0
      this.publishLogs = []
      this.publishResult = null
      this.publishSessionId = null
      this.publishDuplicateWarning = null
      this.error = null
    }
  },
  mounted() {
    // 実績反映タブ用：ダッシュボード状態を取得
    this.fetchDashboardStatus()
  }
}
</script>
