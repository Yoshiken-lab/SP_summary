<template>
  <div class="page-container">
    <header class="page-header">
      <h1>実績反映</h1>
      <p>月次集計の結果をデータベースに保存し、ダッシュボードを更新します</p>
    </header>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

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

      <div v-if="publishFiles.length > 0" class="file-list">
        <h3 class="file-list-title">追加済みファイル（{{ publishFiles.length }}件）</h3>
        <div class="file-list-item" v-for="(item, index) in publishFiles" :key="index">
          <span class="file-name">{{ item.file.name }}</span>
          <button class="file-remove-btn" @click="removePublishFile(index)">削除</button>
        </div>
      </div>
    </div>

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

    <div v-if="!publishDuplicateWarning">
      <button
        class="btn-primary"
        @click="startPublish"
        :disabled="publishFiles.length === 0"
      >
        📊 実績を反映（{{ publishFiles.length }}ファイル）
      </button>
    </div>

    <!-- セクション2: 担当者設定 -->
    <div class="card" style="margin-top: 24px;">
      <h2 class="card-title">
        <span class="step">2</span>
        担当者設定
      </h2>

      <div class="settings-tabs">
        <button
          class="settings-tab"
          :class="{ active: settingsTab === 'alias' }"
          @click="settingsTab = 'alias'"
        >
          名前変換
          <span class="tab-badge" v-if="salesmanAliases.length > 0">{{ salesmanAliases.length }}</span>
        </button>
        <button
          class="settings-tab"
          :class="{ active: settingsTab === 'override' }"
          @click="settingsTab = 'override'"
        >
          学校担当者
          <span class="tab-badge" v-if="schoolManagerOverrides.length > 0">{{ schoolManagerOverrides.length }}</span>
        </button>
      </div>

      <div v-show="settingsTab === 'alias'" class="settings-tab-content">
        <p class="section-description">
          同一人物で担当者名が異なる場合（例: 「佐藤」→「佐藤（邦）」）、変換ルールを設定します。
        </p>
        <div class="alias-add-form">
          <div class="alias-input-group">
            <div class="alias-input-item">
              <label>変換元</label>
              <input type="text" v-model="newAliasFrom" placeholder="例: 佐藤" class="alias-input">
            </div>
            <span class="alias-arrow">→</span>
            <div class="alias-input-item">
              <label>変換先</label>
              <input type="text" v-model="newAliasTo" placeholder="例: 佐藤（邦）" class="alias-input">
            </div>
            <button class="btn-add" @click="addSalesmanAlias" :disabled="!newAliasFrom || !newAliasTo || addingAlias">
              {{ addingAlias ? '追加中...' : '追加' }}
            </button>
          </div>
        </div>
        <div v-if="salesmanAliases.length > 0" class="collapsible-section">
          <div class="collapsible-header" @click="aliasListExpanded = !aliasListExpanded">
            <span class="collapsible-icon">{{ aliasListExpanded ? '▼' : '▶' }}</span>
            <span class="collapsible-title">登録済み（{{ salesmanAliases.length }}件）</span>
          </div>
          <div v-show="aliasListExpanded" class="collapsible-content">
            <div class="alias-list-items">
              <div v-for="alias in salesmanAliases" :key="alias.id" class="alias-list-item">
                <span class="alias-from">{{ alias.from_name }}</span>
                <span class="alias-arrow">→</span>
                <span class="alias-to">{{ alias.to_name }}</span>
                <span class="alias-date">{{ formatAliasDate(alias.created_at) }}</span>
                <button class="alias-delete-btn" @click="deleteSalesmanAlias(alias.id)">削除</button>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="alias-empty">
          登録済みの変換ルールはありません
        </div>
      </div>

      <div v-show="settingsTab === 'override'" class="settings-tab-content">
        <p class="section-description">
          特定の学校・期間の担当者を変更します。既存の売上データも自動更新されます。
        </p>
        <div class="override-form">
          <div class="override-form-row">
            <div class="override-input-item">
              <label>学校名</label>
              <input type="text" v-model="overrideSchoolSearch" placeholder="学校名で検索..." class="override-input" @input="searchSchools" @focus="showSchoolDropdown = true">
              <div v-if="showSchoolDropdown && filteredSchools.length > 0" class="school-dropdown">
                <div v-for="school in filteredSchools" :key="school.id" class="school-dropdown-item" @click="selectSchool(school)">
                  {{ school.school_name }}
                  <span class="school-manager-hint" v-if="school.manager">（現担当: {{ school.manager }}）</span>
                </div>
              </div>
            </div>
          </div>
          <div class="override-form-row" v-if="selectedSchool">
            <div class="override-input-item">
              <label>年度</label>
              <select v-model="overrideFiscalYear" class="override-select">
                <option v-for="year in availableFiscalYears" :key="year" :value="year">{{ year }}年度</option>
              </select>
            </div>
            <div class="override-input-item">
              <label>開始月</label>
              <select v-model="overrideStartMonth" class="override-select">
                <option v-for="month in 12" :key="month" :value="month">{{ month }}月</option>
              </select>
            </div>
            <div class="override-input-item">
              <label>終了月</label>
              <select v-model="overrideEndMonth" class="override-select">
                <option :value="null">指定なし（継続中）</option>
                <option v-for="month in 12" :key="month" :value="month">{{ month }}月</option>
              </select>
            </div>
            <div class="override-input-item">
              <label>担当者</label>
              <select v-model="overrideManager" class="override-select">
                <option value="">選択してください</option>
                <option v-for="manager in availableManagers" :key="manager" :value="manager">{{ manager }}</option>
              </select>
            </div>
            <button class="btn-add" @click="addSchoolManagerOverride" :disabled="!canAddOverride || addingOverride">
              {{ addingOverride ? '追加中...' : '追加' }}
            </button>
          </div>
          <div v-if="selectedSchool" class="selected-school-info">
            選択中: {{ selectedSchool.school_name }}
            <button class="btn-clear-school" @click="clearSelectedSchool">×</button>
          </div>
        </div>
        <div v-if="schoolManagerOverrides.length > 0" class="collapsible-section">
          <div class="collapsible-header" @click="overrideListExpanded = !overrideListExpanded">
            <span class="collapsible-icon">{{ overrideListExpanded ? '▼' : '▶' }}</span>
            <span class="collapsible-title">登録済み（{{ schoolManagerOverrides.length }}件）</span>
          </div>
          <div v-show="overrideListExpanded" class="collapsible-content">
            <div class="override-list-items">
              <div v-for="override in schoolManagerOverrides" :key="override.id" class="override-list-item">
                <span class="override-school">{{ override.school_name }}</span>
                <span class="override-period">{{ override.fiscal_year }}年度 {{ override.start_month }}月〜{{ override.end_month ? override.end_month + '月' : '継続中' }}</span>
                <span class="override-original-manager">{{ override.original_manager || '(不明)' }}</span>
                <span class="override-arrow">→</span>
                <span class="override-manager">{{ override.manager }}</span>
                <span class="override-date">{{ formatFullDate(override.created_at) }}</span>
                <button class="override-delete-btn" @click="deleteSchoolManagerOverride(override.id)">削除</button>
              </div>
            </div>
          </div>
        </div>
        <div v-else class="override-empty">
          登録済みの担当者設定はありません
        </div>
      </div>
    </div>

    <!-- セクション3: 社内サーバー公開 -->
    <div class="card" style="margin-top: 24px;">
      <h2 class="card-title">
        <span class="step">3</span>
        社内サーバーに公開
      </h2>
      <div class="dashboard-status">
        <div class="status-item">
          <span class="status-label">最終生成日時</span>
          <span class="status-value">{{ formatDateTime(dashboardStatus.lastGenerated) || '未生成' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">最終公開日時</span>
          <span class="status-value">{{ formatDateTime(dashboardStatus.lastPublished) || '未公開' }}</span>
        </div>
        <div v-if="dashboardStatus.hasUnpublishedChanges" class="status-notice">
          ※未公開の更新があります
        </div>
      </div>
      <div class="action-buttons" style="margin-top: 16px;">
        <button class="btn-secondary" @click="previewDashboard" :disabled="!dashboardStatus.lastGenerated">
          🔍 プレビュー
        </button>
        <button class="btn-primary" @click="publishToInternalServer" :disabled="!dashboardStatus.lastGenerated || publishingToServer">
          {{ publishingToServer ? '公開中...' : '🚀 社内サーバーに公開' }}
        </button>
      </div>
      <div v-if="dashboardStatus.publishUrl" class="publish-url-box">
        <div class="publish-url-label">公開先:</div>
        <div class="publish-url-value">
          <input type="text" :value="dashboardStatus.publishUrl" readonly @click="$event.target.select()" class="publish-url-input">
          <button class="btn-copy" @click="copyPublishUrl">コピー</button>
        </div>
      </div>
    </div>

    <!-- 実績反映モーダル -->
    <div v-if="publishModalVisible" class="modal-overlay" @click.self="closePublishModalIfComplete">
      <div class="modal-container">
        <!-- 処理中 -->
        <div v-if="publishModalStep === 'processing'" class="modal-content">
          <h2 class="modal-title">実績を反映中...</h2>
          <div class="modal-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: publishProgress + '%' }"></div>
            </div>
            <div class="progress-text">{{ publishProgress }}%</div>
          </div>
          <div class="modal-logs">
            <div v-for="(log, index) in publishLogs" :key="index" :class="['modal-log-item', log.status]">
              <span class="log-icon">{{ getLogIcon(log.status) }}</span>
              <span class="log-message">{{ log.message }}</span>
            </div>
          </div>
        </div>
        <!-- 完了 -->
        <div v-if="publishModalStep === 'complete'" class="modal-content">
          <div class="modal-complete-icon">✅</div>
          <h2 class="modal-title">実績反映完了！</h2>
          <div class="modal-result">
            <div class="modal-result-item">
              <span class="result-label">反映ファイル数</span>
              <span class="result-value">{{ publishResult?.fileCount || 0 }}件</span>
            </div>
            <div class="modal-result-item">
              <span class="result-label">ダッシュボード</span>
              <span class="result-value highlight">生成済み</span>
            </div>
          </div>
          <button class="btn-modal-close" @click="closePublishModal">
            閉じる
          </button>
        </div>
        <!-- エラー -->
        <div v-if="publishModalStep === 'error'" class="modal-content">
          <div class="modal-error-icon">❌</div>
          <h2 class="modal-title">エラーが発生しました</h2>
          <p class="modal-error-message">{{ publishModalError }}</p>
          <button class="btn-modal-close" @click="closePublishModal">
            閉じる
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'Publish',
  data() {
    return {
      error: null,
      publishFiles: [],
      publishNewFile: null,
      publishProgress: 0,
      publishLogs: [],
      publishResult: null,
      publishSessionId: null,
      publishDuplicateWarning: null,
      dashboardStatus: {
        lastGenerated: null,
        lastPublished: null,
        hasUnpublishedChanges: false,
        publishUrl: null,
      },
      publishingToServer: false,
      publishModalVisible: false,
      publishModalStep: 'processing',
      publishModalError: '',
      settingsTab: 'alias',
      aliasListExpanded: false,
      overrideListExpanded: false,
      salesmanAliases: [],
      newAliasFrom: '',
      newAliasTo: '',
      addingAlias: false,
      schoolManagerOverrides: [],
      allSchools: [],
      filteredSchools: [],
      selectedSchool: null,
      overrideSchoolSearch: '',
      showSchoolDropdown: false,
      overrideFiscalYear: new Date().getFullYear(),
      overrideStartMonth: 4,
      overrideEndMonth: null,
      overrideManager: '',
      availableManagers: [],
      addingOverride: false,
    };
  },
  computed: {
    availableFiscalYears() {
      const currentYear = new Date().getFullYear();
      return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i);
    },
    canAddOverride() {
      return this.selectedSchool && this.overrideFiscalYear && this.overrideManager;
    },
  },
  methods: {
    getLogIcon(status) {
      switch (status) {
        case 'success': return '✅';
        case 'processing': return '🔄';
        case 'pending': return '⏳';
        case 'error': return '❌';
        default: return '•';
      }
    },
    formatDateTime(isoString) {
      if (!isoString) return null;
      try {
        const date = new Date(isoString);
        return date.toLocaleString('ja-JP');
      } catch {
        return isoString;
      }
    },
    selectPublishFile(event) {
      const file = event.target.files[0];
      if (file) {
        this.publishNewFile = file;
      }
    },
    addPublishFile() {
      if (this.publishNewFile) {
        this.publishFiles.push({ file: this.publishNewFile });
        this.publishNewFile = null;
        if (this.$refs.publishFileInput) {
          this.$refs.publishFileInput.value = '';
        }
      }
    },
    removePublishFile(index) {
      this.publishFiles.splice(index, 1);
    },
    async startPublish() {
      this.error = null;
      this.publishDuplicateWarning = null;
      try {
        const checkResponse = await fetch('/api/publish/check-duplicates', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            filenames: this.publishFiles.map(f => f.file.name),
          }),
        });
        const checkData = await checkResponse.json();
        if (checkData.status !== 'success') {
          throw new Error(checkData.message);
        }
        if (checkData.duplicates && checkData.duplicates.length > 0) {
          this.publishDuplicateWarning = { months: checkData.duplicates };
        } else {
          await this.executePublish();
        }
      } catch (err) {
        this.error = err.message || '処理中にエラーが発生しました';
      }
    },
    cancelPublish() {
      this.publishDuplicateWarning = null;
    },
    async confirmPublish() {
      this.publishDuplicateWarning = null;
      await this.executePublish();
    },
    async executePublish() {
      this.publishModalVisible = true;
      this.publishModalStep = 'processing';
      this.publishModalError = '';
      this.publishProgress = 0;
      this.publishLogs = [];
      try {
        this.addPublishLog('ファイルをアップロード中...', 'processing');
        await this.uploadPublishFiles();
        this.updatePublishLog(0, 'ファイルアップロード完了', 'success');
        this.publishProgress = 30;

        this.addPublishLog('データベースに反映中...', 'processing');
        const result = await this.runPublishImport();
        this.updatePublishLog(1, 'データベース反映完了', 'success');
        this.publishProgress = 70;

        this.addPublishLog('ダッシュボードを生成中...', 'processing');
        await this.generateDashboard();
        this.updatePublishLog(2, 'ダッシュボード生成完了', 'success');
        this.publishProgress = 100;

        this.publishResult = result;
        this.publishModalStep = 'complete';
        await this.fetchDashboardStatus();
        await this.fetchAvailableManagers();
      } catch (err) {
        this.publishModalStep = 'error';
        this.publishModalError = err.message || '処理中にエラーが発生しました';
      }
    },
    async uploadPublishFiles() {
      const formData = new FormData();
      this.publishFiles.forEach((item, index) => {
        formData.append(`file_${index}`, item.file);
      });
      formData.append('file_count', this.publishFiles.length);
      const response = await fetch('/api/publish/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message);
      }
      this.publishSessionId = data.session_id;
    },
    async runPublishImport() {
      const response = await fetch('/api/publish/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.publishSessionId,
        }),
      });
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message);
      }
      return data;
    },
    async generateDashboard() {
      const response = await fetch('/api/publish/generate-dashboard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message);
      }
      return data;
    },
    async fetchDashboardStatus() {
      try {
        const response = await fetch('/api/publish/dashboard-status');
        const data = await response.json();
        if (data.status === 'success') {
          this.dashboardStatus = data.dashboard;
        }
      } catch (err) {
        console.error('ダッシュボード状態取得エラー:', err);
      }
    },
    previewDashboard() {
      window.open('/api/publish/preview', '_blank');
    },
    async publishToInternalServer() {
      this.publishingToServer = true;
      this.error = null;
      try {
        const response = await fetch('/api/publish/publish-dashboard', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        const data = await response.json();
        if (data.status !== 'success') {
          throw new Error(data.message);
        }
        this.dashboardStatus.lastPublished = new Date().toISOString();
        this.dashboardStatus.publishUrl = data.publishUrl;
        this.dashboardStatus.hasUnpublishedChanges = false;
        alert('社内サーバーへの公開が完了しました！\n\n公開先: ' + data.publishUrl);
      } catch (err) {
        this.error = err.message || '社内サーバー公開中にエラーが発生しました';
        alert('エラー: ' + this.error);
      } finally {
        this.publishingToServer = false;
      }
    },
    copyPublishUrl() {
      if (this.dashboardStatus.publishUrl) {
        navigator.clipboard.writeText(this.dashboardStatus.publishUrl)
          .then(() => alert('URLをコピーしました'))
          .catch(() => alert('コピーに失敗しました'));
      }
    },
    addPublishLog(message, status) {
      this.publishLogs.push({ message, status });
    },
    updatePublishLog(index, message, status) {
      if (this.publishLogs[index]) {
        this.publishLogs[index].message = message;
        this.publishLogs[index].status = status;
      }
    },
    resetPublishForm() {
      this.publishFiles = [];
      this.publishNewFile = null;
      this.publishProgress = 0;
      this.publishLogs = [];
      this.publishResult = null;
      this.publishSessionId = null;
      this.publishDuplicateWarning = null;
      this.error = null;
    },
    closePublishModal() {
      this.publishModalVisible = false;
      if (this.publishModalStep === 'complete') {
        this.resetPublishForm();
      }
    },
    closePublishModalIfComplete() {
      if (this.publishModalStep === 'complete' || this.publishModalStep === 'error') {
        this.closePublishModal();
      }
    },
    async fetchSalesmanAliases() {
      try {
        const response = await fetch('/api/salesman-aliases');
        const data = await response.json();
        if (data.status === 'success') {
          this.salesmanAliases = data.aliases;
        }
      } catch (err) {
        console.error('担当者名変換マッピング取得エラー:', err);
      }
    },
    async addSalesmanAlias() {
      if (!this.newAliasFrom || !this.newAliasTo) return;
      this.addingAlias = true;
      try {
        const response = await fetch('/api/salesman-aliases', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ from_name: this.newAliasFrom, to_name: this.newAliasTo }),
        });
        const data = await response.json();
        if (data.status === 'success') {
          alert(data.message);
          this.newAliasFrom = '';
          this.newAliasTo = '';
          await this.fetchSalesmanAliases();
        } else {
          alert('エラー: ' + data.message);
        }
      } catch (err) {
        alert('追加中にエラーが発生しました: ' + err.message);
      } finally {
        this.addingAlias = false;
      }
    },
    async deleteSalesmanAlias(aliasId) {
      if (!confirm('この変換ルールを削除しますか？')) return;
      try {
        const response = await fetch(`/api/salesman-aliases/${aliasId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.status === 'success') {
          await this.fetchSalesmanAliases();
        } else {
          alert('エラー: ' + data.message);
        }
      } catch (err) {
        alert('削除中にエラーが発生しました: ' + err.message);
      }
    },
    formatAliasDate(dateStr) {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      return `${date.getMonth() + 1}/${date.getDate()}登録`;
    },
    formatFullDate(dateStr) {
      if (!dateStr) return '';
      const date = new Date(dateStr);
      return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()}登録`;
    },
    async fetchSchoolManagerOverrides() {
      try {
        const response = await fetch('/api/school-manager-overrides');
        const data = await response.json();
        if (data.status === 'success') {
          this.schoolManagerOverrides = data.overrides;
        }
      } catch (err) {
        console.error('学校担当者オーバーライド取得エラー:', err);
      }
    },
    async fetchAllSchools() {
      try {
        const response = await fetch('/api/schools/list');
        const data = await response.json();
        if (data.status === 'success') {
          this.allSchools = data.schools;
        }
      } catch (err) {
        console.error('学校一覧取得エラー:', err);
      }
    },
     async fetchAvailableManagers() {
      try {
        const response = await fetch('/api/managers/list');
        const data = await response.json();
        if (data.status === 'success') {
          this.availableManagers = data.managers;
        }
      } catch (err) {
        console.error('担当者一覧取得エラー:', err);
      }
    },
    searchSchools() {
      if (this.overrideSchoolSearch.length < 1) {
        this.filteredSchools = [];
        return;
      }
      this.filteredSchools = this.allSchools.filter(s =>
        s.school_name.includes(this.overrideSchoolSearch)
      ).slice(0, 10);
    },
    selectSchool(school) {
      this.selectedSchool = school;
      this.overrideSchoolSearch = school.school_name;
      this.showSchoolDropdown = false;
    },
    clearSelectedSchool() {
      this.selectedSchool = null;
      this.overrideSchoolSearch = '';
    },
    async addSchoolManagerOverride() {
      if (!this.canAddOverride) return;
      this.addingOverride = true;
      try {
        const response = await fetch('/api/school-manager-overrides', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            school_id: this.selectedSchool.id,
            fiscal_year: this.overrideFiscalYear,
            start_month: this.overrideStartMonth,
            end_month: this.overrideEndMonth,
            manager: this.overrideManager,
          }),
        });
        const data = await response.json();
        if (data.status === 'success') {
          alert(data.message);
          this.clearSelectedSchool();
          this.overrideManager = '';
          await this.fetchSchoolManagerOverrides();
          await this.fetchDashboardStatus();
        } else {
          alert('エラー: ' + data.message);
        }
      } catch (err) {
        alert('追加中にエラーが発生しました: ' + err.message);
      } finally {
        this.addingOverride = false;
      }
    },
    async deleteSchoolManagerOverride(overrideId) {
      if (!confirm('この担当者設定を削除しますか？')) return;
      try {
        const response = await fetch(`/api/school-manager-overrides/${overrideId}`, { method: 'DELETE' });
        const data = await response.json();
        if (data.status === 'success') {
          alert(data.message);
          await this.fetchSchoolManagerOverrides();
          await this.fetchDashboardStatus();
        } else {
          alert('エラー: ' + data.message);
        }
      } catch (err) {
        alert('削除中にエラーが発生しました: ' + err.message);
      }
    },
  },
  async mounted() {
    await this.fetchDashboardStatus();
    await this.fetchSalesmanAliases();
    await this.fetchSchoolManagerOverrides();
    await this.fetchAllSchools();
    await this.fetchAvailableManagers();
  },
};
</script>

