<template>
  <div class="page-container">
    <header class="page-header">
      <h1>累積集計</h1>
      <p>複数の月次集計ファイルを元に、年度の累積報告書を作成します</p>
    </header>

    <div v-if="error" class="error-message">
      {{ error }}
    </div>

    <!-- Step 1: 月次集計ファイルを追加 -->
    <div v-if="cumulativeStep === 'upload'" class="card">
      <h2 class="card-title">
        <span class="step">1</span>
        月次集計ファイルを追加
      </h2>

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

    <!-- 累積集計モーダル -->
    <div v-if="cumulativeModalVisible" class="modal-overlay" @click.self="closeCumulativeModalIfComplete">
      <div class="modal-container">
        <!-- 処理中 -->
        <div v-if="cumulativeModalStep === 'processing'" class="modal-content">
          <h2 class="modal-title">累積集計中...</h2>
          <div class="modal-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: cumulativeProgress + '%' }"></div>
            </div>
            <div class="progress-text">{{ cumulativeProgress }}%</div>
          </div>
          <div class="modal-logs">
            <div
              v-for="(log, index) in cumulativeLogs"
              :key="index"
              :class="['modal-log-item', log.status]"
            >
              <span class="icon">{{ getLogIcon(log.status) }}</span>
              <span>{{ log.message }}</span>
            </div>
          </div>
        </div>

        <!-- 完了 -->
        <div v-if="cumulativeModalStep === 'complete'" class="modal-content">
          <div class="modal-complete-icon">✅</div>
          <h2 class="modal-title">累積集計完了！</h2>
          <div class="modal-result">
            <div class="modal-result-item">
              <span class="label">対象年度</span>
              <span class="value">{{ cumulativeResult.fiscalYear }}年度</span>
            </div>
            <div class="modal-result-item">
              <span class="label">処理ファイル数</span>
              <span class="value">{{ cumulativeResult.processedCount }}件</span>
            </div>
            <div class="modal-result-item">
              <span class="label">追記月</span>
              <span class="value">{{ cumulativeResult.processedMonths }}</span>
            </div>
            <div class="modal-result-item">
              <span class="label">学校別データ</span>
              <span class="value">{{ cumulativeResult.schoolCount }}件</span>
            </div>
            <div class="modal-result-item">
              <span class="label">イベント別データ</span>
              <span class="value">{{ cumulativeResult.eventCount }}件</span>
            </div>
            <div class="modal-result-item">
              <span class="label">保存先</span>
              <span class="value output-path">{{ cumulativeResult.outputPath }}</span>
            </div>
          </div>
          <button class="btn-modal-close" @click="closeCumulativeModal">
            閉じる
          </button>
        </div>

        <!-- エラー -->
        <div v-if="cumulativeModalStep === 'error'" class="modal-content">
          <div class="modal-error-icon">❌</div>
          <h2 class="modal-title">エラーが発生しました</h2>
          <p class="modal-error-message">{{ cumulativeModalError }}</p>
          <button class="btn-modal-close" @click="closeCumulativeModal">
            閉じる
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CumulativeAggregation',
  data() {
    const currentDate = new Date();
    const currentMonth = currentDate.getMonth() + 1;

    return {
      error: null,
      cumulativeStep: 'upload', // upload, processing, result
      existingFilePath: '', // 既存ファイルのパス（テキスト入力）
      cumulativeInputFiles: [], // [{file: File, year: number, month: number}, ...]
      newFileToAdd: null,
      newFileYear: currentDate.getFullYear(),
      newFileMonth: currentMonth,
      cumulativeProgress: 0,
      cumulativeLogs: [],
      cumulativeResult: null,
      cumulativeSessionId: null,
      cumulativeModalVisible: false,
      cumulativeModalStep: 'processing', // processing, complete, error
      cumulativeModalError: '',
    };
  },
  computed: {
    availableYears() {
      const currentYear = new Date().getFullYear();
      return Array.from({ length: 6 }, (_, i) => currentYear - 4 + i);
    },
    calculatedFiscalYear() {
      if (this.cumulativeInputFiles.length > 0) {
        const firstFile = this.cumulativeInputFiles[0];
        return firstFile.month >= 4 ? firstFile.year : firstFile.year - 1;
      }
      const currentDate = new Date();
      const currentMonth = currentDate.getMonth() + 1;
      return currentMonth >= 4 ? currentDate.getFullYear() : currentDate.getFullYear() - 1;
    },
    canStartCumulative() {
      return this.cumulativeInputFiles.length > 0;
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
    onNewFileSelect(event) {
      const file = event.target.files[0];
      if (file) {
        this.newFileToAdd = file;
        this.error = null;
      }
    },
    addInputFile() {
      if (!this.newFileToAdd) return;
      this.cumulativeInputFiles.push({
        file: this.newFileToAdd,
        year: this.newFileYear,
        month: this.newFileMonth,
      });
      this.newFileToAdd = null;
      if (this.$refs.newFileInput) {
        this.$refs.newFileInput.value = '';
      }
    },
    removeInputFile(index) {
      this.cumulativeInputFiles.splice(index, 1);
    },
    async startCumulativeAggregation() {
      this.error = null;
      this.cumulativeProgress = 0;
      this.cumulativeLogs = [];
      this.cumulativeModalVisible = true;
      this.cumulativeModalStep = 'processing';
      this.cumulativeModalError = '';

      try {
        this.addCumulativeLog(`${this.cumulativeInputFiles.length}件のファイルをアップロード中...`, 'processing');
        await this.uploadCumulativeFiles();
        this.updateCumulativeLog(0, `${this.cumulativeInputFiles.length}件のファイルアップロード完了`, 'success');
        this.cumulativeProgress = 30;

        this.addCumulativeLog('累積集計を実行中...', 'processing');
        const result = await this.runCumulativeAggregation();
        this.updateCumulativeLog(1, '累積集計完了', 'success');
        this.cumulativeProgress = 100;

        this.cumulativeResult = result;
        this.cumulativeModalStep = 'complete';
      } catch (err) {
        this.cumulativeModalStep = 'error';
        this.cumulativeModalError = err.message || '処理中にエラーが発生しました';
      }
    },
    async uploadCumulativeFiles() {
      const formData = new FormData();
      const filesInfo = [];
      this.cumulativeInputFiles.forEach((item, index) => {
        formData.append(`input_file_${index}`, item.file);
        filesInfo.push({
          index: index,
          year: item.year,
          month: item.month,
        });
      });
      formData.append('files_info', JSON.stringify(filesInfo));
      if (this.existingFilePath) {
        formData.append('existing_file_path', this.existingFilePath);
      }
      formData.append('fiscal_year', this.calculatedFiscalYear);

      const response = await fetch('/api/cumulative/upload-multiple', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message);
      }
      this.cumulativeSessionId = data.session_id;
    },
    async runCumulativeAggregation() {
      const response = await fetch('/api/cumulative/aggregate-multiple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: this.cumulativeSessionId,
        }),
      });
      const data = await response.json();
      if (data.status !== 'success') {
        throw new Error(data.message);
      }
      return data;
    },
    addCumulativeLog(message, status) {
      this.cumulativeLogs.push({ message, status });
    },
    updateCumulativeLog(index, message, status) {
      if (this.cumulativeLogs[index]) {
        this.cumulativeLogs[index].message = message;
        this.cumulativeLogs[index].status = status;
      }
    },
    resetCumulativeForm() {
      this.cumulativeStep = 'upload';
      this.existingFilePath = '';
      this.cumulativeInputFiles = [];
      this.newFileToAdd = null;
      this.cumulativeProgress = 0;
      this.cumulativeLogs = [];
      this.cumulativeResult = null;
      this.cumulativeSessionId = null;
      this.error = null;
      this.cumulativeModalVisible = false;
    },
    closeCumulativeModal() {
      this.cumulativeModalVisible = false;
      if (this.cumulativeModalStep === 'complete') {
        this.resetCumulativeForm();
      }
    },
    closeCumulativeModalIfComplete() {
      if (this.cumulativeModalStep === 'complete' || this.cumulativeModalStep === 'error') {
        this.closeCumulativeModal();
      }
    },
  },
};
</script>