<style scoped>
/* Common styles can be used, plus specific styles for this component */
.page-container {
  padding: 2rem;
}
.page-header {
  margin-bottom: 1.5rem;
}
.page-header h1 {
  margin-bottom: 0.5rem;
}
.page-header p {
  font-size: 0.9rem;
  color: #555;
}
.card {
  background-color: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 1.5rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}
.card-title {
  display: flex;
  align-items: center;
  font-size: 1.25rem;
  margin-bottom: 1rem;
  color: #333;
}
.card-title .step {
  background-color: #1abc9c;
  color: white;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 0.8rem;
  margin-right: 0.75rem;
  font-weight: bold;
}
.file-add-section, .settings-tabs, .dashboard-status {
  background-color: #fdfdfd;
  border: 1px solid #eee;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
}
.file-add-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.file-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.file-input-display {
  flex-grow: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #f9f9f9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 150px; /* Ensure it has some width */
}
.file-input-display.has-file {
  border-color: #1abc9c;
}
.file-input-btn {
  padding: 0.5rem 1rem;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.file-input-btn:hover {
  background-color: #2980b9;
}
.file-hint {
  font-size: 0.85rem;
  color: #777;
  margin: 0.75rem 0 0 0;
}
.file-list-title {
  font-size: 1rem;
  margin-bottom: 0.75rem;
  color: #444;
}
.file-list-item, .alias-list-item, .override-list-item {
  display: flex;
  align-items: center;
  padding: 0.5rem;
  background-color: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  font-size: 0.95rem;
}
.file-name, .alias-from, .alias-to, .override-school, .override-period, .override-manager, .override-original-manager {
  flex-grow: 1;
}
.file-remove-btn, .alias-delete-btn, .override-delete-btn {
  background: none;
  border: none;
  color: #e74c3c;
  cursor: pointer;
  font-size: 0.9rem;
  margin-left: 0.5rem;
}
.warning-card {
  border-color: #f39c12;
  background-color: #fef9e7;
  display: flex;
  align-items: center;
  gap: 1rem;
}
.warning-icon {
  font-size: 1.5rem;
  color: #f39c12;
}
.warning-title {
  font-size: 1.1rem;
  color: #d35400;
  margin-bottom: 0.25rem;
}
.warning-message {
  font-size: 0.9rem;
  color: #c0392b;
  margin-bottom: 0.75rem;
}
.duplicate-list {
  margin: 0.5rem 0;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.duplicate-item {
  display: inline-block;
  background-color: #f39c12;
  color: white;
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: bold;
}
.action-buttons {
  display: flex;
  gap: 0.75rem;
  margin-top: 1rem;
}
.btn-primary {
  background-color: #1abc9c;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}
.btn-primary:hover {
  background-color: #16a085;
}
.btn-secondary {
  background-color: #bdc3c7;
  color: #333;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
}
.btn-secondary:hover {
  background-color: #95a5a6;
}
.btn-warning {
  background-color: #e74c3c;
  color: white;
  border: none;
  padding: 0.75rem 1.5rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: bold;
}
.btn-warning:hover {
  background-color: #c0392b;
}
.settings-tabs {
  display: flex;
  border-bottom: 1px solid #ddd;
  margin-bottom: 1rem;
}
.settings-tab {
  padding: 0.75rem 1.25rem;
  cursor: pointer;
  border: none;
  background: none;
  font-size: 1rem;
  color: #555;
  border-bottom: 3px solid transparent;
  transition: color 0.2s, border-bottom-color 0.2s;
}
.settings-tab.active {
  color: #1abc9c;
  border-bottom-color: #1abc9c;
}
.tab-badge {
  background-color: #bdc3c7;
  color: white;
  border-radius: 10px;
  padding: 1px 6px;
  font-size: 0.75rem;
  margin-left: 0.5rem;
}
.settings-tab.active .tab-badge {
  background-color: #1abc9c;
}
.settings-tab-content {
  padding-top: 1rem;
}
.section-description {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 1rem;
}
.alias-input-group {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}
.alias-input-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.alias-input {
  padding: 0.5rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.alias-arrow {
  font-weight: bold;
  color: #777;
}
.alias-empty, .override-empty {
  color: #888;
  font-style: italic;
  padding: 1rem 0;
}
.collapsible-section {
  margin-top: 1rem;
  border: 1px solid #eee;
  border-radius: 4px;
}
.collapsible-header {
  cursor: pointer;
  padding: 0.75rem;
  background-color: #f9f9f9;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.collapsible-icon {
  display: inline-block;
  transition: transform 0.2s;
}
.collapsible-header:hover {
  background-color: #f0f0f0;
}
.collapsible-content {
  padding: 1rem;
}
.alias-list-items, .override-list-items {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.alias-date, .override-date {
  font-size: 0.8rem;
  color: #999;
  margin-left: 0.5rem;
}
.override-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.override-form-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}
.override-input-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}
.override-input, .override-select {
  padding: 0.5rem 0.75rem;
  border: 1px solid #ccc;
  border-radius: 4px;
}
.override-select {
  min-width: 120px;
}
.school-dropdown {
  position: absolute;
  background-color: white;
  border: 1px solid #ccc;
  border-radius: 4px;
  max-height: 150px;
  overflow-y: auto;
  z-index: 10;
  width: calc(100% - 2px); /* Adjust for border */
  margin-top: 2px;
}
.school-dropdown-item {
  padding: 0.5rem 0.75rem;
  cursor: pointer;
}
.school-dropdown-item:hover {
  background-color: #eaf2f8;
}
.school-manager-hint {
  font-size: 0.8rem;
  color: #777;
  margin-left: 0.5rem;
}
.selected-school-info {
  margin-top: 0.5rem;
  font-size: 0.95rem;
  color: #333;
  background-color: #eaf2f8;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.btn-clear-school {
  background: none;
  border: none;
  color: #e74c3c;
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0 0.3rem;
}
.override-period {
  font-size: 0.9rem;
  color: #555;
  margin: 0 0.5rem;
}
.override-original-manager {
  font-size: 0.85rem;
  color: #999;
  margin: 0 0.5rem;
}
.override-arrow {
  font-weight: bold;
  color: #777;
}
.dashboard-status {
  background-color: #fdfdfd;
  border: 1px solid #eee;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1rem;
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  align-items: center;
}
.status-item {
  display: flex;
  flex-direction: column;
}
.status-label {
  font-size: 0.85rem;
  color: #777;
  margin-bottom: 0.25rem;
}
.status-value {
  font-size: 1rem;
  color: #333;
  font-weight: bold;
}
.status-notice {
  background-color: #f39c12;
  color: white;
  padding: 0.3rem 0.7rem;
  border-radius: 4px;
  font-size: 0.8rem;
  font-weight: bold;
}
.publish-url-box {
  margin-top: 1rem;
  background-color: #eaf2f8;
  padding: 0.75rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.publish-url-label {
  font-size: 0.9rem;
  color: #333;
}
.publish-url-value {
  flex-grow: 1;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.publish-url-input {
  flex-grow: 1;
  padding: 0.5rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  background-color: #fff;
}
.btn-copy {
  padding: 0.5rem 1rem;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}
.btn-copy:hover {
  background-color: #2980b9;
}

/* Modal styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.6);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}
.modal-container {
  background-color: white;
  border-radius: 8px;
  padding: 2rem;
  width: 90%;
  max-width: 600px;
  box-shadow: 0 5px 15px rgba(0,0,0,0.3);
  text-align: center;
}
.modal-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.modal-title {
  font-size: 1.5rem;
  margin-bottom: 1rem;
  color: #333;
}
.modal-progress {
  width: 100%;
  margin-bottom: 1rem;
}
.progress-bar {
  background-color: #eee;
  border-radius: 4px;
  height: 10px;
  overflow: hidden;
}
.progress-fill {
  background-color: #1abc9c;
  height: 100%;
  transition: width 0.3s ease-out;
}
.progress-text {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #555;
}
.modal-logs {
  width: 100%;
  max-height: 200px;
  overflow-y: auto;
  text-align: left;
  margin-top: 1rem;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 0.75rem;
  background-color: #f9f9f9;
}
.modal-log-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  margin-bottom: 0.3rem;
}
.modal-log-item .log-icon {
  font-size: 1.1rem;
}
.modal-log-item.success .log-icon { color: #2ecc71; }
.modal-log-item.processing .log-icon { color: #3498db; animation: spin 1s linear infinite; }
.modal-log-item.pending .log-icon { color: #95a5a6; }
.modal-log-item.error .log-icon { color: #e74c3c; }
.modal-log-item.success .log-message { color: #27ae60; }
.modal-log-item.error .log-message { color: #c0392b; }

.modal-complete-icon, .modal-error-icon {
  font-size: 3rem;
  margin-bottom: 1rem;
}
.modal-complete-icon { color: #2ecc71; }
.modal-error-icon { color: #e74c3c; }
.modal-error-message {
  color: #c0392b;
  margin-bottom: 1.5rem;
}
.modal-result {
  margin: 1.5rem 0;
  background-color: #eaf2f8;
  padding: 1rem;
  border-radius: 4px;
  width: 100%;
}
.modal-result-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
  font-size: 1rem;
}
.result-label { color: #555; }
.result-value.highlight { font-weight: bold; color: #1abc9c; }

.btn-modal-close {
  padding: 0.75rem 1.5rem;
  background-color: #3498db;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  margin-top: 1rem;
}
.btn-modal-close:hover {
  background-color: #2980b9;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>