<style scoped>
/* Common styles from App.vue can be used or extended here */
.file-add-section {
  background-color: #fdfdfd;
  border: 1px solid #eee;
  padding: 1rem;
  border-radius: 4px;
  margin-bottom: 1.5rem;
}
.file-add-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.file-hint {
  font-size: 0.85rem;
  color: #777;
  margin: 0.75rem 0 0 0;
}
.btn-add {
  background-color: #27ae60;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
}
.btn-add:disabled {
  background-color: #bdc3c7;
  cursor: not-allowed;
}
.file-list {
  margin-top: 1.5rem;
}
.file-list-title {
  font-size: 1rem;
  font-weight: bold;
  color: #555;
  margin-bottom: 0.5rem;
}
.file-list-items {
  max-height: 200px;
  overflow-y: auto;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 0.5rem;
}
.file-list-item {
  display: flex;
  align-items: center;
  padding: 0.5rem;
  background-color: #f9f9f9;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}
.file-list-item:last-child {
  margin-bottom: 0;
}
.file-name {
  flex-grow: 1;
  font-size: 0.9rem;
}
.file-period {
  font-size: 0.85rem;
  color: #34495e;
  background-color: #ecf0f1;
  padding: 2px 6px;
  border-radius: 10px;
  margin: 0 1rem;
}
.file-remove-btn {
  background: none;
  border: none;
  color: #c0392b;
  cursor: pointer;
  font-weight: bold;
}
.fiscal-year-info {
  margin-top: 1rem;
  background-color: #e8f4fd;
  border: 1px solid #bde0fe;
  color: #0d6efd;
  padding: 0.75rem;
  border-radius: 4px;
}
.path-input {
  flex-grow: 1;
  border: 1px solid #ccc;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  margin-right: 0.5rem;
}
.file-clear-btn {
  background: none;
  border: none;
  color: #7f8c8d;
  cursor: pointer;
}
.output-path {
  font-size: 0.9rem;
  font-family: monospace;
  background-color: #e9ecef;
  padding: 0.2rem 0.4rem;
  border-radius: 4px;
  word-break: break-all;
}
</style>